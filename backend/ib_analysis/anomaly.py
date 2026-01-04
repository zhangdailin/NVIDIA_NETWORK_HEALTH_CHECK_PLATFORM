"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

from enum import Enum
import math
import os
import pandas as pd
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import IsolationForest

from .stats_utils import clean_columns
from .const import RED_FLAGS_THRESHOLD
from .utils import NUMERICS, drop_overlapping
from .utils import convert_any_to_decimal, normalize
from .utils import values_with_not_max_length, rename_topo_df

IBH_ANOMALY_TBL_KEY = ['NodeGUID', 'PortNumber']
IBH_ANOMALY_AGG_COL = 'IBH Anomaly'
IBH_ANOMALY_AGG_WEIGHT = 'IBH Anomaly Weight'

IBH_ANOMALY_TOP_COLUMNS = [
    'LinkDownedCounter',
    'LinkErrorRecoveryCounter',
    'SymbolErrorCounter',
    'PortRcvRemotePhysicalErrors',
    'PortRcvErrors',
    'PortXmitDiscards',
    'PortRcvSwitchRelayErrors',
    'ExcessiveBufferOverrunErrors',
    'LocalLinkIntegrityErrors',
    'PortRcvConstraintErrors',
    'PortXmitConstraintErrors',
    'VL15Dropped',
    'SymbolErrorCounterExt',
    'LinkErrorRecoveryCounterExt',
    'LinkDownedCounterExt',
    'PortRcvErrorsExt',
    'PortRcvRemotePhysicalErrorsExt',
    'PortRcvSwitchRelayErrorsExt',
    'PortXmitDiscardsExt',
    'PortXmitConstraintErrorsExt',
    'PortRcvConstraintErrorsExt',
    'LocalLinkIntegrityErrorsExt',
    'ExcessiveBufferOverrunErrorsExt',
    'SyncHeaderErrorCounter',
    'UnknownBlockCounter',
    'ErrorDetectionCounterLane[0]',
    'ErrorDetectionCounterLane[1]',
    'ErrorDetectionCounterLane[2]',
    'ErrorDetectionCounterLane[3]',
    'ErrorDetectionCounterLane[4]',
    'ErrorDetectionCounterLane[5]',
    'ErrorDetectionCounterLane[6]',
    'ErrorDetectionCounterLane[7]',
    'ErrorDetectionCounterLane[8]',
    'ErrorDetectionCounterLane[9]',
    'ErrorDetectionCounterLane[10]',
    'ErrorDetectionCounterLane[11]',
    'max_retransmission_rate_x',
    'PortLocalPhysicalErrors',
    'PortMalformedPacketErrors',
    'PortBufferOverrunErrors',
    'PortDLIDMappingErrors',
    'PortVLMappingErrors',
    'PortLoopingErrors',
    'PortInactiveDiscards',
    'PortNeighborMTUDiscards',
    'link_down_counter',
    'link_error_recovery_counter',
    'symbol_error_counter',
    'port_rcv_remote_physical_errors',
    'port_rcv_errors',
    'port_xmit_discard',
    'port_rcv_switch_relay_errors',
    'excessive_buffer_errors',
    'local_link_integrity_errors',
    'port_rcv_constraint_errors',
    'port_xmit_constraint_errors',
    'symbol_error_counter_extended',
    'link_error_recovery_counter_extended',
    'link_downed_counter_extended',
    'port_rcv_errors_extended',
    'port_rcv_remote_physical_errors_extended',
    'port_rcv_switch_relay_errors_extended',
    'port_xmit_discards_extended',
    'port_xmit_constraint_errors_extended',
    'port_rcv_constraint_errors_extended',
    'local_link_integrity_errors_extended',
    'excessive_buffer_overrun_errors_extended',
    'vl15_dropped_extended',
    'qp1_dropped_extended',
    'sync_header_error_counter',
    'max_retransmission_rate_y',
    'port_local_physical_errors',
    'port_malformed_packet_errors',
    'port_buffer_overrun_errors',
    'port_dlid_mapping_errors',
    'port_vl_mapping_errors',
    'port_looping_errors',
    'port_inactive_discards',
    'port_neighbor_mtu_discards',
    'port_sw_lifetime_limit_discards',
    'port_sw_hoq_lifetime_limit_discards',
    'error_detection_counter_total',
    'error_detection_counter_lane[0]',
    'error_detection_counter_lane[1]',
    'error_detection_counter_lane[2]',
    'error_detection_counter_lane[3]'
]


