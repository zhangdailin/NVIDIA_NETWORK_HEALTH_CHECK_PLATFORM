"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""
MULTI_PLAIN_DEVICES = [
    "0xd2f4",
    "0x25b",
    "0x25c",
    "0x1023"    
]


SWITCH_DICT = {
    "0xc738": "SwitchX and SwitchX-2",
    "0x0246": "SwitchX in Flash Recovery Mode",
    "0xcb20": "Switch-IB",
    "0x0247": "Switch-IB in Flash Recovery Mode",
    "0xcb84": "Spectrum",
    "0x0249": "Spectrum in Flash Recovery Mode",
    "0xcf08": "Switch-IB 2",
    "0x024b": "Switch-IB 2 in Flash Recovery Mode",
    "0xd2f0": "Quantum",
    "0x024d": "Quantum in Flash Recovery Mode",
    "0xcf6c": "Spectrum-2",
    "0x024e": "Spectrum-2 in Flash Recovery Mode",
    "0x024f": "Spectrum-2 in Secure Flash Recovery Mode (obsolete) [Internal]",
    "0xcf70": "Spectrum-3",
    "0x0250": "Spectrum-3 in Flash Recovery Mode",
    "0x0251": "Spectrum-3 in Secure Flash Recovery Mode (obsolete) [Internal]",
    "0x0252": "Spectrum-3 Amos GearBox [Internal]",
    "0x0253": "AGBM - Amos GearBox Manager",
    "0xcf80": "Spectrum-4 Spectrum-4",
    "0x0254": "Spectrum-4 in Flash Recovery Mode",
    "0x0255": "Spectrum-4 RMA [Internal]",
    "0x0256": "Abir GearBox",
    "0x0357": "Abir GearBox in Flash Recovery Mode",
    "0x0358": "Abir GearBox in RMA",
    "0xd2f2": "Quantum-2",
    "0x0257": "Quantum-2 in Flash Recovery Mode",
    "0x0258": "Quantum-2 RMA",
    "0xd2f4": "Quantum-3",
    "0x25b" : "Quantum-3 in Flash Recovery Mode",
    "0x25c" : "Quantum-3 RMA",
}


HCA_DICT = {
    "0x1003": "ConnectX-3",
    "0x1011": "Connect-IB",
    "0x1013": "ConnectX-4",
    "0x1015": "ConnectX-4 Lx",
    "0x1017": "ConnectX-5",
    "0x1019": "ConnectX-5 Ex",
    "0x101b": "ConnectX-6",
    "0x1bc6": "CX6 split_2_v1",
    "0x1bca": "CX6 split_2_v2",
    "0x1bcb": "CX6 split_2_v3",
    "0x101d": "ConnectX-6 Dx",
    "0x1021": "Connectx-7",
    "0x1023": "Connectx-8",
    "0x1025": "Connectx-9",
    "0xa2d0": "BlueField with crypto enabled",
    "0xa2d1": "BlueField with crypto disabled",
    "0xa2d4": "BlueField-2 with crypto enabled",
    "0xa2d5": "BlueField-2 with crypto disabled",
    "0xa2d6": "BlueField-2 integrated ConnectX-6 Dx network controller",
    "0xa2da": "BlueField-3 SoC Crypto enabled",
    "0xa2db": "BlueField-3 SoC Crypto disabled",
    "0xa2dc": "BlueField-3 integrated ConnectX-7 network controller",
    "0xcf09": "Aggregation Node",
}


NVLINK_DICT = {
    "0x2900": "GB100",
}


LINK_STATE_MAPPER = {
    0: "Invalid (on get)",
    1: "Sleep",
    2: "Polling",
    3: "Disabled",
    4: "PortConfigurationTraining",
    5: "LinkUp",
    6: "LinkErrorRecovery",
    7: "Phy Test",
    8: "Reserved",
    9: "Reserved",
    10: "Reserved",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "Reserved",
    15: "Reserved",
}


PP_STATE_MAPPER = {
    0: "Invalid (on get)",
    1: "Sleep",
    2: "Polling",
    3: "Disabled",
    4: "PortConfigurationTraining",
    5: "LinkUp",
    6: "LinkErrorRecovery",
    7: "Phy Test",
    8: "Reserved",
    9: "Reserved",
    10: "Reserved",
    11: "Reserved",
    12: "Reserved",
    13: "Reserved",
    14: "Reserved",
    15: "Reserved",
}


RED_FLAGS_THRESHOLD = {
    "LinkDownedCounter":                (0, ">"), # := bigger than zero is a red flag
    "PortRcvErrorsExt":                 (0, ">"),
    "LocalLinkIntegrityErrorsExt":      (0, ">"),
    "PortRcvSwitchRelayErrors":         (0, ">"),
    "PortSwLifetimeLimitDiscards":      (0, ">"),
    "PortSwHOQLifetimeLimitDiscards":   (0, ">"),
    "PortXmitConstraintErrors":         (0, "!="), # := different than zero is a red flag
    "PortRcvConstraintErrors":          (0, "!="),
    "PortRcvRemotePhysicalErrorsRate":  (0, ">"),

    "LinkErrorRecoveryCounterExt":      (0, ">"),
    "ExcessiveBufferOverrunErrorsExt":  (0, ">"),
    "SyncHeaderErrorCounter":           (0, ">"),

    "Log10 Raw BER":                          (-4, ">"),
    "Log10 Effective BER":                    (-4, ">"),
    "Log10 Symbol BER":                       (-4, ">"),
}


MAX_WIDTH = 85


VENDOR_ID = {
    "0x2c9": "NVIDIA"
}


REPLACEMENT_DICT = {
    'Xmit Data Gbps': 
        {'xdata', 'xmit-data', 'xmit_data', 'xmit data'},
    'Xmit Wait Gbps': 
        {'xwait', 'xmit-wait', 'xmit_wait', 'xmit wait'},
    'Avg RTT(μs)': 
        {'avg_rtt', 'avg rtt', 'avg-rtt'},
    'Min RTT(μs)': 
        {'min_rtt', 'min rtt', 'min-rtt'},
    'MAX RTT(μs)': 
        {'max_rtt', 'max rtt', 'max-rtt'},
    'Node Inferred Type': 
        {'type'},
    'Target Type': 
        {'ttype', 'target type'},
    }


TABLEAU_VALID_TAGS = ['tag', 'appName', 'qps', 'messageSize', 'clusterName', 'keep_forever']
