"""Knowledge-base explanations for anomalies (ported from ib_analysis)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .anomalies import AnomlyType


@dataclass(frozen=True)
class Explanation:
    title: str
    why_it_matters: str
    likely_causes: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    reference: str


class ExplanationKey:
    HIGH_BER = "high_symbol_ber"
    UNUSUAL_BER = "unusual_ber"
    HIGH_TEMPERATURE = "high_temperature"
    MODERATE_TEMPERATURE = "moderate_temperature"
    LINK_DOWN = "link_down"
    LINK_RECOVERY = "link_recovery"
    CONGESTION = "congestion"
    HCA_BACKPRESSURE = "hca_backpressure"
    RED_FLAG = "red_flag_errors"
    PORT_INACTIVE = "port_not_active"
    OPTICAL_TX_BIAS = "optical_tx_bias"
    OPTICAL_TX_POWER = "optical_tx_power"
    OPTICAL_RX_POWER = "optical_rx_power"
    OPTICAL_VOLTAGE = "optical_voltage"
    CONGESTION_FECN = "congestion_fecn"
    CONGESTION_BECN = "congestion_becn"
    CONGESTION_XMIT_TIME = "congestion_xmit_time"
    PSID_UNSUPPORTED = "psid_unsupported"
    FW_OUTDATED = "firmware_outdated"


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
    ExplanationKey.LINK_RECOVERY: Explanation(
        title="Link error recovery counter increasing",
        why_it_matters="Frequent recoveries indicate link flaps or jitter that trigger retraining and traffic loss even if the port never shows LinkDowned events.",
        likely_causes=(
            "Marginal optics or dirty connectors causing intermittent signal drops",
            "Power or airflow instability leading to rapid port retrains",
        ),
        recommended_actions=(
            "Inspect and clean the optic/cable pair, then reseat to stabilize the signal (doc/ibdiagnet_health_check_guide.md:136-150)",
            "Check rack power/thermal conditions and replace suspect modules if recoveries persist",
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
    ExplanationKey.OPTICAL_TX_BIAS: Explanation(
        title="Optical TX bias current out of spec",
        why_it_matters="Bias current drifting outside the vendor window indicates diode aging or thermal runaway; BER usually rises soon after.",
        likely_causes=(
            "Aging optics or laser driver faults",
            "Excessive temperature or dirty fiber end causing the laser to compensate",
        ),
        recommended_actions=(
            "Inspect the optic pair, clean connectors, and reseat (doc/ibdiagnet_health_check_guide.md:170-233)",
            "Replace the optic if bias alarms persist after cooling and cleaning",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:170-233",
    ),
    ExplanationKey.OPTICAL_TX_POWER: Explanation(
        title="TX optical power alarm",
        why_it_matters="Low TX power reduces margin on long-haul fibers; high TX power may indicate calibration faults and can saturate receivers.",
        likely_causes=(
            "Poor fiber terminations or damaged MPO/MTP connectors",
            "Laser mis-calibration or overheating optics",
        ),
        recommended_actions=(
            "Measure and compare TX power to the module's nominal spec (doc/ibdiagnet_health_check_guide.md:170-233)",
            "Swap or recalibrate the optic if power stays outside the vendor threshold",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:170-233",
    ),
    ExplanationKey.OPTICAL_RX_POWER: Explanation(
        title="RX optical power alarm",
        why_it_matters="Receivers operating below the minimum optical budget experience packet loss and unstable links.",
        likely_causes=(
            "Excessive attenuation (dirty fiber, long patch panels, tight bends)",
            "Far-end transmitter faults lowering delivered power",
        ),
        recommended_actions=(
            "Check fiber health (cleanliness, bend radius) and measure insertion loss",
            "Verify the peer TX power; replace optics on both ends if necessary",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:170-233",
    ),
    ExplanationKey.OPTICAL_VOLTAGE: Explanation(
        title="Optical module supply voltage alarm",
        why_it_matters="Optics require stable supply rails; under-voltage causes brownouts and link drops, over-voltage damages the laser.",
        likely_causes=(
            "Noisy or overloaded PSU/backplane in the switch or chassis",
            "Faulty VRM on the line card / HCA slot",
        ),
        recommended_actions=(
            "Check chassis power feeds and replace suspect modules, then re-run ibdiagnet (doc/ibdiagnet_health_check_guide.md:170-233)",
            "Ensure firmware matches the optic's PSU requirements",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:170-233",
    ),
    ExplanationKey.CONGESTION_FECN: Explanation(
        title="FECN notifications on this port",
        why_it_matters="Forward Explicit Congestion Notifications indicate the port is seeing pressure from downstream nodes, even if PortXmitWait is low.",
        likely_causes=(
            "Hot-spot traffic on the far-end switches/HCAs",
            "Insufficient adaptive routing or QoS leading to uneven flow distribution",
        ),
        recommended_actions=(
            "Trace the path for this port and inspect adjacent hops for congestion counters",
            "Balance traffic by adding bandwidth, enabling ARC, or tuning QoS (doc/ibdiagnet_health_check_guide.md:338-345)",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:338-345",
    ),
    ExplanationKey.CONGESTION_BECN: Explanation(
        title="BECN notifications generated",
        why_it_matters="Backward ECN is emitted when this port needs upstream throttling; persistent BECN means the host/switch is a congestion source.",
        likely_causes=(
            "Host/NIC sending bursts beyond what downstream switches can handle",
            "Mismatched link speeds or disabled flow control",
        ),
        recommended_actions=(
            "Rate-limit offending workloads or redistribute queues across links",
            "Check upstream ports for PortXmitWait and ensure PFC/ECN policies are configured",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:338-345",
    ),
    ExplanationKey.CONGESTION_XMIT_TIME: Explanation(
        title="PortXmitTimeCong ratio above healthy guidance",
        why_it_matters="Time spent transmitting under congestion control indicates prolonged backpressure; the manual treats >=1% as warning and >=5% as severe.",
        likely_causes=(
            "Over-subscribed uplinks or insufficient fabric bandwidth",
            "Unbalanced routing causing certain paths to saturate",
        ),
        recommended_actions=(
            "Analyze traffic matrices and add or rebalance links (doc/ibdiagnet_health_check_guide.md:200-207)",
            "Tune congestion control/ECN settings to react sooner",
        ),
        reference="doc/ibdiagnet_health_check_guide.md:200-207",
    ),
    ExplanationKey.PSID_UNSUPPORTED: Explanation(
        title="PSID does not match the qualified list",
        why_it_matters="Mixing unsupported PSIDs within the same device class complicates firmware lifecycle management and often indicates the wrong SKU or cooling profile.",
        likely_causes=(
            "Node was provisioned with an OEM PSID that differs from the standard fleet profile",
            "Recent RMA introduced a mismatched optic/cooling requirement that was not requalified",
        ),
        recommended_actions=(
            "Validate the adapter label/PSID against the fleet baseline and reflash if necessary (doc/health_check_capabilities.md:43-52)",
            "Align procurement with the approved PSID list before deploying replacements",
        ),
        reference="doc/health_check_capabilities.md:43-52",
    ),
    ExplanationKey.FW_OUTDATED: Explanation(
        title="Firmware below recommended revision",
        why_it_matters="Older firmware lacks congestion-control, optics, and telemetry fixes highlighted in the ibdiagnet guide, leading to inconsistent behavior across the fabric.",
        likely_causes=(
            "Hosts skipped the last coordinated firmware rollout",
            "Adapters were RMA’d but not upgraded to the fleet baseline afterward",
        ),
        recommended_actions=(
            "Upgrade the adapter to at least the recommended firmware listed in fw_matrix.json before returning it to service",
            "Automate firmware compliance checks in CI/CD so drifts are caught immediately",
        ),
        reference="doc/ibdiagnet_manual_summary.md:80-82",
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
    AnomlyType.IBH_OPTICAL_TEMP_HIGH: ExplanationKey.HIGH_TEMPERATURE,
    AnomlyType.IBH_OPTICAL_TX_BIAS: ExplanationKey.OPTICAL_TX_BIAS,
    AnomlyType.IBH_OPTICAL_TX_POWER: ExplanationKey.OPTICAL_TX_POWER,
    AnomlyType.IBH_OPTICAL_RX_POWER: ExplanationKey.OPTICAL_RX_POWER,
    AnomlyType.IBH_OPTICAL_VOLTAGE: ExplanationKey.OPTICAL_VOLTAGE,
    AnomlyType.IBH_FECN_ALERT: ExplanationKey.CONGESTION_FECN,
    AnomlyType.IBH_BECN_ALERT: ExplanationKey.CONGESTION_BECN,
    AnomlyType.IBH_XMIT_TIME_CONG: ExplanationKey.CONGESTION_XMIT_TIME,
    AnomlyType.IBH_PSID_UNSUPPORTED: ExplanationKey.PSID_UNSUPPORTED,
    AnomlyType.IBH_FW_OUTDATED: ExplanationKey.FW_OUTDATED,
}


def get_issue_guide(*, anomaly_type: Optional[AnomlyType] = None, custom_key: Optional[str] = None) -> Optional[Dict[str, object]]:
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