DRIB_IGNORED_COLUMNS = [
    "NodeGUID",
    "PortGUID",
    "PortNumber",
    "retransmission_per_sec",
    "max_retransmission_rate",
]


class AnomlyType(Enum):
    # when a port has a high xmit-wait value relative to its xmit-data or in absolute terms
    IBH_HIGH_XMIT_WAIT = "High xmit-wait"

    # seeing xmit-wait coming from the HCAs
    IBH_HCA_BP = "HCA Backpressure"

    # unbalanced xmit-wait or xmit-data among plains
    IBH_PLAIN_UNB = "Unbalanced Plains"

    # unbalanced xmit-wait or xmit-data among links between every two switches
    IBH_AR_UNB = "Unbalanced AR"

    # labeled as outlier with the drib original code
    IBH_DRIB_OUTLIER_SW = "DrIB Outlier Switch"

    # high BER value for the 'Symbol BER'
    IBH_HIGH_SYMBOL_BER = "High Symbol BER"

    # raw BER >= Effective BER >= Symbol BER
    IBH_UNUSUAL_BER = "Unusual BER"

    # outlier categorical value
    IBH_OUTLIER = "Outlier"

    # red flag according to RED_FLAGS_THRESHOLD
    IBH_RED_FLAG = "Red Flag"

    # number of RTT is not related to xmit-data
    IBH_UNUSUAL_RTT_NUM = "Unusual RTT Num"

    # high value for the min_rtt
    IBH_HIGH_MIN_RTT = "High Min RTT"
    
    # asymmetric topology
    IBH_ASYM_TOPO = "Asymmetric Topo"

    def __str__(self):
        return f'{IBH_ANOMALY_AGG_COL} {self.value}'  # or any other custom string representation


def print_no_anomaly_detected():
    return "Huray! no anomaly detected."


def detect_numerical_outliers(column):
    q1 = column.quantile(0.25)
    q3 = column.quantile(0.75)
    iqr = q3 - q1
    return ((column < (q1 - 1.5 * iqr)) | (column > (q3 + 1.5 * iqr)))


def detect_categorical_outliers(column, threshold=0.005):
    frequencies = column.value_counts(normalize=True)
    return column.isin(frequencies[frequencies < threshold].index)


def is_red_flag(row, col):
    if not col in row.index.tolist():
        return False

    row_val = convert_any_to_decimal(row[col])
    if col in RED_FLAGS_THRESHOLD:
        th, op = RED_FLAGS_THRESHOLD[col]

        if op == ">":
            return row_val > th
        if op == "!=":
            return row_val != th
        if op == "<":
            return row_val < th
        if op == "==":
            return row_val == th
    return row_val > 0


def get_drib_anomalies(xmit_df, switch_type='LEAF'):
    """
    drib original switch outlier detection
    """
    columns = IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_DRIB_OUTLIER_SW)]

    # Filter to the required switch type first (preserve index for alignment)
    filtered = xmit_df[xmit_df['Node Inferred Type'] == switch_type].copy()
    if filtered.shape[0] == 0:
        return pd.DataFrame(columns=columns)
    # Keep only numeric columns for model and clean rows (record surviving indices)
    numeric_df = filtered.select_dtypes(include=NUMERICS)
    numeric_df = clean_columns(numeric_df)
    # Align identifier columns to the rows that survived cleaning
    align_idx = numeric_df.index
    id_cols = ['NodeGUID', 'PortGUID', 'PortNumber']
    id_cols = [c for c in id_cols if c in filtered.columns]
    id_df = filtered.loc[align_idx, id_cols].reset_index(drop=True)

    # Drop ignored columns if they slipped into numeric_df (defensive)
    col2drop = set(DRIB_IGNORED_COLUMNS).intersection(set(numeric_df.columns.tolist()))
    if col2drop:
        numeric_df = numeric_df.drop(columns=list(col2drop), axis=1)

    # standartize the data
    transformer = RobustScaler().fit(numeric_df)
    df_trans = transformer.transform(numeric_df)

    clf = IsolationForest(max_samples=100, random_state=0)
    clf.fit(df_trans)

    df_anomalies = pd.DataFrame(df_trans)
    df_anomalies["anom_labels"] = clf.predict(df_trans) # 1: normal, -1: abnormal
    df_anomalies["anom_scores"] = abs(clf.score_samples(df_trans))
    # Attach identifiers aligned to the transformed rows
    for col in id_df.columns:
        df_anomalies[col] = id_df[col]

    anomalous_raw_data = xmit_df.merge(
        df_anomalies[["NodeGUID", "PortNumber", "anom_labels", "anom_scores"]],
        on=["NodeGUID", "PortNumber"],
        how="inner"
    )

    # label the drib column and set weight (single-column assignment)
    anomalous_raw_data[str(AnomlyType.IBH_DRIB_OUTLIER_SW)] = anomalous_raw_data.apply(
        lambda row: label_drib_anomalies(row), axis=1
    )

    # Only return the important columns
    return anomalous_raw_data[columns]


