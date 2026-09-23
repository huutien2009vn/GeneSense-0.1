from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone

from ..schemas import (
    AIInsight,
    AlertItem,
    AssessmentCreate,
    AssessmentResult,
    HealthTip,
    ScoreBreakdown,
    Thresholds,
)


CONDITION_WEIGHTS = {
    "hypertension": 1.8,
    "diabetes": 2.0,
    "cardiovascular": 2.4,
    "stroke": 2.5,
}
F1_RELATIONS = {"father", "mother", "sibling"}


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def _ramp(value: float, healthy_low: float, healthy_high: float, hard_low: float, hard_high: float) -> float:
    if healthy_low <= value <= healthy_high:
        return 0.0
    if value < healthy_low:
        return clamp((healthy_low - value) / max(healthy_low - hard_low, 1) * 100)
    return clamp((value - healthy_high) / max(hard_high - healthy_high, 1) * 100)


def calculate_pgrs(payload: AssessmentCreate) -> float:
    """Pedigree Genetic Risk Score; an explainable proxy, not a genomic PRS."""
    burden = 0.0
    unique_close_conditions: set[str] = set()
    for member in payload.family_history:
        relation_factor = 1.0 if member.relation in F1_RELATIONS else 0.55
        for condition in set(member.conditions):
            burden += CONDITION_WEIGHTS[condition] * relation_factor
            if relation_factor == 1.0:
                unique_close_conditions.add(condition)

    # Saturating curve prevents large families from making the score unbounded.
    score = 100 * (1 - math.exp(-burden / 7.5))
    score += max(0, len(unique_close_conditions) - 1) * 3
    return round(clamp(score), 1)


def calculate_brs(payload: AssessmentCreate) -> float:
    profile = payload.profile
    bmi = profile.bmi
    score = 4.0
    score += clamp((profile.age - 30) * 0.72, 0, 38)

    if bmi < 18.5:
        score += min(12, (18.5 - bmi) * 2.5)
    elif bmi >= 25:
        score += min(25, (bmi - 25) * 2.25)

    if profile.smoker:
        score += 18
    if profile.activity_minutes_week < 150:
        score += (150 - profile.activity_minutes_week) / 150 * 14
    score += min(24, len(set(profile.known_conditions)) * 8)
    return round(clamp(score), 1)


def _variation_score(values: list[float]) -> float:
    if len(values) < 3:
        return 0
    mean = statistics.fmean(values)
    if not mean:
        return 0
    coefficient = statistics.pstdev(values) / mean
    return clamp((coefficient - 0.03) * 400, 0, 35)


def calculate_vital_score(payload: AssessmentCreate) -> float:
    v = payload.vitals
    components: list[tuple[float, float]] = []
    if v.heart_rate is not None:
        components.append((_ramp(v.heart_rate, 60, 100, 35, 160), 0.18))
    if v.systolic is not None:
        components.append((_ramp(v.systolic, 90, 129, 65, 190), 0.24))
    if v.diastolic is not None:
        components.append((_ramp(v.diastolic, 60, 84, 40, 120), 0.18))
    if v.spo2 is not None:
        components.append((_ramp(v.spo2, 95, 100, 85, 101), 0.24))
    if v.glucose is not None:
        # Demo assumes mg/dL and does not infer fasting/post-meal state.
        components.append((_ramp(v.glucose, 70, 140, 45, 260), 0.16))

    if not components:
        return 0.0
    weighted = sum(value * weight for value, weight in components) / sum(weight for _, weight in components)

    for field in ("heart_rate", "systolic", "diastolic", "spo2", "glucose"):
        values = [getattr(sample, field) for sample in payload.samples if getattr(sample, field) is not None]
        weighted += _variation_score(values) * 0.1
    return round(clamp(weighted), 1)


def _build_alerts(payload: AssessmentCreate) -> list[AlertItem]:
    v = payload.vitals
    alerts: list[AlertItem] = []

    def add(metric: str, severity: str, message: str) -> None:
        alerts.append(AlertItem(metric=metric, severity=severity, message=message))

    if v.spo2 is not None:
        if v.spo2 < 90:
            add("SpO₂", "alert", "SpO₂ dưới 90%. Hãy đo lại ngay; nếu kèm khó thở, cần hỗ trợ y tế khẩn cấp.")
        elif v.spo2 < 95:
            add("SpO₂", "attention", "SpO₂ thấp hơn khoảng theo dõi thông thường; nghỉ yên và đo lại.")
    if v.systolic is not None and v.diastolic is not None:
        if v.systolic >= 180 or v.diastolic >= 120:
            add("Huyết áp", "alert", "Chỉ số ở vùng rất cao. Đo lại sau 5 phút và liên hệ cấp cứu nếu có triệu chứng bất thường.")
        elif v.systolic >= 140 or v.diastolic >= 90:
            add("Huyết áp", "attention", "Huyết áp cao; nên ghi lại và trao đổi với nhân viên y tế.")
    if v.heart_rate is not None:
        if v.heart_rate < 40 or v.heart_rate > 150:
            add("Nhịp tim", "alert", "Nhịp tim nằm ngoài vùng an toàn của bản demo; nghỉ yên và đánh giá triệu chứng.")
        elif v.heart_rate < 50 or v.heart_rate > 110:
            add("Nhịp tim", "attention", "Nhịp tim khác vùng nghỉ thường gặp; đo lại khi cơ thể ổn định.")
    if v.glucose is not None:
        if v.glucose < 54 or v.glucose > 300:
            add("Đường huyết", "alert", "Đường huyết ở mức cần xử trí sớm theo kế hoạch của bác sĩ.")
        elif v.glucose < 70 or v.glucose > 180:
            add("Đường huyết", "attention", "Đường huyết cần chú ý; đối chiếu thời điểm ăn và hướng dẫn điều trị cá nhân.")
    if not alerts:
        add("Tổng quan", "safe", "Các chỉ số vừa nhận chưa chạm ngưỡng cảnh báo của bản demo.")
    return alerts


