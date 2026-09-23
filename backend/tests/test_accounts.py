"""Tests use disposable databases and synthetic identities. No Google network calls."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.app import auth
from backend.app import main
from backend.app.database import get_session
from backend.app.migrations import migrate_schema
from backend.app.models import LoginSession, User
from backend.app.schemas import MedicalDocumentAnalysis

HEADERS = {"X-Requested-With": "HealthPredict", "Origin": "http://localhost:8000"}
PROFILE = {
    "display_name": "Người thử nghiệm",
    "profile": {"age": 35, "sex": "female", "height_cm": 165, "weight_kg": 60,
                "activity_minutes_week": 180, "known_conditions": []},
    "family_history": [
        {"member_id": "father", "relation": "father", "knowledge": "known", "conditions": ["hypertension"]},
        {"member_id": "maternal-grandmother", "relation": "grandmother", "side": "maternal", "knowledge": "unknown"},
    ],
    "personal_notes": "Ghi chú riêng", "paternal_notes": "Gia đình phía bố",
    "maternal_notes": "Gia đình phía mẹ", "health_consent": True, "ai_consent": False,
}
MEASUREMENT = {"vitals": {"heart_rate": 72, "systolic": 118, "diastolic": 76, "spo2": 98}, "source": "manual"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "account-test.db"))
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_override():
        async with factory() as session:
            yield session

    monkeypatch.setattr(main, "engine", engine)
    monkeypatch.setattr(auth.settings, "app_env", "development")
    monkeypatch.setattr(auth.settings, "enable_demo_login", True)
    monkeypatch.setattr(auth.settings, "app_base_url", "http://localhost:8000")
    main.app.dependency_overrides[get_session] = session_override
    with TestClient(main.app, base_url="http://localhost:8000", headers=HEADERS) as test_client:
        test_client.db_factory = factory
        yield test_client
    main.app.dependency_overrides.clear()


def login(client):
    response = client.post("/api/auth/demo")
    assert response.status_code == 200
    return response.json()


def test_private_routes_require_login_and_do_not_cache(client):
    for path in ("/api/profile", "/api/assessments", "/api/assessments/unknown", "/api/medical-records"):
        response = client.get(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    assert client.post("/api/assessments", json=MEASUREMENT).status_code == 401
    assert client.post("/api/feedback", json={"rating": 5}).status_code == 401
    assert client.get("/.env").status_code == 404
    assert client.get("/api/not-a-route").status_code == 404


def test_first_login_onboarding_and_profile_survives_reload(client):
    user = login(client)
    assert user["onboarding_completed"] is False
    assert client.get("/api/profile").json()["health"] is None
    assert client.post("/api/assessments", json=MEASUREMENT).status_code == 409
    saved = client.put("/api/profile", json=PROFILE)
    assert saved.status_code == 200
    assert saved.json()["user"]["onboarding_completed"] is True
    assert client.get("/api/auth/me").json()["id"] == user["id"]
    health = client.get("/api/profile").json()["health"]
    assert health["personal_notes"] == PROFILE["personal_notes"]
    assert health["family_history"][1]["side"] == "maternal"
    assert health["family_history"][1]["knowledge"] == "unknown"


def test_account_isolation_including_feedback_and_revoked_cookie(client):
    first = login(client)
    client.put("/api/profile", json=PROFILE)
    record = client.post("/api/assessments", json=MEASUREMENT)
    assert record.status_code == 201
    record_id = record.json()["id"]
    assert len(client.get("/api/assessments").json()) == 1
    raw = client.cookies.get(auth.COOKIE_NAME)
    assert client.post("/api/auth/logout").status_code == 200
    second = login(client)
    assert second["id"] != first["id"]
    assert client.get("/api/profile").json()["health"] is None
    assert client.get("/api/assessments").json() == []
    assert client.get("/api/assessments/" + record_id).status_code == 404
    assert client.post("/api/feedback", json={"rating": 3, "assessment_id": record_id}).status_code == 404
    client.cookies.clear()
    client.cookies.set(auth.COOKIE_NAME, raw)
    assert client.get("/api/auth/me").status_code == 401


def test_cross_origin_writes_and_missing_custom_header_rejected(client):
    assert client.post("/api/auth/demo", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/auth/demo", headers={"X-Requested-With": ""}).status_code == 403
    assert client.get("/api/auth/google/callback?code=forged&state=forged", follow_redirects=False).status_code == 303


def test_profile_validation_and_partial_measurements(client):
    login(client)
    assert client.put("/api/profile", json=PROFILE | {"health_consent": False}).status_code == 422
    assert client.put("/api/profile", json=PROFILE | {"display_name": "   "}).status_code == 422
    client.put("/api/profile", json=PROFILE)
    assert client.post("/api/assessments", json={"vitals": {}}).status_code == 422
    assert client.post("/api/assessments", json={"vitals": {"systolic": 120}}).status_code == 422
    assert client.post("/api/assessments", json={"vitals": {"systolic": 80, "diastolic": 120}}).status_code == 422
    response = client.post("/api/assessments", json={"vitals": {"heart_rate": 72}})
    assert response.status_code == 201
    assert response.json()["measured_vitals"]["spo2"] is None
    emergency = client.post("/api/assessments", json={"vitals": {"spo2": 85}})
    assert emergency.json()["risk_level"] == "alert"


def test_demo_and_no_consent_never_call_ai(client, monkeypatch):
    calls = []

    async def fake_ai(*args):
        calls.append(True)
        return args[-1].insight

    monkeypatch.setattr(main.ai_service, "enrich", fake_ai)
    login(client)
    client.put("/api/profile", json=PROFILE | {"ai_consent": True})
    client.post("/api/assessments", json=MEASUREMENT)
    assert calls == []


def test_expired_sessions_rejected(client):
    login(client)
    raw = client.cookies.get(auth.COOKIE_NAME)

    async def expire():
        async with client.db_factory() as session:
            row = await session.get(LoginSession, auth.digest(raw))
            row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            await session.commit()

    asyncio.run(expire())
    assert client.get("/api/auth/me").status_code == 401


def test_google_callback_creates_one_account_and_remembers_onboarding(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "google_client_id", "synthetic-client")
    monkeypatch.setattr(auth.settings, "google_client_secret", "synthetic-secret")
    monkeypatch.setattr(auth.settings, "session_secret", "s" * 48)

    async def verified_token(request):
        return {"userinfo": {"sub": "synthetic-subject", "email": "test@example.invalid", "email_verified": True, "name": "Test Google"}}

    monkeypatch.setattr(auth.oauth.google, "authorize_access_token", verified_token)
    response = client.get("/api/auth/google/callback?code=synthetic", follow_redirects=False)
    assert response.status_code == 303
    assert "HttpOnly" in response.headers["set-cookie"]
    first = client.get("/api/auth/me").json()
    assert first["onboarding_completed"] is False and first["is_demo"] is False
    assert first["provider"] == "google"
    client.put("/api/profile", json=PROFILE)
    client.post("/api/auth/logout")
    client.get("/api/auth/google/callback?code=synthetic", follow_redirects=False)
    returning = client.get("/api/auth/me").json()
    assert first["id"] == returning["id"]
    assert returning["onboarding_completed"] is True
    assert returning["display_name"] == PROFILE["display_name"]


def test_google_failure_does_not_create_session(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "google_client_id", "synthetic-client")
    monkeypatch.setattr(auth.settings, "google_client_secret", "synthetic-secret")
    monkeypatch.setattr(auth.settings, "session_secret", "s" * 48)
    # Actual Authlib state validation: no matching signed OAuth state exists.
    response = client.get("/api/auth/google/callback?code=forged&state=forged", follow_redirects=False)
    assert response.headers["location"] == "/?auth_error=signin"
    assert client.get("/api/auth/me").status_code == 401


def test_demo_login_disabled_outside_development(client, monkeypatch):
    monkeypatch.setattr(auth.settings, "app_env", "production")
    assert client.get("/api/auth/config").json()["demo_enabled"] is False
    assert client.post("/api/auth/demo").status_code == 404


def test_medical_document_requires_review_then_is_account_scoped(client, monkeypatch):
    login(client)
    client.put("/api/profile", json=PROFILE)
    analysis = MedicalDocumentAnalysis(
        document_type="lab_result",
        document_date="2026-09-20",
        provider="Phòng xét nghiệm mẫu",
        title="Kết quả xét nghiệm giả định",
        summary="Tài liệu giả định dùng để kiểm thử.",
        metrics=[{"name": "Glucose", "value": "99", "unit": "mg/dL", "reference_range": "70-99", "flag": "normal"}],
        conditions=[], medications=[], recommendations=["Đối chiếu với bản gốc."], warnings=[],
        confidence="high", review_required=True, source="ai",
        disclaimer="AI chỉ hỗ trợ trích xuất; cần kiểm tra lại với bản gốc.",
    )

    async def fake_analysis(*_args):
        return analysis

    monkeypatch.setattr(main.ai_service, "analyze_document", fake_analysis)
    image = b"\x89PNG\r\n\x1a\nsynthetic-image"
    analyzed = client.post(
        "/api/medical-records/analyze",
        files={"file": ("synthetic.png", image, "image/png")},
        data={"consent": "true"},
    )
    assert analyzed.status_code == 200
    assert analyzed.json()["analysis"]["review_required"] is True
    assert "không được ghi" in analyzed.json()["privacy_note"]
    assert client.get("/api/medical-records").json() == []

    saved = client.post("/api/medical-records", json={
        "analysis": analyzed.json()["analysis"],
        "document_hash": analyzed.json()["document_hash"],
        "health_consent": True,
    })
    assert saved.status_code == 201
    record_id = saved.json()["id"]
    assert len(client.get("/api/medical-records").json()) == 1
    assert client.post("/api/medical-records", json={
        "analysis": analyzed.json()["analysis"],
        "document_hash": analyzed.json()["document_hash"],
        "health_consent": True,
    }).json()["id"] == record_id
    assert client.delete("/api/medical-records/" + record_id).status_code == 204
    assert client.get("/api/medical-records").json() == []
    record_id = client.post("/api/medical-records", json={
        "analysis": analyzed.json()["analysis"],
        "document_hash": analyzed.json()["document_hash"],
        "health_consent": True,
    }).json()["id"]

    client.post("/api/auth/logout")
    login(client)
    assert client.get("/api/medical-records").json() == []
    assert client.delete("/api/medical-records/" + record_id).status_code == 404


def test_medical_document_validation(client):
    login(client)
    client.put("/api/profile", json=PROFILE)
    image = b"\x89PNG\r\n\x1a\nsynthetic-image"
    no_consent = client.post(
        "/api/medical-records/analyze",
        files={"file": ("synthetic.png", image, "image/png")},
        data={"consent": "false"},
    )
    assert no_consent.status_code == 422
    wrong_type = client.post(
        "/api/medical-records/analyze",
        files={"file": ("synthetic.txt", b"not-an-image", "text/plain")},
        data={"consent": "true"},
    )
    assert wrong_type.status_code == 415


def test_legacy_migration_preserves_unowned_rows(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "legacy.db"))
    with engine.begin() as conn:
        for table in ("assessments", "feedback"):
            conn.execute(text(f"CREATE TABLE {table} (id VARCHAR(36) PRIMARY KEY)"))
            conn.execute(text(f"INSERT INTO {table} (id) VALUES ('legacy-record')"))
        migrate_schema(conn)
        migrate_schema(conn)  # A second startup is safe.
        for table in ("assessments", "feedback"):
            assert "user_id" in {col["name"] for col in inspect(conn).get_columns(table)}
            assert conn.execute(text(f"SELECT id, user_id FROM {table}")).first() == ("legacy-record", None)
    engine.dispose()