def contains_anomalies(df_anomalies):
    count = df_anomalies[IBH_ANOMALY_AGG_COL].isna().sum() + (df_anomalies[IBH_ANOMALY_AGG_COL] == '').sum()
    return count < df_anomalies.shape[0]

## BER ##

def label_high_ber_anomalies(row):
    """
    标记高 BER：直接解析科学计数法的指数部分。
    当 Effective BER 或 Symbol BER 的指数 < 阈值(默认 -14) 时视为异常。
    例如 1.5e-254 的数量级为 -254。
    返回一个权重（阈值与指数差的正值），用于排序。
    """
    # 阈值可通过环境变量 IBA_BER_TH 配置，默认 14（基于“数量级=|负指数|”）。
    # 若传入为负数（兼容旧用法，如 -14），则取其绝对值为数量级阈值。
    try:
        th_val = float(os.environ.get('IBA_BER_TH', '14'))
    except ValueError:
        th_val = 14
    mag_th = int(abs(th_val))

    def _exp_from_sci_str(val: str):
        if not isinstance(val, str):
            return None
        val = val.strip()
        if val.upper() == 'NA' or val == '':
            return None
        # 形如 '1.5e-254' 或 '0e+00'
        if 'e' in val or 'E' in val:
            try:
                parts = val.lower().split('e')
                return int(parts[1])
            except Exception:
                return None
        return None

    eff_str = row.get('Effective BER', 'NA')
    sym_str = row.get('Symbol BER', 'NA')

    eff_exp = _exp_from_sci_str(eff_str)
    sym_exp = _exp_from_sci_str(sym_str)

    def _magnitude(exp):
        if exp is None:
            return None
        # 对于形如 1e-15，数量级为 15；非负指数按 0 处理
        return -int(exp) if int(exp) <= 0 else 0

    eff_mag = _magnitude(eff_exp)
    sym_mag = _magnitude(sym_exp)

    # 触发条件：任一数量级 < 阈值（例如 1e-12 的数量级 12，在阈值 14 下触发）
    eff_bad = (eff_mag is not None and eff_mag < mag_th)
    sym_bad = (sym_mag is not None and sym_mag < mag_th)

    # 需要同时满足：阈值触发 且 SymbolError 有计数
    try:
        fb_min = int(os.environ.get('IBA_BER_FALLBACK_MIN', '1'))  # 默认至少1个符号错误
    except ValueError:
        fb_min = 1

    def _to_int(x):
        try:
            return int(x)
        except Exception:
            return 0

    # 优先使用 net_dump_ext 中的 Symbol Err 字段；不然回退到 PM 计数
    if 'Symbol Err' in row and pd.notnull(row['Symbol Err']):
        sym_cnt = _to_int(row.get('Symbol Err', 0))
    else:
        sym_cnt = _to_int(row.get('SymbolErrorCounter', 0)) + _to_int(row.get('SymbolErrorCounterExt', 0))

    if (eff_bad or sym_bad) and (sym_cnt >= fb_min):
        # 权重按“阈值数量级 - 当前数量级”的最大值，数量级越小（更接近 0），权重越大
        eff_gap = (mag_th - eff_mag) if eff_bad and eff_mag is not None else 0
        sym_gap = (mag_th - sym_mag) if sym_bad and sym_mag is not None else 0
        return max(eff_gap, sym_gap)

    # 不满足条件则非异常
    return 0


