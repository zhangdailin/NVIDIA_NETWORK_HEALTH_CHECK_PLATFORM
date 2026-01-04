import os
from datetime import timedelta
import plotext as plt
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as matplt


from .stats_utils import similar_columns
from .utils import remove_redundant_zero, MAX_WIDTH, print_aggregate_two
from .utils import _t, infere_node, xmit_data2bw_gbps, xmit_wait2bw_gbps
from .utils import INFERRED_HEADERS, print_sum_two, get_section_with_title
from .utils import xmit_wait2bw, xmit_data2bw, process_extended_column, color_row
from .utils import aggregate, xy_scatter_plot
from .duration import extract_duration
from .dbcsv import read_index_table, read_table
from .filter import accommodate_filter_in_graph
from .anomaly import (
    get_high_xmit_anomalies,
    get_hca_bp_anomalies, IBH_ANOMALY_AGG_WEIGHT,
    merge_anomalies,
    IBH_ANOMALY_AGG_COL,
    print_no_anomaly_detected,
    contains_anomalies, IBH_ANOMALY_TBL_KEY,
    get_plain_unbalanced_anomalies,
    get_ar_unbalanced_anomalies,
    #get_drib_anomalies
)


class Xmit:
    XIMT_NAME = "PM_DELTA"
    COLUMNS_TO_PRINT = ['Index', 'NodeGUID', 'Node Name', 'PortNumber', 'Attached To',
                        'Xmit Wait', 'Xmit Data']
    COLUMNS_TO_CSV = ['Source', 'Target', 'Source Port', 'Source Name', 'Attached To',
                      'Speed', 'Xmit Wait', 'Xmit Data', 'Source Name', 'Target Name',
                      'Source Inferred Type', 'Target Inferred Type', 'Source GUID', 'Target GUID'
                      ]
    COLUMNS_TO_PRINT_COMPARE = ['Index', 'Node Name', 'PortNumber', 'NodeGUID',
                                'XmitWait A', 'XmitWait B', 'XmitData A', 'XmitData B',
                                "Visual Comparison ('#':data, '+': wait)"]
    COLUMNS_TO_PRINT_ANOMALY = ['Index', 'NodeGUID', 'Node Name', 'PortNumber',
                                'Attached To', 'Xmit Wait', 'Xmit Data', IBH_ANOMALY_AGG_COL]


    def __init__(self, ib_dir, g, hca_m):
        self.html_label = "xmit-wait"

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)

        try:
            hca_df = hca_m.df.copy()
            self.g = g
            self.duration = extract_duration(file_name)
            self.df = read_table(file_name, Xmit.XIMT_NAME, indexced_table)
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)

            self.df['PortXmitWaitTotal'] = self.df['PortXmitWaitExt']
            self.df['PortXmitDataTotal'] = self.df['PortXmitDataExtended']
            self.df['PortXmitWaitTotal'] = pd.to_numeric(self.df['PortXmitWaitTotal'], errors='coerce').fillna(0)
            self.df['PortXmitDataTotal'] = pd.to_numeric(self.df['PortXmitDataTotal'], errors='coerce').fillna(0)

            self.df['Xmit Wait'] = self.df['PortXmitWaitTotal'].apply(xmit_wait2bw, args=(self.duration,))
            self.df['Xmit Data'] = self.df['PortXmitDataTotal'].apply(xmit_data2bw, args=(self.duration,))

            self.df['Xmit Wait Gbps'] = self.df['PortXmitWaitTotal'].apply(xmit_wait2bw_gbps, args=(self.duration,"float"))
            self.df['Xmit Data Gbps'] = self.df['PortXmitDataTotal'].apply(xmit_data2bw_gbps, args=(self.duration,"float"))
            tick_to_seconds = 4e-9  # Each PortXmitWait tick = 4ns per IBDiagnet guide Section 5.2
            duration_seconds = float(self.duration) if self.duration and float(self.duration) > 0 else 1.0
            self.df['WaitSeconds'] = self.df['PortXmitWaitTotal'] * tick_to_seconds
            self.df['WaitRatioPct'] = (self.df['WaitSeconds'] / duration_seconds) * 100
            self.df['CongestionLevel'] = self.df['WaitRatioPct'].apply(self._classify_wait_ratio)

            # Optimize the infere_node operation by pre-computing unique GUIDs and ports
            unique_guid_port_pairs = self.df[['NodeGUID', 'PortNumber']].drop_duplicates()
            
            # Pre-compute node and connection lookups
            node_cache = {}
            connection_cache = {}
            
            for _, row in unique_guid_port_pairs.iterrows():
                guid = str(row['NodeGUID'])
                port = str(row['PortNumber'])
                
                # Cache node lookup
                if guid not in node_cache:
                    node_cache[guid] = g.get_node(guid)
                
                # Cache connection lookup
                cache_key = (guid, port)
                if cache_key not in connection_cache:
                    connection_cache[cache_key] = g.get_connection(guid, port)
            
            # Apply the optimized function
            def optimized_infere_node(row):
                guid = str(row.get('NodeGUID', 'NA'))
                port = str(row.get('PortNumber', 'NA'))
                
                # Initialize default values
                node_name = node_simple_type = node_infere_type = node_id = node_lid = rack = "NA"
                plain = peer_name = peer_id = target_port = peer_guid = peer_infere_type = peer_rack = "NA"
                
                node = node_cache.get(guid)
                if node:
                    node_name = node.name()
                    node_simple_type = node.simple_type()
                    node_infere_type = node.infere_type()
                    node_id = node.id
                    node_lid = node.lid
                    rack = node.rack
                    
                    peer = connection_cache.get((guid, port))
                    if peer:
                        # Safely attempt to get target_port
                        try:
                            port_index = int(port)
                            target_port = node.children[port_index].dstport
                            plain = node.children[port_index].plain
                        except (ValueError, IndexError, AttributeError):
                            target_port = "NA"
                        
                        peer_name = peer.name()
                        peer_id = peer.id
                        peer_guid = peer.guid
                        peer_infere_type = peer.infere_type()
                        peer_rack = peer.rack
                
                return (node_name, node_simple_type, node_infere_type, peer_name, node_id, peer_id,
                        target_port, peer_guid, peer_infere_type, node_lid, plain, rack, peer_rack)
            
            inferred_series = self.df.apply(optimized_infere_node, axis=1)
            inferred_df = inferred_series.apply(pd.Series)
            expected_headers = INFERRED_HEADERS
            if inferred_df.shape[1] != len(expected_headers):
                # Build a same-index, expected-width frame filled with NA to avoid length mismatch
                inferred_df = pd.DataFrame(
                    [[None] * len(expected_headers)] * len(self.df),
                    index=self.df.index,
                    columns=expected_headers,
                )
            else:
                inferred_df.columns = expected_headers
            self.df[expected_headers] = inferred_df

            hca_df.drop([h for h in INFERRED_HEADERS if h in hca_df.columns.tolist()], axis=1, inplace=True)
            self.df = pd.merge(self.df, hca_df, on='NodeGUID', how='left').copy()

            # Data type corrections
            self.df["Rack"] = self.df["Rack"].astype("Int64")

            self.original_df = self.df.copy()
        except KeyError:
            self.df = None

    def is_valid(self):
        return self.df is not None

    def set_html_label(self, label):
        valid_labels = ['xmit-wait', 'xmit-data']
        assert label in valid_labels, f"HTML label must be a member of {valid_labels}"
        self.html_label = label

    @staticmethod
    def calc_ratio(row, max_xmit_data):
        xmit_wait = float(row['PortXmitWaitTotal'])
        xmit_data = float(row['PortXmitDataTotal'])
        if xmit_wait > 10 ** 3:
            return 1 + xmit_wait / (xmit_data + 1)
        return xmit_data / (max_xmit_data + 1)

    @staticmethod
    def _classify_wait_ratio(value):
        """Return congestion level based on PortXmitWait ratio (IBDiagnet Section 5.2)."""
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "unknown"
        if val >= 5:
            return "severe"
        if val >= 1:
            return "warning"
        if val >= 0:
            return "normal"
        return "unknown"

    @staticmethod
    def xmit_compare_plot(row, max_wait_a, max_wait_b, max_data_a, max_data_b):
        max_wait = max(max_wait_a, max_wait_b) + 1
        max_data = max(max_data_a, max_data_b) + 1

        a_w = 1 + row['XmitWait_A'] * 10.0 / max_wait
        b_w = 1 + row['XmitWait_B'] * 10.0 / max_wait
        a_d = 1 + row['XmitData_A'] * 10.0 / max_data
        b_d = 1 + row['XmitData_B'] * 10.0 / max_data

        blue = "\033[34m"
        yello = "\033[33m"
        end = "\033[0m"

        a_str = f"{blue}{'#' * int(a_d)}{'+' * int(a_w)}{end}"
        b_str = f"{yello}{'#' * int(b_d)}{'+' * int(b_w)}{end}"
        return f"{a_str}|{b_str}"

    def __repr__(self):
        return self.table()

    def compare(self, other, sort=0, num_lines=50, extended_columns=None):
        """
        Compares `self` against `other` Xmit instance

        Parameters:
        - sort (int): Specify the sort algorithm. 
            sort < 0    --> no sort at all. The default sort from the ibdiagnet files
            sort == 0   --> the default heuristic sort
            sort > 0    --> specifies the column number to sort. Index starts from 1.
        - num_lines (int): How many lines to print out
        """
        print_table, columns = process_extended_column(Xmit.COLUMNS_TO_PRINT_COMPARE, extended_columns, self.df)
        if not print_table:
            return [columns]

        df_a = self.df.copy()
        df_b = other.df.copy()

        columns = [col for col in Xmit.COLUMNS_TO_PRINT_COMPARE]

        df_a['RatioA'] = df_a.apply(Xmit.calc_ratio, axis=1, args=(df_a['PortXmitDataTotal'].max(),))
        df_b['RatioB'] = df_b.apply(Xmit.calc_ratio, axis=1, args=(df_b['PortXmitDataTotal'].max(),))

        df_a.rename(columns={'PortXmitWaitTotal': 'XmitWait_A', 'PortXmitDataTotal': 'XmitData_A'}, inplace=True)
        df_b.rename(columns={'PortXmitWaitTotal': 'XmitWait_B', 'PortXmitDataTotal': 'XmitData_B'}, inplace=True)

        df = pd.merge(df_a, df_b, on=['PortNumber', 'NodeGUID', 'Node Name'], how='inner')
        if df.shape[0] == 0:
            raise ValueError("The two ibdiganet directory have nothing in common!")

        df['XmitWait A'] = df['XmitWait_A'].apply(xmit_wait2bw, args=(self.duration,))
        df['XmitData A'] = df['XmitData_A'].apply(xmit_data2bw, args=(self.duration,))
        df['XmitWait B'] = df['XmitWait_B'].apply(xmit_wait2bw, args=(other.duration,))
        df['XmitData B'] = df['XmitData_B'].apply(xmit_data2bw, args=(other.duration,))

        df['RatioA2B'] = abs(df['XmitWait_A'] - df['XmitWait_B']) / (df['XmitWait_B'] + 10 ** 9)
        df['RatioB2A'] = abs(df['XmitWait_B'] - df['XmitWait_A']) / (df['XmitWait_A'] + 10 ** 9)

        # Heuristics sorting paramter
        df['Ratio'] = 4 * (df['RatioA2B'] + df['RatioB2A']) + df['RatioA'] + df['RatioB']

        # visually show the xmitData and xmitWait
        title = "Visual Comparison ('#':data, '+': wait)"
        df[title] = df.apply(
            Xmit.xmit_compare_plot,
            args=(
                df['XmitWait_A'].max(),
                df['XmitWait_B'].max(),
                df['XmitData_A'].max(),
                df['XmitData_B'].max()
            ),
            axis=1,
        )

        # Add extended columns
        for col in extended_columns:
            old_a, new_a = f"{col}_x", f"{col}_A"
            old_b, new_b = f"{col}_y", f"{col}_B"

            df.rename(columns={old_a: new_a, old_b: new_b}, inplace=True)
            columns.append(new_a)
            columns.append(new_b)

        if sort == 0:  # Heuristic
            df = df.sort_values(by='Ratio', ascending=False)
        elif abs(sort) > 0:  # column index
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def get_anomalies(self, nlastic=False):
        anom_arr = []

        anom_arr.append(get_hca_bp_anomalies(self.df.copy()))
        anom_arr.append(get_plain_unbalanced_anomalies(self.df.copy(), xmit="wait"))
        anom_arr.append(get_plain_unbalanced_anomalies(self.df.copy(), xmit="data"))
        anom_arr.append(get_ar_unbalanced_anomalies(self.df.copy(), xmit="wait"))
        anom_arr.append(get_ar_unbalanced_anomalies(self.df.copy(), xmit="data"))

        if nlastic:
            anom_arr.append(get_high_xmit_anomalies(self.df.copy()))

            # DrIB anomaly detection
            # drib_dfs = list(
            #     df_drib
            #     for sw_type in ['LEAF', 'SPINE', 'CORE']
            #     if not (df_drib := get_drib_anomalies(self.df.copy(), switch_type=sw_type)).empty
            # )
            # if drib_dfs:
            #     anom_arr.append(pd.concat(drib_dfs, axis=0))

        df_anomalies = merge_anomalies(self.df, anom_arr)
        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        """
        Main execution point from ib_analysis
        """
        df_anomalies = self.get_anomalies()

        if not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        print_table, columns = process_extended_column(Xmit.COLUMNS_TO_PRINT_ANOMALY, extended_columns, self.df)
        if not print_table:
            return columns

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

    def table(self, sort=0, num_lines=50, extended_columns=None, similar=None, color_plains=False, agg_plains=False):
        """
            Returns the xmit-data and xmit-wait analysis table

            Parameters:
            - sort (int): Specify the sort algorithm. 
                sort < 0    --> no sort at all. The default sort from the ibdiagnet files
                sort == 0   --> the default heuristic sort
                sort > 0    --> specifies the column number to sort. Index starts from 1.
            - num_lines (int): How many lines to print out
        """
        if agg_plains:
            df = self.get_aggregated_plains()
        else:
            df = self.df.copy()

        if self.is_nvlink():
            Xmit.COLUMNS_TO_PRINT.append('Rack')

        print_table, columns = process_extended_column(Xmit.COLUMNS_TO_PRINT, extended_columns, df)
        if not print_table:
            return [columns]

        # heuristic for the default sorting
        df['Ratio'] = df.apply(Xmit.calc_ratio, axis=1, args=(df['PortXmitDataTotal'].max(),))

        if sort == 0:
            df = df.sort_values(by='Ratio', ascending=False)
        elif abs(sort) > 0:
            sort_col = columns[abs(sort) - 1]
            if sort_col.startswith("Xmit "):
                sort_col += " Gbps"
            df = df.sort_values(by=sort_col, ascending=(sort < 0))

        if similar:
            cols = similar_columns(self.df, similar)
            for col in cols:
                columns.append(col)

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)

        if color_plains:
            df = df.apply(color_row, axis=1)

        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def to_csv(self, g, nodes_filename="nodes.csv", edges_filename="edges.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()
        nodes, edges = g.to_dataframe(xmit=self)

        if edges.shape[0] == 0: # b2b scenario. We don't have any switches or edges!
            removed_index = Xmit.COLUMNS_TO_PRINT.copy()
            removed_index.remove("Index")
            df[removed_index + extended_columns].to_csv(edges_filename, index=False)
            return [edges_filename]

        edges.drop([h for h in df.columns.tolist() if h in edges.columns.tolist()], axis=1, inplace=True)
        merged_df = pd.merge(df, edges, left_on=IBH_ANOMALY_TBL_KEY, right_on=['Source GUID', 'Source Port'], how="inner")

        assert len(edges) >= len(merged_df), f"Unexpected merge result: full size: {len(edges)}, filtered size: {len(merged_df)}"

        nodes.to_csv(nodes_filename, index=False)
        merged_df[Xmit.COLUMNS_TO_CSV + extended_columns].to_csv(edges_filename, index=False)

        return [nodes_filename, edges_filename]

    def print_plot(self, extended_columns=None):
        if not extended_columns:
            extended_columns = ['xmit-data', 'xmit-wait']
        return xy_scatter_plot(self.df, extended_columns)

    def print_overview(self, extended_columns=None):
        plots = []

        if not extended_columns:
            extended_columns = []
        nodes, _ = self.g.to_dataframe(xmit=self)

        report_sections = [('InferredType', 'DeviceType', 'Network Layer')]
        for col1, col2, txt in report_sections:
            title=f"Overview | number of elements in each {_t(txt)}"
            plot = print_aggregate_two(nodes, col1, col2, title=title)
            plots.append(plot)
        plots.append("")

        if self.is_nvlink():
            plots.extend(self.print_overview_nvlink())
        else:
            plots.extend(self.print_overview_normal(nodes=nodes, extended_columns=extended_columns))
        return plots

    def is_nvlink(self):
        return len(self.original_df[self.original_df['Simple Type'] == 'GPU']) > 30

    def print_overview_nvlink(self):
        plots = []

        _, filtered_df = accommodate_filter_in_graph(
            nodes=None,
            edges=self.original_df.copy(),
            filtering_df=self.df.copy(),
            src_guid='NodeGUID',
            dst_guid='Target GUID',
            src_port='PortNumber',
            dst_port='Target Port')

        columns = ['Xmit Wait Gbps', 'Xmit Data Gbps']
        directions_df = filtered_df[['Node Inferred Type', 'Target Type']].drop_duplicates()
        direction_set = set(tuple(row) for row in directions_df.to_numpy())

        racks = filtered_df['Rack'].dropna().unique()
        for rack in racks:
            for source, destination in direction_set:
                _names, _counts = [], [[] for _ in columns]

                # Subset the DataFrame
                df = filtered_df[
                    (filtered_df['Rack'] == rack) &
                    (filtered_df['Target Type'] == destination) &
                    (filtered_df['Node Inferred Type'] == source)
                ][['NodeGUID', 'Name']].drop_duplicates()

                # Iterate row-by-row to access NodeGUID and Name
                for row in df.itertuples(index=False):
                    guid = row.NodeGUID
                    _names.append(row.Name)
                    for index, col in enumerate(columns):
                        aggregated_stats = int(filtered_df[filtered_df['NodeGUID'] == guid][col].sum())
                        _counts[index].append(aggregated_stats)

                title = f'Rack{rack} {source}s -> {destination}s (Gbps)'

                # Special case --> when a single SW is filtered
                if source == "NVLinkSW" and destination == "GPU" and len(_names) == 1:
                    title = f'Rack{rack} {_names[0]} -> {destination} (Gbps)'
                    _names, _counts = [], [[] for _ in columns]
                    df = filtered_df[
                        (filtered_df['Rack'] == rack) &
                        (filtered_df['Target Type'] == destination) &
                        (filtered_df['Node Inferred Type'] == source)
                    ][['NodeGUID', 'Name', 'Target GUID']].drop_duplicates()
                    for _, row in df.iterrows():
                        guid = row.NodeGUID
                        target_guid = row['Target GUID']
                        _names.append(self.g.get_node(target_guid).name())
                        for index, col in enumerate(columns):
                            aggregated_stats = int(filtered_df[
                                (filtered_df['NodeGUID'] == guid) &
                                (filtered_df['Target GUID'] == target_guid)
                            ][col].sum())
                            _counts[index].append(aggregated_stats)

                # Somtimes after filtering, the src<->dst are empty.
                if len(_names) == 0:
                    continue

                plt.simple_stacked_bar(_names, _counts, width=MAX_WIDTH, labels=columns, title=title)
                plots.append(plt.build())
                plots.append("")

        # Single GPU corner case
        if filtered_df[filtered_df['Node Inferred Type'] == 'GPU']['NodeGUID'].nunique() == 1:
            gpu_name = filtered_df[filtered_df['Node Inferred Type'] == 'GPU']['Node Name'].unique()[0]
            direction_set = [('GPU', 'NVLinkSW')]
            for rack in racks:
                for source, destination in direction_set:
                    _names, _counts = [], [[] for _ in columns]

                    # Subset the DataFrame
                    df = filtered_df[
                        (filtered_df['Rack'] == rack) &
                        (filtered_df['Target Type'] == destination) &
                        (filtered_df['Node Inferred Type'] == source)
                    ][['NodeGUID', 'Name', 'Attached To', 'Target GUID']].drop_duplicates()

                    # Iterate row-by-row to access NodeGUID and Name
                    for _, row in df.iterrows():
                        label = f"{row['Attached To']} ({row['Target GUID']})"
                        guid = row.NodeGUID
                        _names.append(label)
                        for index, col in enumerate(columns):
                            aggregated_stats = int(filtered_df[
                                (filtered_df['NodeGUID'] == guid) &
                                (filtered_df['Target GUID'] == row['Target GUID'])
                            ][col].sum())
                            _counts[index].append(aggregated_stats)

                    title = f'Rack{rack} {gpu_name} -> {destination}s (Gbps)'
                    plt.simple_stacked_bar(_names, _counts, width=MAX_WIDTH, labels=columns, title=title)
                    plots.append(plt.build())
                    plots.append("")

        return plots

    def print_overview_normal(self, nodes, extended_columns=None):
        plots = []
        # # XMIT Aggregate
        columns = ['Xmit Wait Gbps', 'Xmit Data Gbps']
        unique_sw = nodes[nodes['Type'] == 'SW'][['GUID', 'Name', 'InferredType']].drop_duplicates()
        sw_set = set(tuple(row) for row in unique_sw.to_numpy())
        unique_pairs = self.df[self.df['Simple Type'] == 'SW'][['Node Inferred Type', 'Target Type']].drop_duplicates()
        pairs_set = set(tuple(row) for row in unique_pairs.to_numpy() if not 'AGG_NODE' in row)

        for sw_type, attached_to in pairs_set:
            sw_type_set = {s for s in sw_set if s[2] == sw_type}
            _types, _counts = [], [[] for _ in columns]

            for index, col in enumerate(columns):
                for s in sw_type_set:
                    cnt = int(self.df[(self.df['NodeGUID'] == s[0]) & (self.df['Target Type'] == attached_to)][col].sum())
                    _types.append(s[1])  # s(NodeGUID, name, InferredType)
                    _counts[index].append(cnt)

            xmit_sum = sum([sum(arr) for arr in _counts])
            if len(_types) == 0 or xmit_sum == 0:
                continue

            # Sort
            combined = list(zip(_types, * _counts))
            combined.sort(key=lambda x: x[0])
            sorted_data = list(zip(*combined))
            _types = list(sorted_data[0])
            _counts = [list(row) for row in sorted_data[1:]]

            direction = _t(f"{sw_type} ") + f"(attached to {_t(attached_to)})"
            title = f'Aggregated information for each {direction} in Gbps'
            plt.simple_stacked_bar(_types, _counts, width=MAX_WIDTH, labels=columns, title=title)
            plots.append(plt.build())
            plots.append("")

        # Extended columns
        if len(extended_columns) > 0:
            df = self.df.copy()
            for col in extended_columns:
                plot = print_sum_two(
                    df=df,
                    primary_col=col,
                    secondary_cols=['Xmit Wait Gbps', 'Xmit Data Gbps'],
                    title=f"Overview | PM Delta for {_t(col)}"
                )
                plots.append(plot)
        return plots

    def brief_summary(self):
        briefs = []

        nodes, _ = self.g.to_dataframe(xmit=self)
        df = self.df.copy().groupby('NodeGUID').agg({
            'Node Name': 'first',
            'Node Inferred Type': 'first',
            'LID': 'first',
            'FW': 'first',
            'FW Date': 'first',
            'FWInfo_PSID': 'first',
            'HWInfo_UpTime': 'first',
            'PortXmitWaitTotal': 'sum',
            'PortXmitDataTotal': 'sum'
        }).reset_index()
        df = df[df['Node Inferred Type'] != 'AGG_NODE']
        df = pd.merge(df, nodes[['GUID', 'DeviceType', 'Vendor']], left_on='NodeGUID', right_on='GUID', how='left')

        report_sections = [
            ('Node Inferred Type', 'DeviceType', 'Network Layer'),
            ('DeviceType', 'FW', 'Firmware Version'),
        ]

        for col1, col2, txt in report_sections:
            plot = print_aggregate_two(df, col1, col2, title=f"Overview | number of elements in each {_t(txt)}")
            briefs.append(plot)

        ####### Up Time ########
        briefs.append(get_section_with_title("Up Time Stats"))
        metrics = {
            'Up Time': ['max', 'min'],
        }
        agg_dict = {
            "Up Time Max": ('HWInfo_UpTime', 'max'),
            "Up Time Min": ('HWInfo_UpTime', 'min')
        }
        summary = df.groupby('Node Inferred Type').agg(**agg_dict).reset_index()
        summary['Up Time Max'] = summary['Up Time Max'].apply(lambda x: str(timedelta(seconds=int(x, 16))))
        summary['Up Time Min'] = summary['Up Time Min'].apply(lambda x: str(timedelta(seconds=int(x, 16))))
        briefs.append(tabulate(summary, headers='keys', tablefmt='pretty'))
        ####### XMIT ########
        briefs.append(get_section_with_title("Xmit Stats"))
        df = self.df.copy()
        df = df[df['Node Inferred Type'] != 'AGG_NODE']
        df = df[df['Target Type'] != 'AGG_NODE']
        df = df.groupby(['NodeGUID', 'Target Type']).agg({
            'Node Inferred Type': 'first',
            'PortXmitWaitTotal': 'sum',
            'PortXmitDataTotal': 'sum'
        }).reset_index()
        df['Direction'] = df['Target Type'] + " → " + df['Node Inferred Type']

        metrics = {
            'wait': ['max', 'min', 'median'],
            'data': ['max', 'min', 'median']
        }
        agg_dict = {
            f"{stat.capitalize()} Xmit {metric.capitalize()}": ('PortXmit' + metric.capitalize() + 'Total', stat)
            for metric, stats in metrics.items() for stat in stats
        }
        summary = df.groupby('Direction').agg(**agg_dict).reset_index()

        for col in summary.columns.tolist():
            if "Xmit" in col:
                if "Wait" in col:
                    summary[col] = summary[col].apply(xmit_wait2bw, args=(self.duration,))
                if "Data" in col:
                    summary[col] = summary[col].apply(xmit_data2bw, args=(self.duration,))

        briefs.append(tabulate(summary, headers='keys', tablefmt='pretty'))
        return briefs

    def configure_html_edge(self, group, all_edges, net, u, v, phy):
        if self.html_label == "xmit-wait":
            col = "Xmit Wait"
        else:
            col = "Xmit Data"

        label = round(group[col].max(), 1)
        color, width, title = self.visualise_xmit(
            col=col,
            row=group,
            values=all_edges[col],
            current_value=label
        )

        if not net.add_edge(u, v, physics=phy, label=str(label), title=title, color=color, width=width):
            # duplicated edge!
            opt = net.get_edge(v, u).options
            opt['title'] = f"{opt['title']}\n{title}"
            opt['label'] = f"{max(float(opt['label']), label)}"
            if width > opt['width']:
                opt['width'] = width
                opt['color'] = color

    def visualise_xmit(self, col, row, values, current_value):
        col_xwait = 'Xmit Wait'
        col_xdata = 'Xmit Data'

        max_value = round(values.max(), 1) + 0.1
        min_value = round(values[values > 0.5].min(), 1) # remove zeros

        if col == col_xwait:
            width = 1.0 + 6 * (current_value / max_value)
            colors = matplt.get_cmap('turbo')
        else:
            width = 1.0 + 3 * (current_value / max_value)
            colors = matplt.get_cmap('BuGn')

        if max_value < min_value:
            max_value = min_value + 1

        # Normalize value between 0 and 1
        normalized = (current_value - min_value) / (max_value - min_value)
        color = colors(normalized)
        hex_color = '#%02x%02x%02x' % (int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))

        title = (
            f"######## {row.iloc[0]['Source Inferred Type']} #########\n" +
            f"x-wait from {row.iloc[0]['Target Inferred Type']} (min, max): {row[col_xwait].min()} Gbps, {row[col_xwait].max()} Gbps \n" +
            f"TX to {row.iloc[0]['Target Inferred Type']} (min, max): {row[col_xdata].min()} Gbps, {row[col_xdata].max()} Gbps \n" +
            f"# Cables: {row[col_xdata].count()}\n"
        )
        if current_value > 0.2:
            return (hex_color, width, title)
        return ("#808080", 1, title)

    def get_aggregated_plains(self):
        df = self.df.copy()

        hca_df = df[df['Simple Type'] == "HCA"]
        sw_df = df[df['Simple Type'] == "SW"]

        hca_df = aggregate(
            hca_df,
            keys=['NodeGUID'],
            exclude_numerical=['PortNumber']+INFERRED_HEADERS
        )
        sw_df = aggregate(
            sw_df,
            keys=['Name', 'PortNumber'],
            exclude_numerical=['PortNumber']+INFERRED_HEADERS
        )

        df = pd.concat([hca_df, sw_df], ignore_index=True)

        df['Xmit Wait'] = df['PortXmitWaitTotal'].apply(xmit_wait2bw, args=(self.duration,))
        df['Xmit Data'] = df['PortXmitDataTotal'].apply(xmit_data2bw, args=(self.duration,))
        df['Xmit Wait Gbps'] = df['PortXmitWaitTotal'].apply(xmit_wait2bw_gbps, args=(self.duration,))
        df['Xmit Data Gbps'] = df['PortXmitDataTotal'].apply(xmit_data2bw_gbps, args=(self.duration,))

        df.drop(['Plain'], axis=1, inplace=True)

        return df
