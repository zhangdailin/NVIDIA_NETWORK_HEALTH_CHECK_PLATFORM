import os
from datetime import timedelta
from tabulate import tabulate
import pandas as pd

from .utils import _t, print_aggregate, print_aggregate_two, remove_redundant_zero
from .utils import process_extended_column, xy_scatter_plot
from .utils import INFERRED_HEADERS, infere_node
from .const import SWITCH_DICT, HCA_DICT, NVLINK_DICT
from .dbcsv import read_index_table, read_table
from .duration import extract_duration
from .anomaly import (
    get_outlier_anomalies,
    merge_anomalies,
    contains_anomalies,
    print_no_anomaly_detected,
    IBH_ANOMALY_AGG_WEIGHT,
    IBH_ANOMALY_AGG_COL,
    drop_overlapping
)


class HcaManager:
    HCA_NAME = "NODES_INFO"
    COLUMNS_TO_PRINT = [
        'Index',
        'NodeGUID',
        'Name',
        'Node Inferred Type',
        'Device Type',
        'FW', 'FW Date',
        'FWInfo_PSID',
        'Up Time'
    ]
    COLUMNS_TO_CSV = ['NodeGUID', 'Name', 'Device Type', 'FW', 'FW Date', 'FWInfo_PSID', 'Up Time']
    COLUMNS_TO_CHECK = ['FW', 'FWInfo_PSID']

    def __init__(self, ib_dir, g):
        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)
        self.g = g
        self.duration = extract_duration() # is needed for the filter

        try:
            self.df = read_table(file_name, HcaManager.HCA_NAME, indexced_table)
        except KeyError as exc:
            raise ValueError(f"Error: section for {HcaManager.HCA_NAME} hasn't been found") from exc

        self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)
        self.df['Device Type'] = self.df.apply(HcaManager.device_type, axis=1)
        self.df['LID'] = self.df.apply(lambda row: pd.Series(HcaManager.device_lid(row, g)), axis=1)

        self.df['FW Date'] = (
            self.df['FWInfo_Year'].astype(str).str[2:] + "/" +
            self.df['FWInfo_Month'].astype(str).str[2:] + "/" +
            self.df['FWInfo_Day'].astype(str).str[2:]
        )

        self.df['FWInfo_Extended_Major'] = self.df['FWInfo_Extended_Major'].apply(lambda x: int(x, 16))
        self.df['FWInfo_Extended_Minor'] = self.df['FWInfo_Extended_Minor'].apply(lambda x: int(x, 16))
        self.df['FWInfo_Extended_SubMinor'] = self.df['FWInfo_Extended_SubMinor'].apply(lambda x: int(x, 16))
        self.df['Up Time'] = self.df['HWInfo_UpTime'].apply(lambda x: str(timedelta(seconds=int(x, 16))))
        self.df['Name'] = self.df['NodeGUID'].apply(lambda x: g.get_node(x).name())

        self.df['FW'] = (
            self.df['FWInfo_Extended_Major'].astype(str) + "." +
            self.df['FWInfo_Extended_Minor'].astype(str) + "." +
            self.df['FWInfo_Extended_SubMinor'].astype(str).str.zfill(4)
        )

        # Optimize the infere_node operation by pre-computing unique GUIDs
        unique_guids = self.df['NodeGUID'].drop_duplicates()
        
        # Pre-compute node lookups
        node_cache = {}
        for guid in unique_guids:
            node_cache[str(guid)] = g.get_node(str(guid))
        
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
                
                peer = g.get_connection(guid, port)
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
        
        # Expand tuple results into a DataFrame to match INFERRED_HEADERS length
        inferred_series = self.df.apply(optimized_infere_node, axis=1)
        inferred_df = inferred_series.apply(pd.Series)
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

        self.original_df = self.df.copy()

    @staticmethod
    def device_lid(row, g):
        guid = str(row['NodeGUID'])
        if node := g.get_node(guid):
            return str(node.lid)
        return "NA"

    @staticmethod
    def device_type(row):
        dev_id = str(row['HWInfo_DeviceID'])
        if dev_id in HCA_DICT:
            return HCA_DICT[dev_id]
        if dev_id in SWITCH_DICT:
            return SWITCH_DICT[dev_id]
        if dev_id in NVLINK_DICT:
            return NVLINK_DICT[dev_id]
        return dev_id

    def table(self, num_lines=50, sort=0, extended_columns=None):
        print_table, columns = process_extended_column(HcaManager.COLUMNS_TO_PRINT, extended_columns, self.df)
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

    def to_csv(self, csv_filename="hca.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()
        df = df[HcaManager.COLUMNS_TO_CSV + extended_columns]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

    def get_anomalies(self):
        _, edges = self.g.to_dataframe()
        edges.rename(columns={'Source Port': 'PortNumber'}, inplace=True)

        df_copy = drop_overlapping(self.df.copy(), edges)
        df = edges.merge(
            df_copy,
            how='left',
            left_on=['Source GUID'],
            right_on=['NodeGUID'],
        ).dropna(subset=['NodeGUID'])
        df = df[~df['Name'].str.contains("ufm")]

        df_hca_outlier = get_outlier_anomalies(df[df['Node Inferred Type'] == 'HCA'].copy(), HcaManager.COLUMNS_TO_CHECK, th=.05)
        df_sw_outlier = get_outlier_anomalies(df[df['Simple Type'] == 'SW'].copy(), HcaManager.COLUMNS_TO_CHECK, th=.2)

        df_anomalies = merge_anomalies(df, [df_hca_outlier, df_sw_outlier])
        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        """
        Main execution point from ib_analysis
        """
        df_anomalies = self.get_anomalies()

        if not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        columns = HcaManager.COLUMNS_TO_PRINT + [IBH_ANOMALY_AGG_COL]
        print_table, columns = process_extended_column(columns, extended_columns, self.df)
        if not print_table:
            return[columns]

        # Print Anomalies #
        if sort == 0:
            df_anomalies = df_anomalies.sort_values(by=[IBH_ANOMALY_AGG_WEIGHT, 'NodeGUID'], ascending=False)
        elif abs(sort) > 0:
            df_anomalies = df_anomalies.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        df_anomalies['Index'] = range(1, df_anomalies.shape[0] + 1)  # should be after sort
        df_anomalies = df_anomalies[columns]
        if num_lines > 0:
            df_anomalies = df_anomalies.head(num_lines)

        return [tabulate(df_anomalies, headers='keys', tablefmt='pretty', showindex=False)]

    def print_overview(self, extended_columns=None):
        if not extended_columns:
            extended_columns = []
        
        df = self.df.copy()

        report_sections = [
            ('Device Type', 'FW', 'device model and their FW'),
            ('FWInfo_PSID', 'Node Inferred Type', 'device type and their PSID'),
            ('FW', 'Node Inferred Type', 'device type and their FW'),
        ]

        plots = []
        for col1, col2, txt in report_sections:
            plot = print_aggregate_two(df, col1, col2, title=f"Overview | histogram for {_t(txt)}")
            plots.append(plot)

        for col in extended_columns:
            plot = print_aggregate(df, col, title=f"Overview | how many HCA for each {_t(col)}")
            plots.append(plot)

        return plots

    def print_plot(self, extended_columns=None):
        return xy_scatter_plot(self.df, extended_columns)