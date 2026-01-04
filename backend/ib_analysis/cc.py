"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""
import os
import re
import pandas as pd
from tabulate import tabulate

from .utils import extend_df, s2n, partition_df
from .utils import print_aggregate, _t, xy_scatter_plot
from .utils import polish_cc_header, process_extended_column
from .anomaly import (
    get_rtt_num_anomalies,
    merge_anomalies, get_high_min_rtt_anomalies, contains_anomalies,
    print_no_anomaly_detected, IBH_ANOMALY_AGG_WEIGHT,
    IBH_ANOMALY_AGG_COL
)
from .compare import compare
from .msg import MSG
from .duration import extract_duration


class CongestionControl:
    CC_COUNTERS = ['NUM RTT', 'DEC','AI INC','HAI INC','CNP HANDLE']
    RTT_COUNTERS = ['Avg RTT(μs)', 'MAX RTT(μs)', 'MIN RTT(μs)']
    COLUMNS_TO_PRINT_NO_COUNTER = [
        'Index', 'NodeGUID', 
        'Node Name', 'PortNumber',
        'Xmit Data', 'Xmit Wait', 'BASE RTT', 'AI'
    ]
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber',
        'Xmit Data', 'Xmit Wait'
    ] + RTT_COUNTERS +  CC_COUNTERS
    COLUMNS_TO_PRINT_ANOMALY = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber',
        'Xmit Data', 'Xmit Wait',
        'Avg RTT(μs)', 'MIN RTT(μs)', 'NUM RTT', IBH_ANOMALY_AGG_COL
    ]
    COLUMNS_TO_PRINT_COMPARE = ['Avg RTT(μs)', 'MAX RTT(μs)', 'MIN RTT(μs)']
    COLUMNS_TO_CSV = ['NodeGUID', 'Node Name', 'PortNumber',
                    'Avg RTT(μs)','MAX RTT(μs)', 'MIN RTT(μs)',
                    'NUM RTT', 'DEC','AI INC','HAI INC','CNP HANDLE',
                    'HYPER DEC','TX DEC', 'NOT VLD RTT','NACK HANDLE']

    def __init__(self, ib_dir, xmit, pminfo):
        self.cc_info = {}
        self.all_headers = []
        try:
            # 检查是否有 .ppcc 文件
            ppcc_files = [f for f in os.listdir(ib_dir) if str(f).endswith(".ppcc")]
            if not ppcc_files:
                # 检查其他可能包含拥塞控制数据的文件
                all_files = os.listdir(ib_dir)
                print(f"错误：找不到 .ppcc 文件。")
                print(f"当前目录中的文件：")
                for file in all_files:
                    print(f"  - {file}")
                print(f"\n拥塞控制分析需要包含拥塞控制数据的 .ppcc 文件。")
                print(f"请确保您的 ibdiagnet 输出包含拥塞控制信息。")
                raise ValueError("Congestion Control file (.ppcc) cannot be found! 请检查 ibdiagnet 输出是否包含拥塞控制数据。")
            
            file = ppcc_files[0]
            filename = os.path.join(ib_dir, file)
            self.duration = extract_duration() # is needed for the filter
        except IndexError as exc:
            raise ValueError("Congestion Control file cannot be found!") from exc

        guids_with_cc_info = self.parse_ccfile(filename)

        if xmit.is_valid():
            # CC is only for the HCAs
            df = xmit.original_df[xmit.original_df['Node Inferred Type'] == 'HCA'].copy()
            
            # exclude entries without CC information
            df = df[df.apply(lambda row: row['NodeGUID'] in guids_with_cc_info, axis=1)]
        else:
            # remove xmit related headers from the table, use PmInfo for the list of the nodes
            # CC is only for the HCAs
            df = pminfo.original_df[pminfo.original_df['Node Inferred Type'] == 'HCA'].copy()
            df = df[df.apply(lambda row: row['NodeGUID'] in guids_with_cc_info, axis=1)]
            CongestionControl.COLUMNS_TO_PRINT = [h for h in CongestionControl.COLUMNS_TO_PRINT if "Xmit" not in h]

        # Expand to DataFrame then assign per column to avoid mismatch
        expanded = df.apply(
            lambda row: pd.Series(extend_df(row=row, info=self.cc_info, headers=self.all_headers)),
            axis=1
        )
        if len(self.all_headers) == expanded.shape[1]:
            expanded.columns = self.all_headers
        else:
            # generate placeholder column names to avoid length mismatch
            expanded.columns = [f"cc_col_{i}" for i in range(expanded.shape[1])]
        for col in self.all_headers:
            df[col] = expanded[col].values

        if self.contains_cc_counters:
            df['Avg RTT(μs)'] = df.apply(calc_average, axis=1)
            df['CC BW Mbps'] = df.apply(calc_cc_bw, axis=1, args=(None,))
            for ccc in CongestionControl.CC_COUNTERS:
                df[ccc] = df[ccc].astype(int)
        else:
            CongestionControl.COLUMNS_TO_PRINT = CongestionControl.COLUMNS_TO_PRINT_NO_COUNTER

        self.df = df
        self.original_df = df.copy()

    def table(self, num_lines=50, sort=0, extended_columns=None):
        if self.contains_cc_counters:
            print_table, columns = process_extended_column(CongestionControl.COLUMNS_TO_PRINT, extended_columns, self.df)
        else:
            print_table, columns = process_extended_column(CongestionControl.COLUMNS_TO_PRINT_NO_COUNTER, extended_columns, self.df)
        if not print_table:
            return [columns]

        df = self.df.copy()
        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        if sort == 0 and self.contains_cc_counters:
            df = df.sort_values(by='NOT VLD RTT', ascending=False)

        df['Index'] = range(1, len(df) + 1)  # should be after sort

        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)

        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def compare(self, other_cc, num_lines=50, sort=0, extended_columns=None):
        if self.contains_cc_counters and other_cc.contains_cc_counters:
            print_table, compare_cols = process_extended_column(
                columns_to_print=CongestionControl.COLUMNS_TO_PRINT_COMPARE,
                extend_column=extended_columns,
                df=self.df
            )
            if not print_table:
                return [compare_cols]
        else:
            return [MSG[2]]

        df, columns = compare(
            df_a=self.df,
            df_b=other_cc.df,
            keys=['NodeGUID', 'PortNumber'],
            common_columns=['Node Name'],
            compare_columns=compare_cols
        )

        if abs(sort) > 0:  # column index
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        df['Index'] = range(1, len(df) + 1)  # should be after sort

        if num_lines > 0:
            df = df.head(num_lines)

        df = df[columns]
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def to_csv(self, csv_filename="cc.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()
        if self.contains_cc_counters:
            df = df[CongestionControl.COLUMNS_TO_CSV + extended_columns]
        else:
            no_cc_counters_columns = CongestionControl.COLUMNS_TO_PRINT_NO_COUNTER.copy()
            no_cc_counters_columns.remove('Index')
            df = df[no_cc_counters_columns + extended_columns]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

    def print_plot(self, extended_columns=None):
        if not extended_columns:
            extended_columns = ['Xmit Data Gbps', 'Avg RTT(μs)']
        return xy_scatter_plot(self.df, extended_columns)


    def print_overview(self, extended_columns=None):
        if not self.contains_cc_counters:
            return [MSG[1]]
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()

        extended_columns += ['MAX RTT(μs)', 'Avg RTT(μs)']
        headers = [(col, bin_size) for col in extended_columns for bin_size in [max(1, int(abs(df[col].max() - df[col].min()) / 10))]]

        sorting_prefix = 'ibh_histogram_values_'
        # Expand into a temporary DataFrame to avoid shape mismatch on assignment
        expanded = df.apply(lambda row: pd.Series(partition_df(row, headers)), axis=1)
        out_cols = [item for h in headers for item in (h[0], f'{sorting_prefix}{h[0]}')]
        if len(out_cols) == expanded.shape[1]:
            expanded.columns = out_cols
        else:
            expanded.columns = [f"hist_col_{i}" for i in range(expanded.shape[1])]
        for col in out_cols:
            df[col] = expanded[col].values

        plots = []
        for col, _ in headers:
            sorting_col = f'{sorting_prefix}{col}'
            df[sorting_col] = df[sorting_col].astype(int)
            plot = print_aggregate(df, col, title=f"Overview | how many node for {_t(col)}", sorting_col=sorting_col)
            plots.append(plot)
        return plots

    def get_anomalies(self):
        df_rtt_num = get_rtt_num_anomalies(self.df.copy())
        df_high_min_rtt = get_high_min_rtt_anomalies(self.df.copy())
        df_anomalies = merge_anomalies(self.df, [df_rtt_num, df_high_min_rtt])

        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        """
        Main execution point from ib_analysis
        """
        df_anomalies = self.get_anomalies()

        if not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        print_table, columns = process_extended_column(CongestionControl.COLUMNS_TO_PRINT_ANOMALY, extended_columns, self.df)
        if not print_table:
            return [columns]

        # Print Anomalies #
        if sort == 0:
            df_anomalies = df_anomalies.sort_values(by=IBH_ANOMALY_AGG_WEIGHT, ascending=False)
        elif abs(sort) > 0:
            df_anomalies = df_anomalies.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        df_anomalies['Index'] = range(1, df_anomalies.shape[0] + 1)  # should be after sort
        df_anomalies = df_anomalies[columns]
        if num_lines > 0:
            df_anomalies = df_anomalies.head(num_lines)

        return [tabulate(df_anomalies, headers='keys', tablefmt='pretty', showindex=False)]

    def parse_ccfile(self, filename):
        filecontent = open(filename, 'r', encoding='latin-1').readlines()
        pattern = re.compile(r"Port=(?P<port>\d+) Lid=(?P<lid>\d+) GUID=0x(?P<guid>[a-fA-F0-9]+).*?")
        self.contains_cc_counters = False

        current_key = None
        seen_slot_1 = False
        headers = set()
        for line in filecontent:
            line = line.strip()
            match = pattern.search(line)
            if match:
                seen_slot_1 = False
                data = match.groupdict()

                guid = data['guid']
                port = data['port']
                guid = hex(int(f"{guid}", 16))
                current_key = (guid, port)

                self.cc_info[current_key] = {}
            elif current_key:
                if line.startswith("algo_slot=1"):
                    seen_slot_1 = True
                if line.startswith("algo_slot=2"):
                    seen_slot_1 = False

                if seen_slot_1:
                    match1 = re.compile(r"param name=(?P<name>\w+), param value=(?P<value>\d+)").search(line)
                    match2 = re.compile(r"counter name=(?P<name>\w+), counter value=(?P<value>\d+)").search(line)
                    if match := (match1 or match2):
                        h_name = polish_cc_header(match['name'])
                        value = s2n(match['value'])

                        if h_name == "NA": # invalid parameter names
                            continue

                        if h_name in ['MAX RTT', 'MIN RTT', 'SUM RTT']:
                            self.contains_cc_counters = True
                            value = float(f"{(value / 1000):.1f}")
                            h_name += "(μs)"

                        self.cc_info[current_key][h_name] = value
                        headers.add(h_name)

        self.all_headers.extend(headers)

        # remove empty items from UFM node
        self.cc_info = {k: v for k, v in self.cc_info.items() if len(v) == len(headers)}
        return set([k[0] for k in self.cc_info])

## static functions ##

def calc_average(row):
    try:
        avg = int(row['SUM RTT(μs)'] / (row['NUM RTT'] + 1))
        return pd.Series(avg)
    except ValueError:
        return pd.Series(-1)
    except TypeError:
        return pd.Series(-1)


def calc_cc_bw(row, duration):
    try:
        # We assume 130 bytes for each RTT probes.
        total_bytes = int(row['NUM RTT']) * 130.0
        bw = total_bytes / duration / 10 ** 6
        return pd.Series(bw)
    except ValueError:
        return pd.Series(-1)
    except TypeError:
        return pd.Series(-1)
