from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    health_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    profile: Mapped[dict] = mapped_column(JSON)
    family_history: Mapped[list] = mapped_column(JSON)
    vitals: Mapped[dict] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(20), index=True)
    overall_score: Mapped[float] = mapped_column(Float)
    pgrs_score: Mapped[float] = mapped_column(Float)
    brs_score: Mapped[float] = mapped_column(Float)
    vital_score: Mapped[float] = mapped_column(Float)
    result: Mapped[dict] = mapped_column(JSON)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    rating: Mapped[int] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MedicalRecord(Base):
    """AI-extracted health document data; the source image is never persisted."""

    __tablename__ = "medical_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    document_hash: Mapped[str] = mapped_column(String(64), index=True)
    analysis: Mapped[dict] = mapped_column(JSON)
