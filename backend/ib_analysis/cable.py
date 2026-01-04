"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

import re
import os
import pandas as pd
from tabulate import tabulate
import matplotlib.pyplot as plt

from .utils import _t, print_aggregate, print_aggregate_two
from .utils import remove_redundant_zero, infere_node
from .utils import process_extended_column, INFERRED_HEADERS
from .utils import drop_overlapping, xy_scatter_plot
from .dbcsv import read_index_table, read_table
from .anomaly import (
    get_outlier_anomalies, merge_anomalies, print_no_anomaly_detected,
    contains_anomalies, IBH_ANOMALY_AGG_WEIGHT, IBH_ANOMALY_AGG_COL,
    IBH_ANOMALY_TBL_KEY, get_red_flags_anomalies, AnomlyType
)


class CableManager:
    CABLE_NAME = "CABLE_INFO"
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber', 'Attached To',
        'PN', 'ConnectorFW', 'LinkSpeedEn', 'PortPhyState'
    ]
    COLUMNS_TO_PRINT_ANOMALY = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber',
        'Node Inferred Type', 'PN', 'ConnectorFW', 'Attached To', IBH_ANOMALY_AGG_COL
    ]
    IMPORTANT_ANOMALY_COLUMNS = [
        'LocalPhyError',
        'LinkDownedCounter',
        'PortRcvErrorsExt',
        'LocalLinkIntegrityErrorsExt',
        'PortRcvSwitchRelayErrors',
        'PortXmitConstraintErrors',
        'PortRcvConstraintErrors',
        'PortSwLifetimeLimitDiscards',
        'PortSwHOQLifetimeLimitDiscards',
    ]
    COLUMNS_TO_CSV = [
        'Source', 'Target', 'NodeGUID', 'Node Name', 'PortNumber',
        'Node Inferred Type', 'Vendor', 'PN', 'Temperature (c)',
        'ConnectorFW', 'Rev', 'Attached To', 'LinkSpeedEn', 'PortPhyState', 'PortState',
        'VLCap', 'LinkDownedCounter', 'PortRcvErrorsExt',
        'LocalLinkIntegrityErrorsExt', 'PortRcvSwitchRelayErrors',
        'PortXmitConstraintErrors', 'PortRcvConstraintErrors',
        'PortSwLifetimeLimitDiscards', 'PortSwHOQLifetimeLimitDiscards'
    ]
    COLUMNS_TO_CHECK = ['ConnectorFW', 'PN', 'Vendor']

    def __init__(self, ib_dir, g, port_m, xmit_m):
        self.g = g
        self.ib_dir = ib_dir

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)
        try:
            self.df = read_table(file_name, CableManager.CABLE_NAME, indexced_table)
            self.df = self.df.replace('"', '', regex=True)
            self.df.rename(columns={
                'NodeGuid': 'NodeGUID',
                'PortNum': 'PortNumber',
                'PortGuid': 'PortGUID',
                'FWVersion': 'ConnectorFW',
                }, inplace=True)
            self.df['Temperature (c)'] = self.df.apply(CableManager.temperature_stoi, axis=1)
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)

            # Optimize the infere_node operation by pre-computing unique GUIDs and ports
            unique_guid_port_pairs = self.df[['NodeGUID', 'PortNumber']].drop_duplicates()
            
            # Check DataFrame size and warn if it's very large
            if len(self.df) > 10000:
                print(f"Warning: Processing large DataFrame with {len(self.df)} rows. This may take some time...")
            
            # Pre-compute node and connection lookups
            node_cache = {}
            connection_cache = {}
            
            print(f"Pre-computing lookups for {len(unique_guid_port_pairs)} unique GUID-port pairs...")
            
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
            
            # Use timeout mechanism for the apply operation
            try:
                from .utils import apply_with_timeout
                _series = apply_with_timeout(self.df, optimized_infere_node, axis=1)
                inferred_df = _series.apply(pd.Series)
                expected_headers = INFERRED_HEADERS
                if inferred_df.shape[1] != len(expected_headers):
                    inferred_df = pd.DataFrame(
                        [[None] * len(expected_headers)] * len(self.df),
                        index=self.df.index,
                        columns=expected_headers,
                    )
                else:
                    inferred_df.columns = expected_headers
                self.df[expected_headers] = inferred_df
            except TimeoutError as e:
                print(f"Warning: {e}. Using fallback method...")
                # Fallback to original method with smaller chunks
                from .utils import apply_with_progress
                _series = apply_with_progress(self.df, optimized_infere_node, axis=1, chunk_size=500)
                inferred_df = _series.apply(pd.Series)
                expected_headers = INFERRED_HEADERS
                if inferred_df.shape[1] != len(expected_headers):
                    inferred_df = pd.DataFrame(
                        [[None] * len(expected_headers)] * len(self.df),
                        index=self.df.index,
                        columns=expected_headers,
                    )
                else:
                    inferred_df.columns = expected_headers
                self.df[expected_headers] = inferred_df
            
            # Merge with the port_table
            port_df = port_m.df.copy()
            port_df = drop_overlapping(port_df, self.df)
            self.df = pd.merge(self.df, port_df, on=IBH_ANOMALY_TBL_KEY, how="left")

            # Merge with the xmit_table
            if xmit_m.is_valid():
                xmit_df = xmit_m.df.copy()
                xmit_df = drop_overlapping(xmit_df, self.df)
                self.df = pd.merge(self.df, xmit_df, on=IBH_ANOMALY_TBL_KEY, how="left")

            # for html
            self.min_temperature, self.max_temperature = self.get_temperatures([0.0, 1])

            self.original_df = self.df.copy()
        except KeyError as exc:
            raise ValueError(f"Error: section for {CableManager.CABLE_NAME} hasn't been found") from exc

    def to_csv(self, csv_filename="cables.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()
        df = df[CableManager.COLUMNS_TO_CSV + extended_columns]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

    def to_pairs_csv(self, csv_filename="cables_pairs.csv"):
        """Export pair-view CSV similar to the screenshot (side-by-side info)."""
        import pandas as pd
        from .hca import HcaManager
        # base with source side
        a = self.df.copy()
        # minimal right-side view constructed by matching target GUID/Port back to a's NodeGUID/PortNumber
        right_cols = ['NodeGUID', 'PortNumber', 'Node Name', 'Vendor', 'ConnectorFW', 'LID', 'LinkDownedCounter']
        b = a[right_cols].copy()
        b.columns = ['NodeGUID_b', 'PortNumber_b', 'NodeDesc2', 'Vendor2', 'Firmware2', 'LID2', 'Link Downed Counter 2']

        merged = a.merge(
            b,
            left_on=['Target GUID', 'Target Port'],
            right_on=['NodeGUID_b', 'PortNumber_b'],
            how='left'
        )

        # Join HCA device/FW info for both sides (if available)
        try:
            hca = HcaManager(ib_dir=self.ib_dir, g=self.g)
            hcols = ['NodeGUID', 'FW', 'HWInfo_DeviceID']
            hdf = hca.df[hcols].drop_duplicates()
            merged = merged.merge(hdf.rename(columns={
                'NodeGUID': 'NodeGUID_src', 'FW': 'Firmware1', 'HWInfo_DeviceID': 'DeviceID1'
            }), left_on='NodeGUID', right_on='NodeGUID_src', how='left')
            merged = merged.merge(hdf.rename(columns={
                'NodeGUID': 'NodeGUID_tgt', 'FW': 'Firmware2_h', 'HWInfo_DeviceID': 'DeviceID2'
            }), left_on='Target GUID', right_on='NodeGUID_tgt', how='left')
            # prefer cable firmware if exists; fallback to HCA FW
            merged['Firmware1'] = merged['Firmware1'].fillna(merged.get('ConnectorFW'))
            merged['Firmware2'] = merged['Firmware2'].fillna(merged.get('Firmware2_h'))
        except Exception:
            # fallback: use available columns only
            merged['DeviceID1'] = pd.NA
            merged['DeviceID2'] = pd.NA
            merged['Firmware1'] = merged.get('ConnectorFW')
            # Firmware2 was already filled from right side earlier

        # Build final columns
        merged['NodeDesc1'] = merged['Node Name']
        merged['PortNum1'] = merged['PortNumber']
        merged['LID1'] = merged.get('LID')
        merged['Link Downed Counter 1'] = merged.get('LinkDownedCounter')
        merged['Vendor1'] = merged.get('Vendor')

        out_cols = [
            'NodeDesc1', 'PortNum1', 'DeviceID1', 'Firmware1', 'LID1', 'Link Downed Counter 1', 'Vendor1',
            'NodeDesc2', 'PortNumber_b', 'DeviceID2', 'Firmware2', 'LID2', 'Link Downed Counter 2', 'Vendor2'
        ]
        # Rename PortNumber_b to PortNum2 for readability
        merged.rename(columns={'PortNumber_b': 'PortNum2'}, inplace=True)
        out_cols[8] = 'PortNum2'

        out_df = merged[[c for c in out_cols if c in merged.columns]].copy()
        out_df.to_csv(csv_filename, index=False)
        return [csv_filename]

    @staticmethod
    def temperature_stoi(row):
        temperature_str = row['Temperature']
        match = re.search(r'"([^"]*)"', temperature_str)
        if match:
            temperature_str = match.group(1)

        if temperature_str[-1] == 'C':
            return int(temperature_str[:-1])
        
        # Handle missing or invalid data
        if temperature_str in ["NA", "", None]:
            return pd.NA

        return int(temperature_str)

    def table(self, num_lines=50, sort=0, extended_columns=None):
        print_table, columns = process_extended_column(CableManager.COLUMNS_TO_PRINT, extended_columns, self.df)
        if not print_table:
            return [columns]

        df = self.df.copy()

        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def print_overview(self, extended_columns=None):
        if not extended_columns:
            extended_columns = []

        df = self.df.copy()
        plots = []
        report_sections = [
            ('Vendor', 'vendor'),
            ('TypeDesc', 'type')
        ] + [(col, col) for col in extended_columns]

        for col, txt in report_sections:
            plot = print_aggregate(df, col, title=f"Overview | how many cables for each {_t(txt)}")
            plots.append("") # add space among plots
            plots.append(plot)

        report_sections = [
            ('LinkSpeedEn', 'Node Inferred Type', 'Link Speed'),
            ('PortState', 'Node Inferred Type', 'Port State'),
            ('VLCap', 'Node Inferred Type', 'VLCap'),
            ('Node Inferred Type', 'ConnectorFW', 'revision against node')
        ]

        for col1, col2, txt in report_sections:
            plot = print_aggregate_two(df, col1, col2, title=f"Overview | how many cable for each {_t(txt)}")
            plots.append("") # add space among plots
            plots.append(plot)

        return plots

    def  all_possible_redflags(self):
        return [f'{str(AnomlyType.IBH_RED_FLAG)} {col}' for col in CableManager.IMPORTANT_ANOMALY_COLUMNS]


    def get_anomalies(self):
        df_is_red_flag = get_red_flags_anomalies(self.df.copy(), CableManager.IMPORTANT_ANOMALY_COLUMNS)
        df_outlier = get_outlier_anomalies(self.df.copy(), CableManager.COLUMNS_TO_CHECK)

        # Temperature-based anomaly: Optical Module Temperature High (> 70 C)
        temp_df = self.df[[IBH_ANOMALY_TBL_KEY[0], IBH_ANOMALY_TBL_KEY[1], 'Temperature (c)']].copy()
        # Coerce to numeric and compute weight (degrees above threshold)
        temp_df['Temperature (c)'] = pd.to_numeric(temp_df['Temperature (c)'], errors='coerce')
        label = f"{IBH_ANOMALY_AGG_COL} Optical Module Temperature High"
        threshold = 70.0
        # label as anomaly when temperature >= 70 C; ensure a positive weight even at exactly 70
        def _temp_weight(x):
            if pd.isnull(x):
                return 0.0
            x = float(x)
            if x >= threshold:
                return max(0.1, x - threshold)
            return 0.0
        temp_df[label] = temp_df['Temperature (c)'].apply(_temp_weight)
        # Keep only required columns
        df_temp_anom = temp_df[IBH_ANOMALY_TBL_KEY + [label]]

        df_anomalies = merge_anomalies(self.df, [df_outlier, df_is_red_flag, df_temp_anom])
        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        df_anomalies = self.get_anomalies()

        if not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        print_table, columns = process_extended_column(CableManager.COLUMNS_TO_PRINT_ANOMALY, extended_columns, self.df)
        # print(print_table, columns)
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

    def get_temperatures(self, percentiles):
        return self.df['Temperature (c)'].quantile(percentiles)

    def get_fw_and_more(self, guid, port):
        """
        used by graph.py to put color on the topology based on temperature
        """
        df = self.df
        guid = hex(int(guid, 16))
        condition = ((df['NodeGUID'] == guid) & (df['PortNumber'] == int(port)))
        matching_row = df[condition]
        if matching_row.shape[0] > 0:
            return (matching_row.iloc[0]['Temperature (c)'], matching_row.iloc[0]['ConnectorFW'])
        return (None, None)

    def configure_html_edge(self, group, net, u, v, phy, **kwargs):
        colors = plt.get_cmap('turbo')

        # among two switches, we may have multiple cables. 
        # we only care about one of them at this time.
        guid = group['Source GUID'].min()
        port = group['Source Port'].min()

        temperature, fw = self.get_fw_and_more(guid, port)

        if temperature:
            label = str(temperature)
            title = f"FW: {fw}"

            if not net.add_edge(
                source=u,
                to=v,
                physics=phy,
                label=label,
                title=title,
                color="#000000",
                width=1
            ):
                # duplicated edge!
                opt = net.get_edge(v, u).options
                opt['title'] = f"{opt['title']}\n{title}"
                _max = max(int(opt['label']), temperature)
                normalized = (_max - self.min_temperature) / (self.max_temperature - self.min_temperature)
                color = colors(normalized)
                hex_color = '#%02x%02x%02x' % (
                    int(color[0] * 255),
                    int(color[1] * 255),
                    int(color[2] * 255)
                )

                opt['label'] = f"{_max} C"
                opt['color'] = hex_color

    def print_plot(self, extended_columns=None):
        if not extended_columns:
            extended_columns = ['xmit-data', 'Temperature (c)']
        return xy_scatter_plot(self.df, extended_columns)