"""Knowledge-base explanations for common ibdiagnet issues."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..anomaly import AnomlyType


@dataclass(frozen=True)
class Explanation:
    """Structured payload that explains an ibdiagnet finding."""

    title: str
    why_it_matters: str
    likely_causes: tuple
    recommended_actions: tuple
    reference: str


class ExplanationKey:
    HIGH_BER = "high_symbol_ber"
    UNUSUAL_BER = "unusual_ber"
    HIGH_TEMPERATURE = "high_temperature"
    MODERATE_TEMPERATURE = "moderate_temperature"
    LINK_DOWN = "link_down"
    CONGESTION = "congestion"
    HCA_BACKPRESSURE = "hca_backpressure"
    RED_FLAG = "red_flag_errors"
    PORT_INACTIVE = "port_not_active"


EXPLANATIONS: Dict[str, Explanation] = {
    ExplanationKey.HIGH_BER: Explanation(
        title="Symbol BER above 1e-12 (critical threshold)",
        why_it_matters="The ibdiagnet guide marks symbol BER > 1e-12 as critical because it triggers retransmissions and reduces throughput.",
        likely_causes=(
            "Aging or faulty optical modules/firmware",
            "Dirty, bent, or attenuated fiber links",
            "EMI or damaged shielding around the cable run",
        ),
        recommended_actions=(
            "Clean or replace the affected fiber/optic and verify it is firmly seated (doc/ibdiagnet_health_check_guide.md:155-177)",
            "Check Tx/Rx optical power and temperature against vendor specs",
            "Inspect the far-end port for matching symbol errors and replace optics in pairs when needed",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:155-177",
    ),
    ExplanationKey.UNUSUAL_BER: Explanation(
        title="Unusual BER pattern between raw/effective/symbol metrics",
        why_it_matters="Large gaps between raw, effective, and symbol BER values point to heavy FEC correction and degraded signal integrity.",
        likely_causes=(
            "Mismatched link speed or width between peers",
            "Noise or jitter that FEC cannot fully correct",
        ),
        recommended_actions=(
            "Compare effective vs symbol BER and adjust sampling or lower the link speed if the gap keeps growing",
            "Verify the fiber path (length, routing, bends) and re-route if needed",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:143-177",
    ),
    ExplanationKey.HIGH_TEMPERATURE: Explanation(
        title="Optical module temperature >= 80C",
        why_it_matters="Per the guide, optics at 80C or above are critical because lifetime and stability drop sharply, often leading to link flaps.",
        likely_causes=(
            "Poor airflow or blocked chassis filters",
            "Modules running at sustained peak power without adequate cooling",
        ),
        recommended_actions=(
            "Inspect and restore cold-air flow (clean filters/fans) and confirm rack inlet temperatures (doc/ibdiagnet_health_check_guide.md:170-177)",
            "Consider lowering workload or swapping to optics with better thermal handling",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:170-177",
    ),
    ExplanationKey.MODERATE_TEMPERATURE: Explanation(
        title="Optical module temperature between 70C and 79C",
        why_it_matters="Temperatures in this band are warnings; BER usually rises and the module is close to the critical threshold.",
        likely_causes=(
            "Restricted airflow or localized hot spots inside the rack",
            "Uneven load distribution across nearby HCAs or switches",
        ),
        recommended_actions=(
            "Schedule a cooling/airflow inspection and tidy cable routing to improve convection",
            "Trend the temperature; escalate to replacement if it continues to rise",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:228-233",
    ),
    ExplanationKey.LINK_DOWN: Explanation(
        title="LinkDownedCounter greater than zero",
        why_it_matters="Repeated link downs reduce fabric connectivity and trigger route recalculations, impacting stability.",
        likely_causes=(
            "Loose, damaged, or unseated optics/cables",
            "Power dips or port configuration errors",
        ),
        recommended_actions=(
            "Physically inspect the fiber/cable bend radius and seating (doc/ibdiagnet_health_check_guide.md:136-150)",
            "Review switch/HCA logs to rule out disabled ports or unstable power feeds",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:136-150",
    ),
    ExplanationKey.CONGESTION: Explanation(
        title="PortXmitWait ratio exceeds healthy guidance",
        why_it_matters="The manual treats 1-5% wait ratio as warning and >5% as severe congestion, indicating sustained backpressure.",
        likely_causes=(
            "Hot-spot traffic concentrated on a subset of uplinks",
            "Unbalanced routing/plain allocation or missing QoS tuning",
        ),
        recommended_actions=(
            "Use PM data to find overloaded paths and redistribute traffic or add bandwidth (doc/ibdiagnet_health_check_guide.md:200-207,338-345)",
            "Verify adaptive routing/QoS policies to ensure lanes share traffic evenly",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:200-207,338-345",
    ),
    ExplanationKey.HCA_BACKPRESSURE: Explanation(
        title="HCA backpressure detected",
        why_it_matters="When HCAs generate xmit-wait, applications stall and congestion can propagate into the fabric.",
        likely_causes=(
            "Outdated or inconsistent HCA firmware/driver",
            "Burst-heavy workloads saturating send queues",
        ),
        recommended_actions=(
            "Align firmware and driver versions across hosts",
            "Coordinate with application owners to shape bursts or stagger large jobs",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:200-207",
    ),
    ExplanationKey.RED_FLAG: Explanation(
        title="Error counters (red flag) above zero",
        why_it_matters="Symbol/LinkIntegrity/Constraint counters should remain at zero; any increment signals unhealthy physical layers.",
        likely_causes=(
            "Low-quality or damaged cables/optics",
            "MTU/VL/PKey mismatches causing constraint violations",
        ),
        recommended_actions=(
            "Clear counters, resample, and determine if the error is transient or persistent (doc/ibdiagnet_health_check_guide.md:320-357)",
            "Replace optics/cables and audit port configuration if errors persist",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:320-357",
    ),
    ExplanationKey.PORT_INACTIVE: Explanation(
        title="Port is not Active/LinkUp",
        why_it_matters="Ports in Down/Init remove available bandwidth and can trigger reroutes or stranded paths.",
        likely_causes=(
            "Peer disabled or optic not fully seated",
            "Topology file/configuration mismatch that left the port administratively down",
        ),
        recommended_actions=(
            "Verify the port physical state and GUID mapping to confirm it should be enabled",
            "If unintended, reset the port and validate LinkUp before returning to service",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:118-152",
    ),
}


ANOMALY_TO_KEY = {
    AnomlyType.IBH_HIGH_SYMBOL_BER: ExplanationKey.HIGH_BER,
    AnomlyType.IBH_UNUSUAL_BER: ExplanationKey.UNUSUAL_BER,
    AnomlyType.IBH_HIGH_XMIT_WAIT: ExplanationKey.CONGESTION,
    AnomlyType.IBH_HCA_BP: ExplanationKey.HCA_BACKPRESSURE,
    AnomlyType.IBH_RED_FLAG: ExplanationKey.RED_FLAG,
    AnomlyType.IBH_PLAIN_UNB: ExplanationKey.CONGESTION,
    AnomlyType.IBH_AR_UNB: ExplanationKey.CONGESTION,
    AnomlyType.IBH_DRIB_OUTLIER_SW: ExplanationKey.CONGESTION,
    AnomlyType.IBH_UNUSUAL_RTT_NUM: ExplanationKey.CONGESTION,
    AnomlyType.IBH_HIGH_MIN_RTT: ExplanationKey.CONGESTION,
    AnomlyType.IBH_ASYM_TOPO: ExplanationKey.PORT_INACTIVE,
}


def get_issue_guide(
    *,
    anomaly_type: Optional[AnomlyType] = None,
    custom_key: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """Return a serializable explanation dict for a given anomaly/custom key."""

    key = None
    if anomaly_type and anomaly_type in ANOMALY_TO_KEY:
        key = ANOMALY_TO_KEY[anomaly_type]
    if not key and custom_key:
        key = custom_key
    if not key:
        return None

    explanation = EXPLANATIONS.get(key)
    if not explanation:
        return None

    return {
        "title": explanation.title,
        "why_it_matters": explanation.why_it_matters,
        "likely_causes": list(explanation.likely_causes),
        "recommended_actions": list(explanation.recommended_actions),
        "reference": explanation.reference,
    }