def label_unusual_ber_anomalies(row):
    """
    label unusually relationed BER values
    """
    try:
        raw_ber = float(row['Raw BER'])
        effective_ber = float(row['Effective BER'])
        symbol_ber = float(row['Symbol BER'])

        # condition to label as high BER
        if not (raw_ber >= effective_ber and effective_ber >= symbol_ber):
            return 0.5
    except ValueError: # ber = NA
        return 0
    return 0


def get_unusual_ber_anomalies(ber_df):
    ber_df[str(AnomlyType.IBH_UNUSUAL_BER)] = ber_df.apply(
        lambda row: label_unusual_ber_anomalies(row), axis=1
    )
    return ber_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_UNUSUAL_BER)])]


def get_high_ber_anomalies(ber_df):
    ber_df[str(AnomlyType.IBH_HIGH_SYMBOL_BER)] = ber_df.apply(
        lambda row: label_high_ber_anomalies(row), axis=1
    )
    return ber_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_HIGH_SYMBOL_BER)])]


def merge_anomalies(base_df, other_df_list):
    """
    This method has two usecases:
    1- Merge various anomaly detection dataframe inside an operation
    2- In BRIEF operation, we uese this method to merge anomalies from various operation
    """
    output_df = base_df.copy()

    for other_df in other_df_list:
        # Identify if there is an 'IBH Anomaly ...' column in the other_df
        ibh_cols = [col for col in other_df.columns.tolist() if f'{col}'.startswith(IBH_ANOMALY_AGG_COL)]
        if not ibh_cols:
            continue  # Skip if no 'IBH' column is found

        # Drop the aggregated anomaly columns in case of item 2 in above description
        if IBH_ANOMALY_AGG_COL in ibh_cols:
            other_df = other_df.drop(columns=IBH_ANOMALY_AGG_COL, axis=1)
        if IBH_ANOMALY_AGG_WEIGHT in ibh_cols:
            other_df = other_df.drop(columns=IBH_ANOMALY_AGG_WEIGHT, axis=1)

        # Merge the base_df with the other_df on 'NodeGUID' and 'PortNumber'
        other_df = drop_overlapping(other_df, output_df)
        output_df = output_df.merge(
            other_df,
            how='left',
            on=IBH_ANOMALY_TBL_KEY,
        )

    # Get a list of all 'IBH Anomaly' columns in the output_df
    ibh_cols = [col for col in output_df.columns if f'{col}'.startswith(IBH_ANOMALY_AGG_COL)]

    # Define a function to aggregate 'IBH' columns where the value is non-zero
    def aggregate_ibh(row):
        non_zero_ibh = [col for col in ibh_cols if pd.notnull(row[col]) and row[col] != 0]
        if len(non_zero_ibh) > 0:
            # drop the first 'IBH Anomaly' part!
            non_zero_ibh = [str(ibh)[len(IBH_ANOMALY_AGG_COL) + 1:] for ibh in non_zero_ibh]
            return ', '.join(non_zero_ibh)
        return ""

    # Apply the aggregation function to create the 'AGG IBH' column
    output_df[IBH_ANOMALY_AGG_COL] = output_df.apply(aggregate_ibh, axis=1)

    # Calculate the sum of the 'IBH' columns for each row
    output_df[IBH_ANOMALY_AGG_WEIGHT] = output_df[ibh_cols].sum(axis=1, skipna=True)
    return output_df

## XMIT ##

def label_high_xmit_anomalies(row):
    """
    rank and label high xmit related anomalies
    """
    # TODO: make thresholds configurable

    default_th = 200.0   # xwait threshold in Gbps

    xwait = float(row['Xmit Wait Gbps'])
    xdata = float(row['Xmit Data Gbps'])

    # condition to label as high xmit
    if xwait > default_th or (xdata < xwait and xdata > 10):
        return abs(xwait / xdata)
    return 0


def label_hca_bp_anomalies(row):
    """
    rank and label HCA backpressure
    """
    # TODO: make thresholds configurable
    nic_backpressure_th = 0.5    # NIC backpressure threshold in Gbps

    xwait = float(row['Xmit Wait Gbps'])
    xdata = float(row['Xmit Data Gbps'])

    # condition to label backpressure from the NIC
    if xwait > nic_backpressure_th and row['Target Type'] == "HCA":
        return 1 + abs(xwait / xdata)
    return 0


