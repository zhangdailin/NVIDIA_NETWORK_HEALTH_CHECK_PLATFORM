"""Anomaly metadata and enums used by the new analysis service."""

from __future__ import annotations

from enum import Enum

IBH_ANOMALY_TBL_KEY = ["NodeGUID", "PortNumber"]
IBH_ANOMALY_AGG_COL = "IBH Anomaly"
IBH_ANOMALY_AGG_WEIGHT = "IBH Anomaly Weight"


class AnomlyType(Enum):
    # congestion / xmit
    IBH_HIGH_XMIT_WAIT = "High xmit-wait"
    IBH_HCA_BP = "HCA Backpressure"
    IBH_PLAIN_UNB = "Unbalanced Plains"
    IBH_AR_UNB = "Unbalanced AR"
    IBH_DRIB_OUTLIER_SW = "DrIB Outlier Switch"
    IBH_UNUSUAL_RTT_NUM = "Unusual RTT Num"
    IBH_HIGH_MIN_RTT = "High Min RTT"
    IBH_FECN_ALERT = "FECN Congestion"
    IBH_BECN_ALERT = "BECN Congestion"
    IBH_XMIT_TIME_CONG = "Transmit Time Congestion"
    IBH_LINK_DOWNSHIFT = "Link Speed/Width Downshift"
    IBH_CREDIT_WATCHDOG = "Credit Watchdog Timeout"

    # signal / optics
    IBH_HIGH_SYMBOL_BER = "High Symbol BER"
    IBH_UNUSUAL_BER = "Unusual BER"
    IBH_OPTICAL_TEMP_HIGH = "Optical Temperature High"
    IBH_OPTICAL_TX_BIAS = "Optical TX Bias Alarm"
    IBH_OPTICAL_TX_POWER = "Optical TX Power Alarm"
    IBH_OPTICAL_RX_POWER = "Optical RX Power Alarm"
    IBH_OPTICAL_VOLTAGE = "Optical Voltage Alarm"

    # errors/topology
    IBH_OUTLIER = "Outlier"
    IBH_RED_FLAG = "Red Flag"
    IBH_ASYM_TOPO = "Asymmetric Topo"
    IBH_DUPLICATE_GUID = "Duplicate GUID"
    IBH_DUPLICATE_DESC = "Duplicate Node Description"

    # config / compliance
    IBH_PSID_UNSUPPORTED = "PSID Not Supported"
    IBH_FW_OUTDATED = "Firmware Below Recommended"
    IBH_CABLE_MISMATCH = "Cable Media/Speed Mismatch"
    IBH_FAN_FAILURE = "Fan Speed Out of Range"

    # routing / adaptive routing
    IBH_ROUTING_RN_ERROR = "RN Routing Error"
    IBH_ROUTING_FR_ERROR = "Fast Recovery Error"
    IBH_ROUTING_HBF_FALLBACK = "HBF Fallback Detected"

    # port health
    IBH_PORT_ICRC_ERROR = "ICRC Error"
    IBH_PORT_PARITY_ERROR = "Parity Error"
    IBH_PORT_UNHEALTHY = "Port Unhealthy"

    # links
    IBH_LINK_ASYMMETRIC = "Asymmetric Link"

    # temperature / power
    IBH_TEMP_CRITICAL = "Temperature Critical"
    IBH_TEMP_WARNING = "Temperature Warning"
    IBH_PSU_CRITICAL = "PSU Critical"
    IBH_PSU_WARNING = "PSU Warning"

    # MLNX counters / performance
    IBH_MLNX_COUNTER_CRITICAL = "MLNX Counter Critical"
    IBH_MLNX_COUNTER_WARNING = "MLNX Counter Warning"
    IBH_FEC_UNCORRECTABLE = "FEC Uncorrectable Blocks"
    IBH_RELAY_ERROR = "Switch Relay Error"

    def __str__(self) -> str:
        return f"{IBH_ANOMALY_AGG_COL} {self.value}"