def _rule_tips(payload: AssessmentCreate, level: str, alerts: list[AlertItem]) -> AIInsight:
    tips: list[HealthTip] = []
    profile = payload.profile
    if profile.activity_minutes_week < 150:
        tips.append(HealthTip(title="Tăng vận động từ từ", action="Thêm 10–15 phút đi bộ nhanh vào 5 ngày mỗi tuần.", reason="Mục tiêu tiến dần tới 150 phút vận động mức vừa mỗi tuần.", priority="medium"))
    if profile.bmi >= 25:
        tips.append(HealthTip(title="Theo dõi cân nặng theo tuần", action="Ưu tiên khẩu phần nhiều rau, đạm nạc và giảm đồ uống có đường.", reason="BMI hiện nằm trên vùng tham chiếu của bản demo.", priority="medium"))
    if profile.smoker:
        tips.append(HealthTip(title="Lập kế hoạch bỏ thuốc", action="Chọn một ngày bắt đầu và tìm hỗ trợ từ bác sĩ hoặc chương trình cai thuốc.", reason="Hút thuốc làm tăng rủi ro tim mạch có thể thay đổi được.", priority="high"))
    if any(a.metric == "Huyết áp" for a in alerts):
        tips.append(HealthTip(title="Đo huyết áp đúng tư thế", action="Ngồi nghỉ 5 phút, chân đặt sàn, tay ngang tim rồi đo 2 lần.", reason="Kỹ thuật đo nhất quán giúp giảm sai lệch.", priority="high"))
    if any(a.metric == "Đường huyết" for a in alerts):
        tips.append(HealthTip(title="Ghi rõ thời điểm đo", action="Đánh dấu trước ăn, sau ăn hoặc khi có triệu chứng.", reason="Ngữ cảnh bữa ăn cần thiết để diễn giải đường huyết.", priority="high"))
    if not tips:
        tips.append(HealthTip(title="Duy trì nhịp theo dõi", action="Đo cùng thời điểm và cùng điều kiện trong các ngày tiếp theo.", reason="Xu hướng nhiều ngày hữu ích hơn một phép đo đơn lẻ.", priority="low"))

    follow_up = {
        "safe": "Tiếp tục thói quen lành mạnh và theo dõi định kỳ.",
        "attention": "Nên đo lại trong điều kiện nghỉ ngơi và đặt lịch tư vấn nếu chỉ số lặp lại.",
        "alert": "Ưu tiên đánh giá triệu chứng và tìm hỗ trợ y tế ngay khi có đau ngực, khó thở, lú lẫn hoặc yếu liệt.",
    }[level]
    return AIInsight(
        summary={"safe": "Các chỉ số đã cung cấp chưa chạm ngưỡng cảnh báo. Hãy tiếp tục theo dõi đều đặn.",
                 "attention": "Có yếu tố cần chú ý. Hãy xem hướng dẫn bên dưới và đo lại khi đã nghỉ ngơi.",
                 "alert": "Có dấu hiệu cần được kiểm tra sớm. Ưu tiên đọc cảnh báo và tìm hỗ trợ y tế khi cần."}[level],
        explanations=["Điểm là công cụ sàng lọc minh họa, không phải chẩn đoán.", "Xu hướng và bối cảnh đo quan trọng hơn một giá trị đơn lẻ."],
        tips=tips[:4],
        follow_up=follow_up,
        source="rules",
    )


@dataclass
class RiskCalculation:
    result: AssessmentResult
    pgrs: float
    brs: float
    vitals: float


def calculate_risk(payload: AssessmentCreate) -> RiskCalculation:
    pgrs = calculate_pgrs(payload)
    brs = calculate_brs(payload)
    vitals = calculate_vital_score(payload)

    # Multiplicative three-layer fusion. Each layer amplifies the others.
    multiplicative = ((1 + pgrs / 100) * (1 + brs / 100) * (1 + vitals / 100) - 1) / 7 * 100
    overall = round(clamp(multiplicative), 1)

    attention_threshold = round(max(22, 40 - pgrs * 0.12), 1)
    alert_threshold = round(max(45, 70 - pgrs * 0.16), 1)
    alerts = _build_alerts(payload)
    emergency_override = any(alert.severity == "alert" for alert in alerts)

    if emergency_override or overall >= alert_threshold:
        level = "alert"
    elif overall >= attention_threshold or any(alert.severity == "attention" for alert in alerts):
        level = "attention"
    else:
        level = "safe"

    insight = _rule_tips(payload, level, alerts)
    result = AssessmentResult(
        created_at=datetime.now(timezone.utc),
        risk_level=level,
        scores=ScoreBreakdown(pgrs=pgrs, brs=brs, vitals=vitals, overall=overall),
        thresholds=Thresholds(attention=attention_threshold, alert=alert_threshold),
        alerts=alerts,
        insight=insight,
        disclaimer="Chỉ dùng để tham khảo và hỗ trợ theo dõi, không thay thế chẩn đoán hoặc xử trí của nhân viên y tế.",
    )
    return RiskCalculation(result=result, pgrs=pgrs, brs=brs, vitals=vitals)
