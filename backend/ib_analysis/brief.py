"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

import os
import json
import pandas as pd
from tabulate import tabulate

from ib_analysis.utils import hex2decimal, drop_overlapping, process_extended_column
from ib_analysis.xmit import Xmit
from ib_analysis.msg import MSG
from ib_analysis.const import TABLEAU_VALID_TAGS
from ib_analysis.duration import extract_timestamp
from ib_analysis.anomaly import (
    IBH_ANOMALY_AGG_WEIGHT, IBH_ANOMALY_AGG_COL,
    merge_anomalies, IBH_ANOMALY_TBL_KEY, AnomlyType
)

class Brief:
    # 默认展示更多跨模块的关键信息；若列不存在会在运行时自动剔除
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber', 'Attached To',
        # XMIT
        'Xmit Wait', 'Xmit Data',
        # PORT/PM_INFO（连通性/错误计数）
        'PortState', 'PortPhyState', 'LinkDownedCounter', 'LinkErrorRecoveryCounter',
        'LocalLinkIntegrityErrorsExt', 'PortRcvErrorsExt', 'PortRcvSwitchRelayErrors',
        'PortXmitDiscards', 'PortXmitConstraintErrors', 'PortRcvConstraintErrors',
        # CABLE（光模块）
        'Vendor', 'PN', 'Temperature (c)',
        # CC（拥塞控制）
        'Avg RTT(μs)', 'MAX RTT(μs)', 'MIN RTT(μs)', 'NUM RTT',
    ]
    COLUMNS_TO_PRINT_ANOMALY = ['Index', 'NodeGUID', 'Node Name', 'PortNumber',
                                'Attached To', 'Xmit Wait', 'Xmit Data', IBH_ANOMALY_AGG_COL]

    def __init__(self, g, xmit, hca_m, cable_m, ber_m, cc_m, hist_m, ibdir, tag):
        self.g = g
        self.xmit_m = xmit
        self.hca_m = hca_m
        self.cable_m = cable_m
        self.ber_m = ber_m
        self.cc_m = cc_m
        self.hist_m = hist_m
        self.tag = tag
        self.ibdir = ibdir

        if not xmit.is_valid():
            raise ModuleNotFoundError(f"{Xmit.XIMT_NAME} table not found!")

        file = [f for f in os.listdir(ibdir) if str(f).endswith(".db_csv")][0]
        filename = os.path.join(ibdir, file)
        self.timestamp = extract_timestamp(filename)

        self.df = self.merge()
        self.original_df = self.df.copy()

    def merge(self):
        df = self.xmit_m.df.copy()
        df['Up Time Seconds'] = df['HWInfo_UpTime'].apply(hex2decimal)
        _, edges = self.g.to_dataframe(xmit=self.xmit_m)

        ## XMIT ##
        edges = drop_overlapping(edges, df, [])
        merged_xmit = pd.merge(df, edges, left_on=IBH_ANOMALY_TBL_KEY, right_on=['Source GUID', 'Source Port'], how="inner")
        assert len(edges) >= len(merged_xmit), f"Unexpected merge result: full size: {len(edges)}, filtered size: {len(merged_xmit)}"

        ## HCA ##
        df = self.hca_m.df.copy()
        df = drop_overlapping(df, merged_xmit, ['NodeGUID'])
        merged_hca = pd.merge(merged_xmit, df, on='NodeGUID', how="left")
        
        ## CABLE ##
        if self.cable_m:
            df = self.cable_m.df.copy()
            df.rename(columns={'NodeGuid': 'NodeGUID', 'PortNum': 'PortNumber'}, inplace=True)
            df = drop_overlapping(df, merged_hca)
            merged_cable = pd.merge(merged_hca, df, on=IBH_ANOMALY_TBL_KEY, how="left")
        else:
            merged_cable = merged_hca

        ## BER ##
        if self.ber_m:
            df = self.ber_m.df.copy()
            df = drop_overlapping(df, merged_cable)
            merged_ber = pd.merge(merged_cable, df, on=IBH_ANOMALY_TBL_KEY, how="left")
        else:
            merged_ber = merged_cable
        
        ## CC ##
        if self.cc_m:
            df = self.cc_m.df.copy()
            df = drop_overlapping(df, merged_ber)
            merged_cc = pd.merge(merged_ber, df, on=IBH_ANOMALY_TBL_KEY, how="left")
        else:
            merged_cc = merged_ber
        

        ## histogram ##
        if self.hist_m:
            df = self.hist_m.df.copy()
            df = drop_overlapping(df, merged_cc)
            merged_hist = pd.merge(merged_cc, df, on=IBH_ANOMALY_TBL_KEY, how="left")
        else:
            merged_hist = merged_cc

        return merged_hist

    def table(self, sort=0, num_lines=50, extended_columns=None):
        print_table, columns = process_extended_column(
            Brief.COLUMNS_TO_PRINT, extended_columns, self.df
        )
        if not print_table:
            return [columns]

        df = self.df.copy()

        # 仅保留当前存在的列，避免 KeyError（不同环境字段差异大）
        columns = [c for c in columns if c in df.columns]
        # 若因过滤导致列过少，至少保底核心列
        if not columns:
            columns = ['NodeGUID', 'Node Name', 'PortNumber', 'Xmit Wait', 'Xmit Data']

        # heuristic for the default sorting
        df['ibh_brief_ranking'] = df.apply(Xmit.calc_ratio, axis=1, args=(df['PortXmitDataTotal'].max(),))

        if sort == 0:
            df = df.sort_values(by='ibh_brief_ranking', ascending=False)
        elif abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)

        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def print_overview(self, extended_columns=None):
        if extended_columns:
            return [MSG[0]]
        plots = []
        try:
            plots += self.g.brief_summary() or []
        except Exception:
            pass
        try:
            if self.xmit_m and hasattr(self.xmit_m, 'brief_summary') and self.xmit_m.is_valid():
                plots += self.xmit_m.brief_summary() or []
        except Exception:
            pass
        # 追加其它模块的概览（若实现了 print_overview）
        for mgr in [self.hca_m, self.cable_m, self.ber_m, self.cc_m, self.hist_m]:
            try:
                if mgr and hasattr(mgr, 'print_overview'):
                    plots += mgr.print_overview() or []
            except Exception:
                continue
        return plots

    def get_anomalies(self):
        anomalies_arr = []
        try:
            anomalies_arr.append(self.g.get_anomalies())
        except Exception:
            anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))
        try:
            anomalies_arr.append(self.xmit_m.get_anomalies(nlastic=True))
        except Exception:
            anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))
        if self.ber_m:
            try:
                anomalies_arr.append(self.ber_m.get_anomalies())
            except Exception:
                anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))
        if self.cc_m and self.cc_m.contains_cc_counters:
            try:
                anomalies_arr.append(self.cc_m.get_anomalies())
            except Exception:
                anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))
        if self.cable_m:
            try:
                anomalies_arr.append(self.cable_m.get_anomalies())
            except Exception:
                anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))
        try:
            anomalies_arr.append(self.hca_m.get_anomalies())
        except Exception:
            anomalies_arr.append(pd.DataFrame(columns=['NodeGUID', 'PortNumber']))

        df_anomalies = merge_anomalies(self.df, anomalies_arr)
        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        df_anomalies = self.get_anomalies()

        if not extended_columns:
            extended_columns = []
        columns = Xmit.COLUMNS_TO_PRINT_ANOMALY + extended_columns

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

    def add_possibly_missing_cols(self, df):
        enum_list = [
            str(en) for en in list(AnomlyType) if en not in [
                AnomlyType.IBH_RED_FLAG,
                AnomlyType.IBH_OUTLIER
            ]
        ]

        red_flag_list = []
        if self.cable_m:
            red_flag_list = self.cable_m.all_possible_redflags()

        possibly_missing_cols = enum_list + red_flag_list + [
            "NOT VLD RTT",
            "BW G",
            "DEC",
            "HAI INC",
            "MAX RTT(μs)",
            "MAX INC",
            "CNP DEC",
            "AI INC",
            "CNP HANDLE",
            "HAI PERIOD NS",
            "BASE RTT",
            "TX DEC",
            "RATE ON FIRST CONGESTION",
            "NUM RTT",
            "ALPHA",
            "HYPER DEC",
            "DELAY ONLY",
            "MIN RTT(μs)",
            "HAI",
            "CNP VLD RTT",
            "AI",
            "FIXED RATE",
            "SUM RTT(μs)",
            "MAX DELAY",
            "NACK HANDLE",
            "MAX DEC",
            "Avg RTT(μs)"
        ]

        for col in possibly_missing_cols:
            if col not in df.columns.tolist():
                df[col] = 0

    def meta_data(self, filename):
        """
        Build a JSON metadata file according to three rules:

        1. If self.tag is None or '', create {'ibdir': ibdir, 'tag': ibdir}.
        2. If self.tag has no '=', treat the whole tag value as 'tag'.
        3. If self.tag contains '=', split on ',';   
           * each piece that contains '=' goes into the dict as key→value  
           * exactly one piece *without* '=' is allowed and becomes 'tag'  
           * > 1 such piece → ValueError

        The resulting dict is dumped to *filename* (defaults to self.metafile)
        and the path is returned.
        """
        meta: dict[str, str] = {'ibdir': self.ibdir}

        # Rule 1 – no tag provided
        if not self.tag:
            meta['tag'] = self.ibdir

        else:
            if '=' not in self.tag:                       # Rule 2
                meta['tag'] = self.tag
            else:                                         # Rule 3
                tagless_parts = []
                for part in filter(None, (p.strip() for p in self.tag.split(','))):
                    if '=' in part:
                        key, val = map(str.strip, part.split('=', 1))
                        if not key:                       # safeguard empty key
                            raise ValueError(f"Empty key in tag segment: {part!r}")
                        if key not in TABLEAU_VALID_TAGS:
                            raise ValueError(
                                f"Invalid key {key}." +
                                f"The key should be one of {TABLEAU_VALID_TAGS}"
                            )
                        if key == 'keep_forever':
                            assert val == 'true' or val == 'false', MSG[5]
                        meta[key] = val
                    else:
                        tagless_parts.append(part)

                if len(tagless_parts) == 1:
                    meta['tag'] = tagless_parts[0]
                elif len(tagless_parts) == 0:
                    raise ValueError("No standalone tag provided in tag string.")
                else:  # > 1 tag without '='
                    raise ValueError(
                        f"Expected at most one standalone tag, got: {tagless_parts}"
                    )

        # write JSON (pretty-printed but guaranteed stable order in ≥Py3.7)
        with open(filename, 'w', encoding='latin-1') as f:
            json.dump(meta, f, indent=2)
        return filename

    def to_csv(self, csv_filename="brief", extended_columns=None):
        if extended_columns:
            return [MSG[0]]
        filenames = self.to_(csv_filename, "csv")
        return filenames

    def to_json(self, json_filename="brief", extended_columns=None):
        if extended_columns:
            return [MSG[0]]
        filenames = self.to_(json_filename, "json")
        return filenames

    def to_(self, brief_filename="brief", out_format="csv"):
        """
        We treat this to_csv and to_json differently compared to other oeprations. 
        1- The generated file includes all the columns
        2- The anomalies are also included
        3- A visualisation of the cluster (xmit) will be created as well. 
        """
        df = self.get_anomalies()
        self.add_possibly_missing_cols(df)
        df['Run Date'] = self.timestamp

        # Replace "." with "_" as Tal required (guard when no columns)
        if df.shape[1] > 0:
            df.columns = df.columns.str.replace('.', '_', regex=False)

        dir_name = os.path.dirname(brief_filename)
        base_nlastic_name = os.path.basename(brief_filename).split(".")[0] + ".ibh"
        base_html_name = os.path.basename(brief_filename).split(".")[0] + ".html"
        base_json_name = os.path.basename(brief_filename).split(".")[0] + ".json"
        base_meta_name = os.path.basename(brief_filename).split(".")[0] + ".meta"

        nlastic_file = os.path.join(dir_name, base_nlastic_name)
        html_file = os.path.join(dir_name, base_html_name)
        json_file = os.path.join(dir_name, base_json_name)
        meta_file = os.path.join(dir_name, base_meta_name)

        if out_format == "csv":
            df.to_csv(nlastic_file, index=False)
            df.to_json(json_file, orient='records', lines=False, force_ascii=False)
        if out_format == "json":
            df.to_json(nlastic_file, orient='records', lines=False, force_ascii=False)

        self.g.to_html(edge_handler=self.xmit_m, filename=html_file)
        self.meta_data(filename=meta_file)

        return [nlastic_file, html_file, json_file, meta_file]
