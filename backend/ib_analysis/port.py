import os
import pandas as pd

from .dbcsv import read_index_table, read_table
from .const import PP_STATE_MAPPER
from .utils import remove_redundant_zero
from .utils import INFERRED_HEADERS
from .anomaly import IBH_ANOMALY_TBL_KEY, IBH_ANOMALY_AGG_COL
from .anomaly import merge_anomalies


class Port:
    PORT_NAME = "PORTS"
    COLUMNS_TO_PRINT = [
        'Index', 'NodeGUID', 'PortNumber', 'Node Name',
        'Node Inferred Type', 'Attached To', 'LinkSpeedEn',
        'PortPhyState', 'PortState', 'VLCap'
    ]
    COLUMNS_TO_CSV = [
        'NodeGUID', 'PortNumber', 'Node Name', 'Node Inferred Type',
        'Attached To', 'LinkSpeedEn', 'PortPhyState', 'PortState',
        'VLCap', 'LinkDownedCounter', 'PortRcvErrorsExt',
        'LocalLinkIntegrityErrorsExt', 'PortRcvSwitchRelayErrors',
        'PortXmitConstraintErrors', 'PortRcvConstraintErrors',
        'PortSwLifetimeLimitDiscards', 'PortSwHOQLifetimeLimitDiscards'
    ]
    COLUMNS_TO_PRINT_ANOMALY = [
        'Index', 'NodeGUID', 'PortNumber', 'Node Name', 'Node Inferred Type',
        'Attached To', 'PortState', 'PortPhyState', 'LinkDownedCounter',
        'PortRcvErrorsExt', 'LocalLinkIntegrityErrorsExt', 'PortRcvSwitchRelayErrors',
        'PortXmitConstraintErrors', 'PortRcvConstraintErrors', IBH_ANOMALY_AGG_COL
    ]

    def __init__(self, ib_dir, g, pminfo=None):
        self.g = g
        self.pminfo = pminfo
        self.ib_dir = ib_dir

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".db_csv")][0]
        file_name = os.path.join(ib_dir, file)
        indexced_table = read_index_table(file_name=file_name)

        try:
            self.df = read_table(file_name, Port.PORT_NAME, indexced_table)
            self.df.rename(columns={'NodeGuid': 'NodeGUID', 'PortNum': 'PortNumber', 'PortGuid': 'PortGUID'}, inplace=True)
            self.df['NodeGUID'] = self.df.apply(remove_redundant_zero, axis=1)
            self.df['PortPhyState'] = self.df.apply(Port.decode_port_phy_state, axis=1)
            # Enrich with inferred headers (Node Name / Inferred Type / Attached To ...)
            # Precompute caches to speed up repeated lookups
            unique_pairs = self.df[['NodeGUID', 'PortNumber']].drop_duplicates()
            node_cache = {}
            connection_cache = {}
            for _, row in unique_pairs.iterrows():
                guid = str(row['NodeGUID'])
                port = str(row['PortNumber'])
                if guid not in node_cache:
                    node_cache[guid] = g.get_node(guid)
                key = (guid, port)
                if key not in connection_cache:
                    connection_cache[key] = g.get_connection(guid, port)

            def optimized_infere_node(row):
                guid = str(row.get('NodeGUID', 'NA'))
                port = str(row.get('PortNumber', 'NA'))
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
                        try:
                            port_index = int(port)
                            target_port = node.children[port_index].dstport
                            plain = node.children[port_index].plain
                        except Exception:
                            target_port = "NA"
                        peer_name = peer.name()
                        peer_id = peer.id
                        peer_guid = peer.guid
                        peer_infere_type = peer.infere_type()
                        peer_rack = peer.rack
                return (node_name, node_simple_type, node_infere_type, peer_name, node_id, peer_id,
                        target_port, peer_guid, peer_infere_type, node_lid, plain, rack, peer_rack)

            inferred = self.df.apply(optimized_infere_node, axis=1).apply(pd.Series)
            expected = INFERRED_HEADERS
            if inferred.shape[1] != len(expected):
                inferred = pd.DataFrame([[None]*len(expected)]*len(self.df), index=self.df.index, columns=expected)
            else:
                inferred.columns = expected
            self.df[expected] = inferred
        except KeyError as exc:
            raise ValueError(f"Error: section for {Port.PORT_NAME} hasn't been found") from exc

    @staticmethod
    def decode_port_phy_state(row):
        pp_state = row['PortPhyState']
        if pp_state in PP_STATE_MAPPER:
            return PP_STATE_MAPPER[pp_state]
        return pp_state

    def to_pairs_csv(self, csv_filename="ports_pairs.csv", hide_zero_linkdown: bool = False, filter_nonzero_linkdown: bool = False):
        """Export side-by-side port pairs similar to screenshot.

        Columns: NodeDesc1, PortNum1, DeviceID1, Firmware1, LID1,
                 Link Downed Counter 1, Vendor1, NodeDesc2, PortNum2,
                 DeviceID2, Firmware2, LID2, Link Downed Counter 2, Vendor2
        """
        out_df = self._build_pairs_df()
        if filter_nonzero_linkdown:
            for_pair_cols = ['Link Downed Counter 1', 'Link Downed Counter 2']
            if any(c in out_df.columns for c in for_pair_cols):
                c1 = out_df.get('Link Downed Counter 1', 0)
                c2 = out_df.get('Link Downed Counter 2', 0)
                try:
                    mask = (pd.to_numeric(c1, errors='coerce').fillna(0) > 0) & (pd.to_numeric(c2, errors='coerce').fillna(0) > 0)
                    out_df = out_df[mask]
                except Exception:
                    pass
        if hide_zero_linkdown:
            for col in ['Link Downed Counter 1', 'Link Downed Counter 2']:
                if col in out_df.columns:
                    try:
                        if out_df[col].fillna(0).astype(float).abs().sum() == 0:
                            out_df.drop(columns=[col], inplace=True)
                    except Exception:
                        pass
        out_df.to_csv(csv_filename, index=False)
        return [csv_filename]

    def _build_pairs_df(self):
        from .hca import HcaManager
        df = self.df.copy()
        # Build edges to map peer GUID/port
        _, edges = self.g.to_dataframe()
        left = df.copy()

        # Vendor mapping from graph nodes
        vendor_map = {}
        for guid, node in getattr(self.g, 'nodes', {}).items():
            try:
                vendor_map[guid] = node.vendor()
            except Exception:
                vendor_map[guid] = None
        left['Vendor1'] = left['NodeGUID'].map(vendor_map)

        # Join left with edges to get target side keys
        edges_view = edges[['Source GUID', 'Source Port', 'Target GUID', 'Target Port', 'Target Name']].copy()
        # Normalize dtypes for first join keys
        left['NodeGUID'] = left['NodeGUID'].astype(str)
        left['PortNumber'] = pd.to_numeric(left['PortNumber'], errors='coerce').astype('Int64')
        edges_view['Source GUID'] = edges_view['Source GUID'].astype(str)
        edges_view['Source Port'] = pd.to_numeric(edges_view['Source Port'], errors='coerce').astype('Int64')

        left = left.merge(
            edges_view,
            left_on=['NodeGUID', 'PortNumber'],
            right_on=['Source GUID', 'Source Port'],
            how='left'
        )

        # Fallback: if merge didn't bring target columns, derive via graph on the fly
        if 'Target GUID' not in left.columns or 'Target Port' not in left.columns:
            def _peer_lookup(row):
                try:
                    guid = str(row['NodeGUID'])
                    port = str(row['PortNumber'])
                    node = self.g.get_node(guid)
                    peer = self.g.get_connection(guid, port)
                    tgt_guid = peer.guid if peer else None
                    tgt_name = peer.name() if peer else None
                    try:
                        pidx = int(port)
                        tgt_port = node.children[pidx].dstport if node and pidx in node.children else None
                    except Exception:
                        tgt_port = None
                    return pd.Series({'Target GUID': tgt_guid, 'Target Port': tgt_port, 'Target Name': tgt_name})
                except Exception:
                    return pd.Series({'Target GUID': None, 'Target Port': None, 'Target Name': None})
            derived = left.apply(_peer_lookup, axis=1)
            for c in ['Target GUID', 'Target Port', 'Target Name']:
                if c not in left.columns:
                    left[c] = derived[c]

        # Right side basic info by remapping from df itself (tolerate missing counters)
        right_basic = df[['NodeGUID', 'PortNumber', 'Node Name']].copy()
        right_basic['Link Downed Counter 2'] = df.get(
            'LinkDownedCounter', df.get('LinkDownedCounterExt', pd.Series(0, index=df.index))
        )
        right_basic.columns = ['NodeGUID_r', 'PortNumber_r', 'NodeDesc2', 'Link Downed Counter 2']
        # Ensure dtype match for second join keys
        left['Target Port'] = pd.to_numeric(left['Target Port'], errors='coerce').astype('Int64')
        right_basic['NodeGUID_r'] = right_basic['NodeGUID_r'].astype(str)
        right_basic['PortNumber_r'] = pd.to_numeric(right_basic['PortNumber_r'], errors='coerce').astype('Int64')

        left = left.merge(
            right_basic,
            left_on=['Target GUID', 'Target Port'],
            right_on=['NodeGUID_r', 'PortNumber_r'],
            how='left'
        )

        # Use PM_INFO LinkDownedCounter directly for both sides (no fallback heuristics)
        try:
            if self.pminfo is not None and hasattr(self.pminfo, 'df') and 'LinkDownedCounter' in self.pminfo.df.columns:
                pm_map = self.pminfo.df[['NodeGUID', 'PortNumber', 'LinkDownedCounter']].copy()
                pm_map['NodeGUID'] = pm_map['NodeGUID'].astype(str)
                pm_map['PortNumber'] = pd.to_numeric(pm_map['PortNumber'], errors='coerce').astype('Int64')

                # Left side
                left = left.merge(
                    pm_map.rename(columns={'LinkDownedCounter': 'Link Downed Counter 1'}),
                    on=['NodeGUID', 'PortNumber'], how='left'
                )
                left['Link Downed Counter 1'] = pd.to_numeric(left['Link Downed Counter 1'], errors='coerce').fillna(0).astype(int)

                # Right side (target)
                pm_map_r = pm_map.rename(columns={'NodeGUID': 'NodeGUID_r2', 'PortNumber': 'PortNumber_r2', 'LinkDownedCounter': 'Link Downed Counter 2'})
                left['Target GUID'] = left['Target GUID'].astype(str)
                left['Target Port'] = pd.to_numeric(left['Target Port'], errors='coerce').astype('Int64')
                left = left.merge(
                    pm_map_r,
                    left_on=['Target GUID', 'Target Port'],
                    right_on=['NodeGUID_r2', 'PortNumber_r2'],
                    how='left'
                )
                # Handle possible suffixes after merge; prefer PM column
                ld2_pm = pd.to_numeric(
                    left.get('Link Downed Counter 2_y', left.get('Link Downed Counter 2')),
                    errors='coerce'
                ).fillna(0).astype(int)
                left['Link Downed Counter 2'] = ld2_pm
                # Clean up helper/suffix columns
                for col in ['NodeGUID_r2', 'PortNumber_r2', 'Link Downed Counter 2_x', 'Link Downed Counter 2_y']:
                    if col in left.columns:
                        left.drop(columns=[col], inplace=True)
        except Exception:
            pass

        # Vendor from START_CABLE_INFO (CABLE_INFO) for both sides; override graph vendor when available
        try:
            file = [f for f in os.listdir(self.ib_dir) if str(f).endswith(".db_csv")][0]
            file_name = os.path.join(self.ib_dir, file)
            indexced_table = read_index_table(file_name=file_name)
            cable_df = read_table(file_name, "CABLE_INFO", indexced_table).copy()
            # Remove stray quotes and trim whitespace to avoid "Vendor2 没有改变，去掉 \"\"" issues
            try:
                cable_df = cable_df.replace('"', '', regex=True)
            except Exception:
                pass
            cable_df.rename(columns={'NodeGuid': 'NodeGUID', 'PortNum': 'PortNumber'}, inplace=True)
            cable_df['NodeGUID'] = cable_df.apply(remove_redundant_zero, axis=1)
            vmap = cable_df[['NodeGUID', 'PortNumber', 'Vendor']].drop_duplicates()
            # Normalize Vendor values: strip spaces, convert empty/NA strings to NaN
            if 'Vendor' in vmap.columns:
                try:
                    vmap['Vendor'] = vmap['Vendor'].astype(str).str.strip()
                    vmap['Vendor'] = vmap['Vendor'].replace({'': pd.NA, 'NA': pd.NA, 'None': pd.NA, 'nan': pd.NA})
                except Exception:
                    pass
            vmap['NodeGUID'] = vmap['NodeGUID'].astype(str)
            vmap['PortNumber'] = pd.to_numeric(vmap['PortNumber'], errors='coerce').astype('Int64')
            # Left side vendor
            left = left.merge(
                vmap.rename(columns={'Vendor': 'Vendor1_cable'}),
                on=['NodeGUID', 'PortNumber'], how='left'
            )
            # Clean helper then prefer cable Vendor when present
            if 'Vendor1_cable' in left.columns:
                try:
                    left['Vendor1_cable'] = left['Vendor1_cable'].astype(str).str.strip()
                    left['Vendor1_cable'] = left['Vendor1_cable'].replace({'': pd.NA, 'NA': pd.NA, 'None': pd.NA, 'nan': pd.NA})
                except Exception:
                    pass
            # Keep a verification flag if Vendor1 is sourced from CABLE_INFO
            left['Vendor1 Verified'] = left.get('Vendor1_cable').notna()
            left['Vendor1'] = left.get('Vendor1_cable').combine_first(left.get('Vendor1'))
            # Right side vendor: PREFER mapping using NodeDesc2's GUID/Port (NodeGUID_r/PortNumber_r),
            # then fallback to target keys if needed. This ensures Vendor2 matches NodeDesc2.
            # 1) Preferred join via NodeGUID_r/PortNumber_r
            vmap_r2 = vmap.rename(columns={'NodeGUID': 'NodeGUID_r', 'PortNumber': 'PortNumber_r', 'Vendor': 'Vendor2_cable_r'})
            # Ensure key dtypes
            left['NodeGUID_r'] = left.get('NodeGUID_r').astype(str)
            left['PortNumber_r'] = pd.to_numeric(left.get('PortNumber_r'), errors='coerce').astype('Int64')
            left = left.merge(
                vmap_r2,
                on=['NodeGUID_r', 'PortNumber_r'],
                how='left'
            )
            # 2) Fallback join via Target GUID/Target Port
            vmap_r = vmap.rename(columns={'NodeGUID': 'NodeGUID_vr', 'PortNumber': 'PortNumber_vr', 'Vendor': 'Vendor2_cable'})
            left['Target GUID'] = left['Target GUID'].astype(str)
            left['Target Port'] = pd.to_numeric(left['Target Port'], errors='coerce').astype('Int64')
            left = left.merge(
                vmap_r,
                left_on=['Target GUID', 'Target Port'],
                right_on=['NodeGUID_vr', 'PortNumber_vr'],
                how='left'
            )
            # Clean helper then prefer cable Vendor when present
            for helper in ['Vendor2_cable_r', 'Vendor2_cable']:
                if helper in left.columns:
                    try:
                        left[helper] = left[helper].astype(str).str.strip()
                        left[helper] = left[helper].replace({'': pd.NA, 'NA': pd.NA, 'None': pd.NA, 'nan': pd.NA})
                    except Exception:
                        pass
            # Prefer NodeDesc2-based vendor, then fallback to target-based; materialize Vendor2 now
            v2_from_r = left.get('Vendor2_cable_r')
            v2_from_t = left.get('Vendor2_cable')
            try:
                left['Vendor2'] = v2_from_r.combine_first(v2_from_t)
            except Exception:
                # Safe fallback if any is None
                left['Vendor2'] = v2_from_r if v2_from_r is not None else v2_from_t
            for col in ['Vendor1_cable', 'Vendor2_cable', 'Vendor2_cable_r', 'NodeGUID_vr', 'PortNumber_vr']:
                if col in left.columns:
                    left.drop(columns=[col], inplace=True)
        except Exception:
            pass

        # HCA info for DeviceID/FW/LID (node-level)
        try:
            hca = HcaManager(ib_dir=self.ib_dir, g=self.g)
            hcols = ['NodeGUID', 'FW', 'HWInfo_DeviceID', 'LID']
            hdf = hca.df[hcols].drop_duplicates()

            # Left annotations
            left = left.merge(
                hdf.rename(columns={'NodeGUID': 'NodeGUID_left', 'FW': 'Firmware1', 'HWInfo_DeviceID': 'DeviceID1', 'LID': 'LID1'}),
                left_on='NodeGUID', right_on='NodeGUID_left', how='left'
            )
            # Right annotations
            left = left.merge(
                hdf.rename(columns={'NodeGUID': 'NodeGUID_right', 'FW': 'Firmware2', 'HWInfo_DeviceID': 'DeviceID2', 'LID': 'LID2'}),
                left_on='Target GUID', right_on='NodeGUID_right', how='left'
            )
        except Exception:
            # Fallback empty columns
            left['DeviceID1'] = pd.NA
            left['Firmware1'] = pd.NA
            left['LID1'] = pd.NA
            left['DeviceID2'] = pd.NA
            left['Firmware2'] = pd.NA
            left['LID2'] = pd.NA

        # Build final fields
        left['NodeDesc1'] = left['Node Name']
        left['PortNum1'] = left['PortNumber']
        # Do not overwrite PM_INFO result; only fill if missing/NaN using PORTS fallback
        if 'Link Downed Counter 1' not in left.columns:
            left['Link Downed Counter 1'] = pd.to_numeric(
                left.get('LinkDownedCounter', left.get('LinkDownedCounterExt', pd.Series(0, index=left.index))),
                errors='coerce'
            ).fillna(0).astype(int)
        else:
            fallback_ld1 = pd.to_numeric(
                left.get('LinkDownedCounter', left.get('LinkDownedCounterExt', pd.Series(0, index=left.index))),
                errors='coerce'
            )
            left['Link Downed Counter 1'] = pd.to_numeric(left['Link Downed Counter 1'], errors='coerce').fillna(fallback_ld1).fillna(0).astype(int)
        # Preserve Vendor2 from CABLE_INFO; only set from graph if currently NA
        try:
            graph_vendor2 = left['Target GUID'].map(vendor_map)
            if 'Vendor2' in left.columns:
                left['Vendor2'] = left['Vendor2'].where(left['Vendor2'].notna(), graph_vendor2)
            else:
                left['Vendor2'] = graph_vendor2
        except Exception:
            pass
        left['PortNum2'] = left['Target Port']
        # Prefer joined NodeDesc2; fallback to Target Name from edges
        left['NodeDesc2'] = left['NodeDesc2'].fillna(left.get('Target Name'))

        out_cols = [
            'NodeDesc1', 'PortNum1', 'DeviceID1', 'Firmware1', 'LID1', 'Link Downed Counter 1', 'Vendor1',
            'NodeDesc2', 'PortNum2', 'DeviceID2', 'Firmware2', 'LID2', 'Link Downed Counter 2', 'Vendor2'
        ]
        out_df = left[[c for c in out_cols if c in left.columns]].copy()
        return out_df

    def print_pairs(self, num_lines=50, sort=0, hide_zero_linkdown: bool = False, filter_nonzero_linkdown: bool = False):
        from tabulate import tabulate
        df = self._build_pairs_df()
        if filter_nonzero_linkdown:
            for_pair_cols = ['Link Downed Counter 1', 'Link Downed Counter 2']
            if any(c in df.columns for c in for_pair_cols):
                c1 = df.get('Link Downed Counter 1', 0)
                c2 = df.get('Link Downed Counter 2', 0)
                try:
                    mask = (pd.to_numeric(c1, errors='coerce').fillna(0) > 0) & (pd.to_numeric(c2, errors='coerce').fillna(0) > 0)
                    df = df[mask]
                except Exception:
                    pass
        columns = df.columns.tolist()
        if abs(sort) > 0 and (abs(sort) - 1) < len(columns):
            df = df.sort_values(by=columns[abs(sort) - 1], ascending=(sort < 0))
        if hide_zero_linkdown:
            for col in ['Link Downed Counter 1', 'Link Downed Counter 2']:
                if col in df.columns:
                    try:
                        if df[col].fillna(0).astype(float).abs().sum() == 0:
                            df.drop(columns=[col], inplace=True)
                    except Exception:
                        pass
        if num_lines > 0:
            df = df.head(num_lines)
        return [tabulate(df, headers='keys', tablefmt='pretty', showindex=False)]

    def get_anomalies(self):
        import pandas as pd
        df = self.df.copy()
        # Build individual anomaly flags with simple thresholds
        # 1) Port state not Active/Up
        # PortState 在某些数据中是数值（如 4 表示 Active），也可能是字符串
        if 'PortState' in df.columns:
            ps = df['PortState']
            try:
                numeric = pd.to_numeric(ps, errors='coerce')
                bad_state = (numeric != 4).astype(int)
                mask_nan = numeric.isna()
                if mask_nan.any():
                    text_bad = ~ps.astype(str).str.contains('Active|Up', case=False, na=False)
                    bad_state = bad_state.where(~mask_nan, text_bad.astype(int))
            except Exception:
                bad_state = (~ps.astype(str).str.contains('Active|Up', case=False, na=False)).astype(int)
        else:
            bad_state = pd.Series(0, index=df.index, dtype=int)
        df_state = df[IBH_ANOMALY_TBL_KEY].copy()
        df_state[f"{IBH_ANOMALY_AGG_COL} Port State Abnormal"] = bad_state

        # 2) Link instability
        link_down = df.get('LinkDownedCounter', df.get('LinkDownedCounterExt'))
        if link_down is None or not hasattr(link_down, 'fillna'):
            link_down = pd.Series(0, index=df.index, dtype=float)
        else:
            link_down = link_down.fillna(0).astype(float)
        link_recovery = df.get('LinkErrorRecoveryCounter')
        if link_recovery is None or not hasattr(link_recovery, 'fillna'):
            link_recovery = pd.Series(0, index=df.index, dtype=float)
        else:
            link_recovery = link_recovery.fillna(0).astype(float)
        df_link = df[IBH_ANOMALY_TBL_KEY].copy()
        df_link[f"{IBH_ANOMALY_AGG_COL} Link Instability"] = (
            (link_down > 0).astype(int) + (link_recovery > 0).astype(int)
        )

        # 3) Physical/receive/switch relay errors
        phy_err = df.get('LocalLinkIntegrityErrorsExt')
        phy_err = phy_err.fillna(0).astype(float) if hasattr(phy_err, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        rcv_err = df.get('PortRcvErrorsExt')
        rcv_err = rcv_err.fillna(0).astype(float) if hasattr(rcv_err, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        relay_err = df.get('PortRcvSwitchRelayErrors')
        relay_err = relay_err.fillna(0).astype(float) if hasattr(relay_err, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        df_errs = df[IBH_ANOMALY_TBL_KEY].copy()
        df_errs[f"{IBH_ANOMALY_AGG_COL} Receive/Physical Errors"] = (
            (phy_err > 0).astype(int) + (rcv_err > 0).astype(int) + (relay_err > 0).astype(int)
        )

        # 4) Transmit/constraint/discards
        xmit_disc = df.get('PortXmitDiscards', df.get('PortXmitDiscardsExt'))
        xmit_disc = xmit_disc.fillna(0).astype(float) if hasattr(xmit_disc, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        xmit_const = df.get('PortXmitConstraintErrors')
        xmit_const = xmit_const.fillna(0).astype(float) if hasattr(xmit_const, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        rcv_const = df.get('PortRcvConstraintErrors')
        rcv_const = rcv_const.fillna(0).astype(float) if hasattr(rcv_const, 'fillna') else pd.Series(0, index=df.index, dtype=float)
        df_xmit = df[IBH_ANOMALY_TBL_KEY].copy()
        df_xmit[f"{IBH_ANOMALY_AGG_COL} Tx/Constraint Issues"] = (
            (xmit_disc > 0).astype(int) + (xmit_const > 0).astype(int) + (rcv_const > 0).astype(int)
        )

        # Merge all anomaly frames
        df_anom = merge_anomalies(df, [df_state, df_link, df_errs, df_xmit])
        return df_anom
