from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


Condition = Literal["hypertension", "diabetes", "cardiovascular", "stroke"]
Relation = Literal["father", "mother", "sibling", "grandfather", "grandmother"]


class ProfileInput(BaseModel):
    age: int = Field(ge=1, le=120)
    sex: Literal["female", "male", "other"]
    height_cm: float = Field(ge=80, le=250)
    weight_kg: float = Field(ge=20, le=350)
    smoker: bool = False
    activity_minutes_week: int = Field(default=120, ge=0, le=3000)
    known_conditions: list[Condition] = Field(default_factory=list)

    @computed_field
    @property
    def bmi(self) -> float:
        return round(self.weight_kg / ((self.height_cm / 100) ** 2), 1)


class FamilyHistoryInput(BaseModel):
    relation: Relation
    conditions: list[Condition] = Field(default_factory=list)
    member_id: str | None = None
    side: Literal["immediate", "paternal", "maternal"] = "immediate"
    knowledge: Literal["unknown", "none", "known"] = "unknown"

    @model_validator(mode="after")
    def consistent_history(self):
        if self.knowledge == "none" and self.conditions:
            raise ValueError("Không thể chọn không có bệnh cùng với một bệnh đã biết.")
        return self


class VitalSample(BaseModel):
    timestamp: datetime | None = None
    heart_rate: float | None = Field(default=None, ge=20, le=260)
    systolic: float | None = Field(default=None, ge=50, le=260)
    diastolic: float | None = Field(default=None, ge=30, le=180)
    spo2: float | None = Field(default=None, ge=50, le=100)
    glucose: float | None = Field(default=None, ge=20, le=600)


class AssessmentCreate(BaseModel):
    profile: ProfileInput
    family_history: list[FamilyHistoryInput] = Field(default_factory=list, max_length=20)
    vitals: VitalSample
    samples: list[VitalSample] = Field(default_factory=list, max_length=120)


class ScoreBreakdown(BaseModel):
    pgrs: float
    brs: float
    vitals: float
    overall: float


class Thresholds(BaseModel):
    attention: float
    alert: float


class AlertItem(BaseModel):
    metric: str
    severity: Literal["safe", "attention", "alert"]
    message: str


class HealthTip(BaseModel):
    title: str
    action: str
    reason: str
    priority: Literal["low", "medium", "high"]


class AIInsight(BaseModel):
    summary: str
    explanations: list[str]
    tips: list[HealthTip]
    follow_up: str
    source: Literal["ai", "rules"] = "rules"


class AssessmentResult(BaseModel):
    id: str | None = None
    created_at: datetime
    risk_level: Literal["safe", "attention", "alert"]
    scores: ScoreBreakdown
    thresholds: Thresholds
    alerts: list[AlertItem]
    insight: AIInsight
    disclaimer: str
    measurement_source: Literal["manual", "ble", "simulation"] = "manual"
    measured_vitals: VitalSample | None = None


class AssessmentHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    risk_level: str
    overall_score: float
    pgrs_score: float
    brs_score: float
    vital_score: float
    vitals: dict


class FeedbackCreate(BaseModel):
    assessment_id: str | None = None
    rating: int = Field(ge=1, le=5)
    message: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_content(self) -> "FeedbackCreate":
        if not self.message.strip() and self.rating < 1:
            raise ValueError("Feedback is empty")
        return self


class FeedbackResult(BaseModel):
    id: str
    status: Literal["received"] = "received"


class AccountProfile(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    profile: ProfileInput
    family_history: list[FamilyHistoryInput] = Field(default_factory=list, max_length=20)
    personal_notes: str = Field(default="", max_length=2000)
    paternal_notes: str = Field(default="", max_length=2000)
    maternal_notes: str = Field(default="", max_length=2000)
    ai_consent: bool = False
    health_consent: Literal[True]

    @model_validator(mode="after")
    def validate_profile(self):
        self.display_name = self.display_name.strip()
        if not self.display_name:
            raise ValueError("Vui lòng nhập tên hiển thị.")
        member_ids = [member.member_id for member in self.family_history if member.member_id]
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("Một người thân chỉ được khai báo một lần.")
        return self


class MeasurementCreate(BaseModel):
    vitals: VitalSample
    samples: list[VitalSample] = Field(default_factory=list, max_length=120)
    source: Literal["manual", "ble", "simulation"] = "manual"

    @model_validator(mode="after")
    def require_measurement(self):
        values = self.vitals.model_dump(exclude={"timestamp"})
        if all(value is None for value in values.values()):
            raise ValueError("Vui lòng cung cấp ít nhất một chỉ số.")
        if (self.vitals.systolic is None) != (self.vitals.diastolic is None):
            raise ValueError("Huyết áp cần cả tâm thu và tâm trương.")
        if self.vitals.systolic is not None and self.vitals.systolic <= self.vitals.diastolic:
            raise ValueError("Huyết áp tâm thu phải lớn hơn tâm trương.")
        return self


class MedicalMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=120)
    unit: str = Field(default="", max_length=40)
    reference_range: str = Field(default="", max_length=120)
    flag: Literal["normal", "high", "low", "abnormal", "unknown"] = "unknown"


class MedicalMedication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    dose: str = Field(default="", max_length=120)
    frequency: str = Field(default="", max_length=160)


class MedicalDocumentAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_type: Literal["lab_result", "prescription", "discharge_note", "imaging_report", "vaccination", "other"]
    document_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    provider: str = Field(default="", max_length=180)
    title: str = Field(min_length=1, max_length=180)
    summary: str = Field(min_length=1, max_length=1200)
    metrics: list[MedicalMetric] = Field(default_factory=list, max_length=50)
    conditions: list[str] = Field(default_factory=list, max_length=30)
    medications: list[MedicalMedication] = Field(default_factory=list, max_length=30)
    recommendations: list[str] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    confidence: Literal["high", "medium", "low"]
    review_required: bool = True
    source: Literal["ai"] = "ai"
    disclaimer: str = Field(min_length=1, max_length=500)


class MedicalDocumentAnalyzeResult(BaseModel):
    analysis: MedicalDocumentAnalysis
    document_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    privacy_note: str


class MedicalRecordCreate(BaseModel):
    analysis: MedicalDocumentAnalysis
    document_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    health_consent: Literal[True]


class MedicalRecordResult(BaseModel):
    id: str
    created_at: datetime
    analysis: MedicalDocumentAnalysis
