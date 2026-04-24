"""Score earthquake event risk from cached features."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import config
import database


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if numeric != numeric:
        return 0.0
    return numeric


def _magnitude_component(magnitude: float) -> float:
    return _clamp((magnitude / 8.0) * 100.0)


def _depth_component(depth: float) -> float:
    if depth <= 0:
        return 100.0
    if depth >= 300:
        return 0.0
    return _clamp(100.0 - (depth / 300.0) * 100.0)


def _activity_component(recent_region_event_count: float) -> float:
    return _clamp((recent_region_event_count / 10.0) * 100.0)


def _anomaly_component(anomaly_score: float) -> float:
    if anomaly_score <= 0:
        return 0.0
    return _clamp((anomaly_score / 5.0) * 100.0)


def _risk_level(risk_score: float) -> str:
    if risk_score >= config.RISK_LEVEL_HIGH_THRESHOLD:
        return "high"
    if risk_score >= config.RISK_LEVEL_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _build_explanation(
    region: str,
    magnitude: float,
    depth: float,
    recent_region_event_count: float,
    anomaly_score: float,
    risk_score: float,
    risk_level: str,
) -> str:
    segments: List[str] = [
        f"{region} 事件的综合风险评分为 {risk_score:.1f}，判定为 {risk_level.upper()}。",
    ]

    if magnitude >= 5.0:
        segments.append(f"震级 {magnitude:.1f} 较高，是当前评分的主要抬升因素。")
    else:
        segments.append(f"震级 {magnitude:.1f} 处于相对可控范围，对总分抬升有限。")

    if depth <= 70:
        segments.append(f"震源深度 {depth:.1f} km 较浅，潜在感知和影响风险更高。")
    else:
        segments.append(f"震源深度 {depth:.1f} km 较深，降低了部分风险权重。")

    if recent_region_event_count >= 5:
        segments.append(f"近窗内同区域事件数达到 {int(recent_region_event_count)}，区域活跃度偏高。")
    else:
        segments.append(f"近窗内同区域事件数为 {int(recent_region_event_count)}，区域活跃度暂不突出。")

    if anomaly_score > 1:
        segments.append(f"异常分数 {anomaly_score:.2f} 为正且偏高，说明近期活跃度高于历史基线。")
    elif anomaly_score > 0:
        segments.append(f"异常分数 {anomaly_score:.2f} 略高于基线，存在一定异常抬升。")
    else:
        segments.append(f"异常分数 {anomaly_score:.2f} 未显示明显高于历史基线的异常。")

    return "".join(segments)


def score_feature_row(feature_row: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate a rule-based risk score from one feature row."""
    magnitude = _safe_float(feature_row.get("magnitude"))
    depth = _safe_float(feature_row.get("depth"))
    recent_region_event_count = _safe_float(feature_row.get("recent_region_event_count"))
    anomaly_score = _safe_float(feature_row.get("anomaly_score"))
    region = str(feature_row.get("region") or "UNKNOWN")

    magnitude_component = _magnitude_component(magnitude)
    depth_component = _depth_component(depth)
    activity_component = _activity_component(recent_region_event_count)
    anomaly_component = _anomaly_component(anomaly_score)

    risk_score = round(
        magnitude_component * config.RISK_WEIGHT_MAGNITUDE
        + depth_component * config.RISK_WEIGHT_DEPTH
        + activity_component * config.RISK_WEIGHT_ACTIVITY
        + anomaly_component * config.RISK_WEIGHT_ANOMALY,
        4,
    )
    risk_level = _risk_level(risk_score)

    return {
        "event_unid": feature_row["event_unid"],
        "event_time": feature_row["event_time"],
        "region": region,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "magnitude_component": round(magnitude_component, 4),
        "depth_component": round(depth_component, 4),
        "activity_component": round(activity_component, 4),
        "anomaly_component": round(anomaly_component, 4),
        "explanation": _build_explanation(
            region=region,
            magnitude=magnitude,
            depth=depth,
            recent_region_event_count=recent_region_event_count,
            anomaly_score=anomaly_score,
            risk_score=risk_score,
            risk_level=risk_level,
        ),
        "score_version": config.RISK_SCHEMA_VERSION,
        "scored_at": datetime.now(timezone.utc),
    }


def score_recent_features(limit: int = config.DEFAULT_FEATURE_BATCH_LIMIT) -> Dict[str, Any]:
    """Score a batch of recent feature rows and persist the results."""
    feature_rows = database.list_event_features(limit=limit)
    scored_rows: List[Dict[str, Any]] = []
    failed_rows = 0

    for row in feature_rows:
        try:
            scored_rows.append(score_feature_row(row))
        except Exception:
            failed_rows += 1

    written_rows = database.upsert_risk_scores(scored_rows)
    return {
        "candidate_rows": len(feature_rows),
        "processed_rows": len(scored_rows),
        "written_rows": written_rows,
        "failed_rows": failed_rows,
        "limit": limit,
    }