def label_drib_anomalies(row):
    """
    rank and label drib anomalies
    """
    # condition to label backpressure from the NIC
    if row['anom_labels'] == -1:
        return abs(row['anom_scores']) * 10**-1
    return 0


def get_high_xmit_anomalies(xmit_df):
    xmit_df[str(AnomlyType.IBH_HIGH_XMIT_WAIT)] = xmit_df.apply(
        lambda row: label_high_xmit_anomalies(row), axis=1
    )
    return xmit_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_HIGH_XMIT_WAIT)])]


def get_hca_bp_anomalies(xmit_df):
    xmit_df[str(AnomlyType.IBH_HCA_BP)] = xmit_df.apply(
        lambda row: label_hca_bp_anomalies(row), axis=1
    )
    return xmit_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_HCA_BP)])]


def get_plain_unbalanced_anomalies(xmit_df, th=0.5, xmit="wait"):
    pd.options.mode.chained_assignment = None  # Disable the warning

    if xmit == "wait":
        xmit_col = 'Xmit Data Gbps'
    else:
        xmit_col = 'Xmit Wait Gbps'

    xmit_df = xmit_df[xmit_df['Simple Type'] == "HCA"]
    xmit_df.loc[:, xmit_col] = xmit_df[xmit_col].astype(float)

    # Calculate the STD for each HCA, label those with high values
    xmit_df['plain_data_std'] = xmit_df.groupby(['NodeGUID'])[xmit_col].transform('std')
    xmit_df['plain_data_sum'] = xmit_df.groupby(['NodeGUID'])[xmit_col].transform('sum')
    xmit_df['plain_data_avg'] = xmit_df.groupby(['NodeGUID'])[xmit_col].transform('mean')

    # Only pay attention to those with higher than 1 Gbps
    xmit_df = xmit_df[xmit_df['plain_data_sum'] > 1.0]

    xmit_df[str(AnomlyType.IBH_PLAIN_UNB)] = xmit_df.apply(
        lambda row: row['plain_data_std'] if row['plain_data_std'] / row['plain_data_avg'] > th else 0, axis=1
    )

    # Display the updated DataFrame
    return xmit_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_PLAIN_UNB)])]


def get_ar_unbalanced_anomalies(xmit_df, th=0.5, xmit="wait"):
    pd.options.mode.chained_assignment = None  # Disable the warning

    if xmit == "wait":
        xmit_col = 'Xmit Data Gbps'
    else:
        xmit_col = 'Xmit Wait Gbps'

    xmit_df = xmit_df[xmit_df['Simple Type'] == "SW"]
    xmit_df.loc[:, xmit_col] = xmit_df[xmit_col].astype(float)

    # Calculate the STD for each HCA, label those with high values
    keys = ['NodeGUID', 'Target GUID']

    xmit_df['ar_data_sum'] = xmit_df.groupby(keys)[xmit_col].transform('sum')
    xmit_df['ar_data_std'] = xmit_df.groupby(keys)[xmit_col].transform('std')
    xmit_df['ar_data_avg'] = xmit_df.groupby(keys)[xmit_col].transform('mean')

    # Ignore small values!
    xmit_df = xmit_df[xmit_df['ar_data_sum'] > 1.0]

    xmit_df[str(AnomlyType.IBH_AR_UNB)] = xmit_df.apply(
        lambda row: row['ar_data_std'] if row['ar_data_std'] / row['ar_data_avg'] > th else 0, axis=1
    )

    # Display the updated DataFrame
    return xmit_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_AR_UNB)])]

## CABLE ##

def label_red_flags_anomalies(row, important_columns):
    flags = {col: False for col in important_columns}
    for col in important_columns:
        try:
            if is_red_flag(row, col):
                flags[col] = 0.5
            else:
                flags[col] = 0
        except KeyError:
            flags[col] = 0
    return flags


