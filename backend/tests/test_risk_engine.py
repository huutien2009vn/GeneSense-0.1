from backend.app.schemas import AssessmentCreate, FamilyHistoryInput
from backend.app.services.risk_engine import calculate_pgrs, calculate_risk


def make_payload(**vitals):
    return AssessmentCreate.model_validate(
        {
            "profile": {
                "age": 38,
                "sex": "female",
                "height_cm": 162,
                "weight_kg": 58,
                "smoker": False,
                "activity_minutes_week": 180,
                "known_conditions": [],
            },
            "family_history": [],
            "vitals": {"heart_rate": 72, "systolic": 118, "diastolic": 76, "spo2": 98, "glucose": 105} | vitals,
            "samples": [],
        }
    )


def test_healthy_payload_is_safe():
    result = calculate_risk(make_payload()).result
    assert result.risk_level == "safe"
    assert result.scores.overall < result.thresholds.attention


def test_emergency_vital_overrides_combined_score():
    result = calculate_risk(make_payload(spo2=86)).result
    assert result.risk_level == "alert"
    assert any(alert.metric == "SpO₂" and alert.severity == "alert" for alert in result.alerts)


def test_close_family_history_has_higher_pgrs_than_grandparent():
    close = make_payload()
    close.family_history = [FamilyHistoryInput(relation="father", conditions=["cardiovascular"])]
    distant = make_payload()
    distant.family_history = [FamilyHistoryInput(relation="grandfather", conditions=["cardiovascular"])]
    assert calculate_pgrs(close) > calculate_pgrs(distant)


def test_high_pgrs_lowers_alert_threshold():
    baseline = calculate_risk(make_payload()).result
    payload = make_payload()
    payload.family_history = [
        FamilyHistoryInput(relation="father", conditions=["hypertension", "diabetes", "cardiovascular"]),
        FamilyHistoryInput(relation="mother", conditions=["hypertension", "stroke"]),
    ]
    elevated = calculate_risk(payload).result
    assert elevated.thresholds.alert < baseline.thresholds.alert
