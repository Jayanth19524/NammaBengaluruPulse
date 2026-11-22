"""
Static alert templates — one per incident_type.
No LLM. Returns specific, plain-language recommended_action strings.
"""
from contracts.agent_contract import Severity


def get_recommended_action(
    incident_type: str,
    severity: Severity,
    area_name: str,
    duration_hrs: float,
) -> str:
    """
    Return a specific recommended action string.
    Language is plain and actionable, never generic.
    """
    area = area_name or "your area"

    if incident_type == "supply_disruption":
        if severity in (Severity.critical, Severity.high):
            return (
                f"Supply disruption near {area}. Expected cut: {int(duration_hrs)} hrs. "
                f"Store water now. Tanker helpline: 1916. Emergency kiosk may be available at your ward office."
            )
        if severity == Severity.moderate:
            return (
                f"Reduced supply near {area} for approx {int(duration_hrs)} hrs. "
                f"Store water as a precaution. Check BWSSB updates at bwssb.gov.in."
            )
        return (
            f"Minor supply irregularity reported near {area}. "
            f"Monitor your taps. Likely resolved within {int(duration_hrs)} hrs."
        )

    if incident_type == "tanker_shortage":
        if severity in (Severity.critical, Severity.high):
            return (
                f"Tanker supply unavailable near {area} for {int(duration_hrs)} hrs. "
                f"Contact ward tanker helpline: 080-22221111. Store available water."
            )
        return (
            f"Tanker delayed near {area} by approx {int(duration_hrs)} hrs. "
            f"Check back or call 080-22221111 for updated schedule."
        )

    if incident_type == "sensor_anomaly":
        if severity in (Severity.critical, Severity.high):
            return (
                f"Significant pressure/flow drop detected near {area}. "
                f"Possible main pipe issue. Avoid heavy water use. Report to BWSSB: 1916."
            )
        return (
            f"Low water pressure detected near {area}. "
            f"Monitor your taps. May resolve within {int(max(duration_hrs, 1))} hrs."
        )

    if incident_type == "demand_spike":
        return (
            f"High demand period near {area}. Supply may be reduced for approx {int(duration_hrs)} hrs. "
            f"Use stored water if possible and avoid peak usage 2–5 PM."
        )

    # Fallback for unknown types
    return f"Water supply issue reported near {area}. Check BWSSB updates or call 1916."
