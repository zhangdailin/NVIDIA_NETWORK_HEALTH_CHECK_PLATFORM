"""
NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
property and proprietary rights in and to this material, related
documentation and any modifications thereto. Any use, reproduction,
disclosure or distribution of this material and related documentation
without an express license agreement from NVIDIA CORPORATION or
its affiliates is strictly prohibited.
"""

import os
import math
import pandas as pd
from tabulate import tabulate

from .utils import (
    _t, remove_redundant_zero,
    print_aggregate,
    infere_node,
    INFERRED_HEADERS,
    process_extended_column,
    xy_scatter_plot
)
from .dbcsv import read_index_table, read_table
from .net_dump_parser import NetDumpExtParser
from .msg import MSG
from .duration import extract_duration
from .anomaly import (
    IBH_ANOMALY_AGG_WEIGHT,
    get_high_ber_anomalies,
    merge_anomalies,
    IBH_ANOMALY_AGG_COL,
    print_no_anomaly_detected,
    get_unusual_ber_anomalies,
    contains_anomalies
)


class Ber:
    BER_NAME = "PHY_DB16"
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'PortNumber',
        'Node Name', 'Node Inferred Type',
        'Attached To', 'Raw BER',
        'Effective BER', 'Symbol BER'
    ]
    COLUMNS_TO_PRINT_ANOMALY = [
        'Index', 'NodeGUID', 'PortNumber',
        'Node Name', 'Attached To', 'Raw BER',
        'Effective BER', 'Symbol BER',
        IBH_ANOMALY_AGG_COL
    ]
    COLUMNS_TO_CSV = [
        'NodeGUID', 'PortNumber', 'Node Name',
        'Node Inferred Type', 'Attached To',
        'Raw BER', 'Effective BER', 'Symbol BER'
    ]
    BER_COLS = ['Raw BER', 'Effective BER', 'Symbol BER']

    def __init__(self, ib_dir, g, use_net_dump_ext=True):
        self.g = g
        self.ib_dir = ib_dir
        self.use_net_dump_ext = use_net_dump_ext
        
        # Try to use net_dump_ext file first if available and requested
        if use_net_dump_ext:
            try:
                self.df = self._load_from_net_dump_ext()
                self.data_source = "net_dump_ext"
                print(f"Successfully loaded BER data from net_dump_ext file ({len(self.df)} records)")
            except Exception as e:
                print(f"Failed to load from net_dump_ext: {e}")
                print("Falling back to db_csv method...")
                self.df = self._load_from_db_csv()
                self.data_source = "db_csv"
        else:
            self.df = self._load_from_db_csv()
            self.data_source = "db_csv"
            
        if self.df.shape[0] == 0:
            raise ValueError(f"Error: No BER data found in {ib_dir}")
        
        self.duration = extract_duration() # is needed for the filter
        
        # Post-process the DataFrame regardless of source
        self._post_process_dataframe()
        self.original_df = self.df.copy()
    
    def _load_from_net_dump_ext(self):
        """Load BER data from net_dump_ext file"""
        parser = NetDumpExtParser(self.ib_dir)
        df = parser.parse_ber_data()
        
        if df.empty:
            raise ValueError("No BER data found in net_dump_ext file")
            
        # Ensure required columns exist
        required_cols = ['NodeGUID', 'PortNumber', 'Raw BER', 'Effective BER', 'Symbol BER']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in net_dump_ext data")
                
        return df
    
    def _load_from_db_csv(self):
        """Load BER data from db_csv file (original method)"""
        file = [f for f in os.listdir(self.ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(self.ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)

        try:
            df = read_table(file_name, Ber.BER_NAME, indexced_table)
            if df.shape[0] == 0:
                raise ValueError(f"Error: section {Ber.BER_NAME} in ibdiagnet.db_csv is empty!")
                
            df.rename(columns={'NodeGuid': 'NodeGUID', 'PortNum': 'PortNumber', 'PortGuid': 'PortGUID'}, inplace=True)
            df['NodeGUID'] = df.apply(remove_redundant_zero, axis=1)

            # Process mantissa/exponent fields for db_csv data
            self._process_mantissa_exponent_fields(df)
            
            # Calculate BER values from fields
            out_mode = os.environ.get('IBA_BER_OUTPUT', 'sci').lower()
            df[Ber.BER_COLS] = df.apply(
                lambda row: pd.Series(Ber.calculate_ber(row, out_mode)), axis=1
            )
            
            return df
            
        except KeyError as exc:
            raise ValueError(f"Error: section for {Ber.BER_NAME} hasn't been found") from exc
    
    def _process_mantissa_exponent_fields(self, df):
        """Process mantissa/exponent fields for db_csv data"""
        # Expose raw mantissa/exponent pairs as explicit columns (no formatting)
        for (m_col, e_col, out_m, out_e) in [
            ('field12','field13','Raw Mantissa','Raw Exponent'),
            ('field14','field15','Eff Mantissa','Eff Exponent'),
            ('field16','field17','Sym Mantissa','Sym Exponent'),
        ]:
            try:
                df[out_m] = df[m_col].astype(int)
            except Exception:
                df[out_m] = df[m_col]
            try:
                df[out_e] = df[e_col].astype(int)
            except Exception:
                df[out_e] = df[e_col]
    
    def _post_process_dataframe(self):
        """Post-process DataFrame regardless of data source"""
        # Ensure NodeGUID format is consistent
        if 'NodeGUID' in self.df.columns:
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)

        # For net_dump_ext data, we need to create Log10 columns
        if self.data_source == "net_dump_ext":
            for col in Ber.BER_COLS:
                self.df[f'Log10 {col}'] = self.df.apply(lambda row: pd.Series(Ber.log10(row, col)), axis=1)
        
        # For db_csv data, handle the existing processing
        elif self.data_source == "db_csv":
            out_mode = os.environ.get('IBA_BER_OUTPUT', 'sci').lower()
            if out_mode == 'log10':
                # Columns already hold log10 values; mirror to Log10 columns without re-log
                for col in Ber.BER_COLS:
                    self.df[f'Log10 {col}'] = pd.to_numeric(self.df[col], errors='coerce').fillna(0.0)
            else:
                for col in Ber.BER_COLS:
                    self.df[f'Log10 {col}'] = self.df.apply(lambda row: pd.Series(Ber.log10(row, col)), axis=1)
        
        # Add node inference information
        self._add_node_inference()

        # Merge PM counters if available
        self._merge_pm_counters()
        self._annotate_symbol_ber()

    def _annotate_symbol_ber(self):
        """Enrich Symbol BER with log10/severity metadata."""
        if 'Log10 Symbol BER' not in self.df.columns:
            return

        log_series = pd.to_numeric(self.df['Log10 Symbol BER'], errors='coerce')
        self.df['SymbolBERLog10Value'] = log_series

        def to_value(log_value):
            if pd.isna(log_value):
                return None
            return math.pow(10, log_value)

        self.df['SymbolBERValue'] = log_series.apply(to_value)
        threshold_log = math.log10(1e-12)
        warning_log = math.log10(1e-15)

        def classify(log_value):
            if pd.isna(log_value):
                return "unknown"
            if log_value > threshold_log:
                return "critical"
            if log_value > warning_log:
                return "warning"
            return "normal"

        self.df['SymbolBERSeverity'] = log_series.apply(classify)
        self.df['SymbolBERThreshold'] = 1e-12
    
    def _add_node_inference(self):
        """Add node inference information to the DataFrame"""
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
                node_cache[guid] = self.g.get_node(guid)
            
            # Cache connection lookup
            cache_key = (guid, port)
            if cache_key not in connection_cache:
                connection_cache[cache_key] = self.g.get_connection(guid, port)
        
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
            inferred_df = pd.DataFrame(
                [[None] * len(expected_headers)] * len(self.df),
                index=self.df.index,
                columns=expected_headers,
            )
        else:
            inferred_df.columns = expected_headers
        self.df[expected_headers] = inferred_df
    
    def _merge_pm_counters(self):
        """Merge PM counters if available"""
        # Merge useful PM counters (fallback anomaly signals) if available via graph
        try:
            pminfo = getattr(self.g, 'pminfo_m', None)
            if pminfo is not None and hasattr(pminfo, 'df'):
                pm_df = pminfo.df.copy()
                pm_key = ['NodeGUID', 'PortNumber']
                fallback_cols = [
                    'SymbolErrorCounter', 'SymbolErrorCounterExt', 'SyncHeaderErrorCounter',
                    'PortRcvErrors', 'PortRcvRemotePhysicalErrors', 'UnknownBlockCounter'
                ]
                available_cols = [c for c in fallback_cols if c in pm_df.columns.tolist()]
                pm_df = pm_df[pm_key + available_cols].drop_duplicates(subset=pm_key, keep='last')
                self.df = pd.merge(self.df, pm_df, on=pm_key, how='left')
        except Exception:
            # non-fatal: continue without PM merge
            pass

    @staticmethod
    def log10(row, col):
        try:
            val = float(row[col])
            if val == 0.0:
                # define log10(0) as a very small negative number for ranking/sorting
                return -50.0
            return math.log10(val)
        except ValueError:
            return 0.0

    @staticmethod
    def calculate_ber(row, out_mode='sci'):
        field12 = int(row['field12'])
        field13 = int(row['field13'])
        field14 = int(row['field14'])
        field15 = int(row['field15'])
        field16 = int(row['field16'])
        field17 = int(row['field17'])

        def to_sci_from_log10(value_log10):
            if value_log10 is None:
                return 'NA'
            exponent = int(math.floor(value_log10))
            mantissa = 10 ** (value_log10 - exponent)
            return f"{mantissa:.1f}e{exponent:+03d}"

        def to_strict_from_me(mantissa_val, exponent_val):
            # no rounding; raw mantissa/exponent stitched
            return f"{mantissa_val}e-{int(exponent_val)}" if mantissa_val != 0 else "0e+00"

        # Compute real BER values and their log10
        def me_to_log10(m, e):
            try:
                m = int(m)
                e = int(e)
                if m == 0:
                    return None  # represent exact zero
                return math.log10(abs(m)) - e
            except Exception:
                return None

        raw_log10 = me_to_log10(field12, field13)
        eff_log10 = me_to_log10(field14, field15)
        sym_log10 = me_to_log10(field16, field17)

        if out_mode == 'log10':
            # emit numeric log10 values; for exact zero use a very small negative for readability
            raw_out = raw_log10 if raw_log10 is not None else -50.0 if int(field12) == 0 else 'NA'
            eff_out = eff_log10 if eff_log10 is not None else -50.0 if int(field14) == 0 else 'NA'
            sym_out = sym_log10 if sym_log10 is not None else -50.0 if int(field16) == 0 else 'NA'
            return (raw_out, eff_out, sym_out)

        # strict mode: return raw mantissa/exponent without rounding
        if out_mode in ['strict', 'raw']:
            return (
                to_strict_from_me(field12, field13),
                to_strict_from_me(field14, field15),
                to_strict_from_me(field16, field17)
            )

        # Default: scientific notation strings with 1 decimal mantissa
        raw_ber = to_sci_from_log10(raw_log10) if raw_log10 is not None or int(field12) == 0 else 'NA'
        eff_ber = to_sci_from_log10(eff_log10) if eff_log10 is not None or int(field14) == 0 else 'NA'
        sym_ber = to_sci_from_log10(sym_log10) if sym_log10 is not None or int(field16) == 0 else 'NA'
        # For exact zeros, force string to 0e+00
        if int(field12) == 0:
            raw_ber = '0e+00'
        if int(field14) == 0:
            eff_ber = '0e+00'
        if int(field16) == 0:
            sym_ber = '0e+00'
        return (raw_ber, eff_ber, sym_ber)

    @staticmethod
    def calc_rank(row):
        return sum(float(row[f'Log10 {x}']) for x in Ber.BER_COLS)

    def to_csv(self, csv_filename="ber.csv", extended_columns=None):
        if not extended_columns:
            extended_columns = []

        df = self.df.copy()
        # Only keep extended columns that actually exist to avoid KeyError
        safe_extended = [c for c in extended_columns if c in df.columns.tolist()]
        df = df[Ber.COLUMNS_TO_CSV + safe_extended]
        df.to_csv(csv_filename, index=False)
        return [csv_filename]

    def table(self, num_lines=50, sort=0, extended_columns=None):
        print_table, columns = process_extended_column(Ber.COLUMNS_TO_PRINT, extended_columns, self.df)
        if not print_table:
            return [columns]

        df = self.df.copy()
        columns = Ber.COLUMNS_TO_PRINT + extended_columns

        df['ibh_ber_ranking'] = df.apply(lambda row: pd.Series(Ber.calc_rank(row)), axis=1)

        if abs(sort) > 0:
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        if sort == 0:
            df = df.sort_values(by='ibh_ber_ranking', ascending=False)

        df['Index'] = range(1, len(df) + 1)  # should be after sort
        df = df[columns]

        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def get_anomalies(self):
        df_high_ber = get_high_ber_anomalies(self.df.copy())
        df_unusual_ber = get_unusual_ber_anomalies(self.df.copy())
        df_anomalies = merge_anomalies(self.df, [df_high_ber, df_unusual_ber])

        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        """
        Main execution point from iba
        """
        df_anomalies = self.get_anomalies()

        # Only keep rows that actually have anomalies
        try:
            from .anomaly import IBH_ANOMALY_AGG_COL
            df_anomalies = df_anomalies[
                df_anomalies[IBH_ANOMALY_AGG_COL].notna() & (df_anomalies[IBH_ANOMALY_AGG_COL] != '')
            ]
        except Exception:
            pass

        if df_anomalies.empty or not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        print_table, columns = process_extended_column(Ber.COLUMNS_TO_PRINT_ANOMALY, extended_columns, self.df)
        if not print_table:
            return[columns]

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

    def print_overview(self, extended_columns=None):
        if extended_columns:
            return [MSG[0]]

        plots = []
        df = self.df.copy()
        for col in Ber.BER_COLS:
            log_col = f'SciLog {col}'
            df[log_col] = df.apply(lambda row: f"10^{int(float(row[f'Log10 {col}']))}", axis=1)
            title = f"Overview | #links with a certain order of magnitude {_t(col)}"
            plot = print_aggregate(df, log_col, title=title)
            plots.append(plot)

        return plots

    def print_plot(self, extended_columns=None):
        return xy_scatter_plot(self.df, extended_columns)