def get_red_flags_anomalies(cable_df, columns):
    keys = [f'{str(AnomlyType.IBH_RED_FLAG)} {col}' for col in columns]
    expanded = cable_df.apply(lambda row: pd.Series(label_red_flags_anomalies(row, columns)), axis=1)
    # 只保留需要的列，并逐列安全赋值
    for col in keys:
        if col in expanded.columns:
            cable_df[col] = expanded[col].values

    non_empty_keys = []
    for col in keys:
        if col in cable_df.columns and cable_df[col].nunique() > 1:
            non_empty_keys.append(col)

    return cable_df[(IBH_ANOMALY_TBL_KEY + non_empty_keys)]


def get_outlier_anomalies(df, columns, th=0.005):
    """
    Only categorical columns.
    """
    column_names = []
    for column in columns:
        # Calculate the normalized frequency (percentage) of each unique value.
        value_frequencies = df[column].value_counts(normalize=True)
        frequency_map = value_frequencies.to_dict()

        # Map the frequencies back to the DataFrame
        freq_series = df[column].map(frequency_map)

        # Map the frequencies back to the DataFrame and apply the transformation.
        column_names.append(f'{str(AnomlyType.IBH_OUTLIER)} {column}')
        df[column_names[-1]] = freq_series.apply(
            lambda freq: 0 if freq > th else normalize(freq/(th+.001))
        )
    return df[(IBH_ANOMALY_TBL_KEY + column_names)]


## CC ##
def label_high_min_rtt_anomalies(row):
    """
    rank and label high min-rtt values
    """
    # TODO: make thresholds configurable

    min_rtt_th = 10.0   # min_rtt threshold in us
    num_rtt_th = 100    # num_rtt threshold

    min_rtt = float(row['MIN RTT(μs)'])
    rtt_num = float(row['NUM RTT'])

    # condition to label as high xmit
    if min_rtt > min_rtt_th and rtt_num > num_rtt_th:
        return abs(min_rtt/100.0)
    return 0


def label_rtt_num_anomalies(row):
    """
    rank and label unusuall NUM RTT values
    """
    # TODO: make thresholds configurable

    xwait = float(row['Xmit Wait Gbps'])
    xdata = float(row['Xmit Data Gbps'])
    rtt_num = float(row['NUM RTT'])

    # condition to label as too few rtt_num relative to xmit values
    coef = rtt_num / (xwait + xdata + 1)
    if coef < 1:
        return coef
    return 0


def get_rtt_num_anomalies(cc_df):
    cc_df[str(AnomlyType.IBH_UNUSUAL_RTT_NUM)] = cc_df.apply(
        lambda row: label_rtt_num_anomalies(row), axis=1
    )
    return cc_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_UNUSUAL_RTT_NUM)])]


def get_high_min_rtt_anomalies(cc_df):
    cc_df[str(AnomlyType.IBH_HIGH_MIN_RTT)] = cc_df.apply(
        lambda row: label_high_min_rtt_anomalies(row), axis=1
    )
    return cc_df[(IBH_ANOMALY_TBL_KEY + [str(AnomlyType.IBH_HIGH_MIN_RTT)])]


## TOPO ##
def get_asymmetric_topo_anomalies(all_nodes, edge_df, side_a="LEAF", side_b="HCA"):
    # Filter the nodes by the side_a type
    nodes = {k: v for k, v in all_nodes.items() if v.inferred_type == side_a}

    # Build count_dict: key is the number of side_b children as a string, value is list of GUIDs
    count_dict = {}
    for guid, a_node in nodes.items():
        num = str(a_node.num_child(side_b))
        count_dict.setdefault(num, []).append(guid)

    if len(count_dict) > 1:
        rename_topo_df(edge_df)
        # Identify the GUIDs with irregular (not max) neighbors
        guids = values_with_not_max_length(count_dict)

        # Explicitly copy to avoid the SettingWithCopyWarning
        filtered_df = edge_df[
            edge_df['NodeGUID'].isin(guids) &
            (edge_df['Target Inferred Type'] == side_b)
        ].copy()

        # Assign the anomaly weight
        key = f"{str(AnomlyType.IBH_ASYM_TOPO)} {side_a}-{side_b}"
        # Unique weight for each port. It's not essential though
        filtered_df[key] = filtered_df.apply(
            lambda row: len(count_dict) + 1.0/int(row['PortNumber']), axis=1
        )

        return filtered_df[IBH_ANOMALY_TBL_KEY + [key]]

    # in case of empty `count_dict` or empty `nodes`
    return pd.DataFrame(columns=IBH_ANOMALY_TBL_KEY)
