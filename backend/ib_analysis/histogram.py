import os
import pandas as pd
from tabulate import tabulate
import plotext as plt

from .utils import (
    infere_node, remove_redundant_zero,
    INFERRED_HEADERS, process_extended_column
)
from .dbcsv import read_index_table, read_table
from .msg import MSG
from .duration import extract_duration

class Histogram:
    TABLE_NAME = "PERFORMANCE_HISTOGRAM_BUFFER_DATA"
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'PortNumber',
        'Node Name', 'bin[0]', 'pbin[0]'
    ]
    COLUMNS_TO_CSV = [
        'NodeGUID', 'PortNumber','Node Name'
    ] + [f'bin[{i}]' for i in list(range(0,10))] + [f'pbin[{i}]' for i in list(range(0,10))]

    def __init__(self, ib_dir, g, xmit):
        self.g = g
        self.xmit_m = xmit

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)

        try:
            self.duration = extract_duration() # is needed for the filter
            self.df = read_table(file_name, Histogram.TABLE_NAME, indexced_table)
            if self.df.shape[0] == 0:
                raise ValueError(
                    f"Error: section {Histogram.TABLE_NAME} in ibdiagnet.db_csv is empty!"
                )
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)

            bin_columns = [col for col in self.df.columns if col.startswith('bin[')]
            self.df['sum_bins'] = self.df[bin_columns].sum(axis=1)
            for col in bin_columns:
                self.df[f'p{col}'] = self.df[col].div(self.df['sum_bins'], fill_value=0)

            self.df = flatten_vls(self.df)

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
            
            # Expand tuple results into a DataFrame to match INFERRED_HEADERS
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
        except KeyError as exc:
            raise ValueError(f"Error: section for {Histogram.TABLE_NAME} hasn't been found") from exc

    def table(self, num_lines=50, sort=0, extended_columns=None):
        print_table, columns = process_extended_column(
            Histogram.COLUMNS_TO_PRINT,
            extended_columns,
            self.df
        )
        if not print_table:
            return [columns]

        df = self.df.copy()
        columns = Histogram.COLUMNS_TO_PRINT + extended_columns

        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='psql', showindex=False, floatfmt=".2f")]

    def print_overview(self, extended_columns=None):
        if extended_columns:
            if not extended_columns:
                return [MSG[0]]
        df = self.df.copy()

        # Extract bin numbers from the column names
        bin_columns = [col for col in df.columns if col.startswith('pbin[') and "vl" not in col]
        df[bin_columns] = df[bin_columns] * 100

        grouped = df.groupby(['Node Name']).mean(numeric_only=True)

        plots = []
        # Loop over each Name to plot their average bin values
        for name in grouped.index:
            bin_values = grouped.loc[name, bin_columns]
            x_labels = bin_columns
            plt.simple_bar(x_labels, bin_values, width=100, title=str(name))
            plots.append(plt.build())

        if len(grouped) == 1:
            grouped = df.groupby(['Node Name', 'Attached To']).mean(numeric_only=True)
            for name in grouped.index:
                bin_values = grouped.loc[name, bin_columns]
                x_labels = bin_columns
                plt.simple_bar(x_labels, bin_values, width=100, title=str(name[0] + ' -> ' + name[1]))
                plots.append(plt.build())

        return plots

    def to_csv(self, csv_filename="histogram.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []

        df = self.df.copy()
        df = df[Histogram.COLUMNS_TO_CSV + extended_columns]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

def flatten_vls(df):
    """
    Flatten the table so as we have new columns for each available VL value. 
    """
    df_pivot = df.set_index(['NodeGUID', 'PortNumber', 'PortGUID', 'vl'])

    # Unstack the 'vl' level to pivot it into columns
    df_unstacked = df_pivot.unstack('vl')

    # Flatten the MultiIndex columns and rename them to include keyC values
    if getattr(df_unstacked.columns, "__iter__", None):
        df_unstacked.columns = [
            col[0] if col[1] == 0 else f"{col[0]} vl{col[1]}"
                for col in df_unstacked.columns
        ]

    # Reset the index to turn 'NodeGUID' and 'PortNumber' back into columns
    df_final = df_unstacked.reset_index()

    # Get the list of columns excluding 'NodeGUID' and 'PortNumber'
    data_columns = [col for col in df_final.columns if col not in ['NodeGUID', 'PortNumber', 'PortGUID']]

    # Combine 'NodeGUID', 'PortNumber', and data columns
    desired_columns = ['NodeGUID', 'PortNumber', 'PortGUID'] + data_columns

    df_final = df_final[desired_columns]

    # Now df_final contains the flattened dataframe
    return df_final
