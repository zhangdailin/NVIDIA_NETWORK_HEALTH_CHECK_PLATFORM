import os
import pandas as pd
from tabulate import tabulate

from .dbcsv import read_index_table, read_table
from .stats_utils import similar_columns
from .utils import (
    _t, remove_redundant_zero, infere_node, print_aggregate, INFERRED_HEADERS,
    convert_any_to_decimal, partition_df, xy_scatter_plot
)
from .utils import process_extended_column
from .duration import extract_duration
from .anomaly import IBH_ANOMALY_TOP_COLUMNS



class PMInfo:
    PMINFO_NAME = "PM_INFO"
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber', 'Node Inferred Type', 'Attached To'
    ]
    COLUMNS_TO_PRINT_COMPARE = ['Index', 'PortNumber', 'NodeGUID', 'Node Name']
    COLUMNS_TO_CSV = ['NodeGUID', 'Node Name', 'PortNumber', 'Node Inferred Type', 'Attached To']

    def __init__(self, ib_dir, g, hca_m, ib_pm):
        self.g = g

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)
        hca_df = hca_m.df.copy()

        try:
            self.df = read_table(file_name, PMInfo.PMINFO_NAME, indexced_table)
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)
            self.duration = extract_duration(file_name)

            # xmit-data and xmit-wait information from PM_INFO
            self.df['PortXmitWaitTotal'] = self.df['PortXmitWaitExt']
            self.df['PortXmitDataTotal'] = self.df['PortXmitDataExtended'] + self.df['PortXmitData']

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
            if inferred_df.shape[1] != len(expected_headers) or inferred_df.shape[1] == 0:
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
            self.df = pd.merge(self.df, ib_pm.df, on=['NodeGUID', 'PortNumber'], how='left').copy()

            self.original_df = self.df.copy()
        except KeyError as exc:
            raise ValueError(f"Error: section for {PMInfo.PMINFO_NAME} hasn't been found") from exc

    def table(self, num_lines=50, sort=0, extended_columns=None, similar=None):
        print_table, columns = process_extended_column(PMInfo.COLUMNS_TO_PRINT, extended_columns, self.df)
        if not print_table:
            return [columns]

        df = self.df.copy()
        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        if similar:
            cols = similar_columns(self.df, similar)
            for col in cols:
                columns.append(col)

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)

        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def print_overview(self, extended_columns=None):
        df = self.df.copy()

        if not extended_columns:
            extended_columns = []

        columns = IBH_ANOMALY_TOP_COLUMNS +  extended_columns

        plots = []
        all_columns = df.columns.tolist()
        max_int64 = 2**63 - 1
        for col in columns:
            if not col in all_columns:
                continue
            num_unique = df[col].nunique()
            if num_unique == 1:
                continue

            unique_vals = df[col].unique().tolist()
            unique_vals = [convert_any_to_decimal(u) for u in unique_vals if u != "NA"]

            if len(unique_vals) < 2 or set(unique_vals) == set([0, -1]):
                continue

            if len(unique_vals) < 10:
                if set(df[col].unique().tolist()) == set([0, -1]):
                    continue
                plot = print_aggregate(df, col, title=f"Overview | PM Info for {_t(col)}")
                plots.append(plot)
            else:
                headers = [(col, max(1, int(abs(df[col].max() - df[col].min()) / 10)))]
                sorting_col = f'ibh_histogram_values_{col}'
                expanded = df.apply(lambda row: pd.Series(partition_df(row, headers)), axis=1)
                if expanded.shape[1] == 2:
                    expanded.columns = [col, sorting_col]
                else:
                    expanded.columns = [f"{col}_bucket", f"{sorting_col}_tmp"]
                df[col] = expanded[col].values
                # sorting_col might not exist if shape mismatch; guard
                if sorting_col in expanded.columns:
                    df[sorting_col] = expanded[sorting_col].values

                df.loc[df[sorting_col] > max_int64, sorting_col] = max_int64 # drop values large than 2^64
                df[sorting_col] = df[sorting_col].astype('int64')

                plot = print_aggregate(df, col, title=f"Overview | how many node for {_t(col)}", sorting_col=sorting_col)
                plots.append(plot)

        return plots

    def to_csv(self, csv_filename="pminfo.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []
        df = self.df.copy()
        df = df[PMInfo.COLUMNS_TO_CSV + extended_columns]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

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
        print_table, columns = process_extended_column(PMInfo.COLUMNS_TO_PRINT_COMPARE, extended_columns, self.df)
        if not print_table:
            return [columns]

        df_a = self.df.copy()
        df_b = other.df.copy()


        df = pd.merge(df_a, df_b, on=['PortNumber', 'NodeGUID', 'Node Name'], how='inner')
        if df.shape[0] == 0:
            raise ValueError("The two ibdiganet directory have nothing in common!")

        # Add extended columns
        for col in extended_columns:
            old_a, new_a = f"{col}_x", f"{col}_A"
            old_b, new_b = f"{col}_y", f"{col}_B"

            df.rename(columns={old_a: new_a, old_b: new_b}, inplace=True)
            columns.append(new_a)
            columns.append(new_b)
            columns.remove(col)

        if abs(sort) > 0:  # column index
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def print_plot(self, extended_columns=None):
        return xy_scatter_plot(self.df, extended_columns)
