import re
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import pandas as pd
from pyvis.network import Network
from tabulate import tabulate

from .msg import MSG
from .const import MULTI_PLAIN_DEVICES
from .pbar import enable_pbar, disable_pbar, pbar_r, close_pbar
from .utils import _t, print_aggregate_two, print_aggregate
from .utils import process_extended_column, is_intera_plain_link
from .utils import rename_topo_df, get_section_with_title
from .node import Node
from .edge import Edge, add_edges_for_node_with_xmit, add_edges_for_node
from .filter import accommodate_filter_in_graph
from .grouper import group_switch_list
from .anomaly import (
    get_asymmetric_topo_anomalies, contains_anomalies,
    IBH_ANOMALY_AGG_COL, IBH_ANOMALY_AGG_WEIGHT,
    print_no_anomaly_detected, merge_anomalies
)


class Graph:
    COLUMNS_TO_PRINT_NODES = ['ID', 'InferredType', 'DeviceType', 'GUID', 'Name']
    COLUMNS_TO_PRINT_EDGES = ['Source Name', 'Source Port', 'Target Name', 'Target Port']
    COLUMNS_TO_PRINT_ANOMALY = [
        'Index', 'NodeGUID', 'Node Name', 'PortNumber',
        'Node Inferred Type', 'Attached To', IBH_ANOMALY_AGG_COL
    ]

    def __init__(self, ib_dir):
        self.nodes = {}     # guid --> node (includes ufm nodes)
        self.ufms = {}      # guid --> ufm node
        self.connections = {}  # (guid, port) --> node
        self.filtering_df = pd.DataFrame()  # will be used in generating (edges,nodes) dataFrames
        self.xmit_m = None
        self.pminfo_m = None

        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".ibnetdiscover")][0]
        filename = os.path.join(ib_dir, file)

        # decide if we want pBar or not!
        with open(filename, 'r', encoding='latin-1') as file:
            total_line_count = sum(1 for line in file)
            if total_line_count < 5*10**4:
                disable_pbar()
            else:
                enable_pbar()

        # parse the switches, hcas, and more...
        self.find_switches(filename)
        self.find_hcas(filename)

        # find UFMs
        file = [f for f in os.listdir(ib_dir) if str(f).endswith(".log")][0]
        log_filename = os.path.join(ib_dir, file)
        self.find_ufms(log_filename)

        # parse edges (after UFM to disable the links)
        self.find_edges(filename)

        self.infere_types()
        self.infere_plains()
        self.infere_racks() # NVLink only! GB100/GB200 architecture
        self.update_node_names() # NVLink only! GB100/GB200 architecture

    def update_node_names(self):
        gpu_list = [n for n in self.nodes.values() if n.simple_type("GPU")]
        if len(gpu_list) < 30:
            return
        name_set = set([n.name() for n in gpu_list])
        if len(name_set) == 1:
            for gpu in gpu_list:
                port_set = set()
                for _, edge in gpu.children.items():
                    port_set.add(edge.dstport)
                if len(port_set) == 1:
                    gpu_id = f"{str(int(list(port_set)[0])).zfill(3)}"
                    gpu.name_cache = f"{gpu.name_cache}_{gpu.rack}_{gpu_id}"

    def set_xmit(self, xmit):
        self.xmit_m = xmit

    def set_pminfo(self, pmifno):
        self.pminfo_m = pmifno

    def set_filtering_df(self, df):
        self.filtering_df = df

    def get_anomalies(self):
        _, edge_df = self.to_dataframe()
        rename_topo_df(edge_df)

        anomalies_arr = []
        anomalies_arr.append(get_asymmetric_topo_anomalies(self.nodes, edge_df, "LEAF", "HCA"))
        anomalies_arr.append(get_asymmetric_topo_anomalies(self.nodes, edge_df, "LEAF", "SPINE"))
        anomalies_arr.append(get_asymmetric_topo_anomalies(self.nodes, edge_df, "SPINE", "CORE"))
        anomalies_arr.append(get_asymmetric_topo_anomalies(self.nodes, edge_df, "SPINE", "LEAF"))
        anomalies_arr.append(get_asymmetric_topo_anomalies(self.nodes, edge_df, "CORE", "SPINE"))

        df_anomalies = merge_anomalies(edge_df, anomalies_arr)
        return df_anomalies

    def print_anomalies(self, sort=0, num_lines=50, extended_columns=None):
        """
        Main execution point from iba
        """
        df_anomalies = self.get_anomalies()

        if not contains_anomalies(df_anomalies):
            return [print_no_anomaly_detected()]

        _, edge_df = self.to_dataframe()
        print_table, columns = process_extended_column(Graph.COLUMNS_TO_PRINT_ANOMALY, extended_columns, edge_df)
        if not print_table:
            return[columns]

        # Print Anomalies #
        if sort == 0:
            df_anomalies = df_anomalies.sort_values(by=[IBH_ANOMALY_AGG_WEIGHT, 'NodeGUID', 'PortNumber'], ascending=False)
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

        nodes, _ = self.to_dataframe()

        report_sections = [('InferredType', 'DeviceType', 'inferred type')]

        plots = []
        for col1, col2, txt in report_sections:
            plot = print_aggregate_two(
                nodes, col1, col2,
                title=f"Overview | more details on {_t(txt)}"
            )
            plots.append(plot)

        report_sections = [('DeviceType', 'device model')]
        for col1, txt in report_sections:
            plot = print_aggregate(nodes, col1, title=f"Overview | {_t(txt)}")
            plots.append(plot)


        # Use PMInfo to build neighbor table if available; otherwise fall back to simple aggregates
        if self.pminfo_m is None or not hasattr(self.pminfo_m, 'df'):
            nodes, _ = self.to_dataframe()
            plots.append(get_section_with_title("Type/Count of neighbors (PM_INFO missing)"))
            plots.append(tabulate(nodes[Graph.COLUMNS_TO_PRINT_NODES], headers='keys', tablefmt='pretty', showindex=False))
            return plots

        df_edges = self.pminfo_m.df.copy()
        df_edges = df_edges.dropna(subset=['Name', 'Attached To'])

        # --- 2.  Drop exact duplicates (same tail  same head) ------------------
        df_edges = df_edges.drop_duplicates(subset=["Name", "Attached To"])

        # --- 3.  Work out the complete vocabulary of node types -----------------
        all_types = pd.unique(
            pd.concat([df_edges["Node Inferred Type"], df_edges["Target Type"]])
        )

        # --- 4.  Build the table -------------------------------------------------
        #  • one row per focal node
        #  • one column per possible neighbour type
        #  • each cell = count of **unique** neighbours of that type
        tidy = (
            df_edges
            .drop_duplicates(subset=["Name", "Attached To"])      # safety
            .pivot_table(
                index="Name",
                columns="Target Type",
                values="Attached To",
                aggfunc=pd.Series.nunique,
                fill_value=0,
            )
            .reindex(columns=all_types, fill_value=0)              # keep missing types
            .reset_index()
        )

        # --- 5.  (Optional) tidy column order A, B, C… --------------------------
        tidy = tidy[["Name"] + sorted([c for c in tidy.columns if c != "Name"])]

        plots.append(get_section_with_title("Type/Count of neighbors"))
        plots.append(tabulate(tidy, headers='keys', tablefmt='pretty', showindex=False))
        return plots

    def brief_summary(self):
        return []

    def infere_racks(self):
        """
        Infere the rack for a GPU or Switch port
        """
        # currently the only way I'm aware of see if it's NVLink, is if we have GPUs!
        gpu_list = [n for n in self.nodes.values() if n.simple_type("GPU")]
        if len(gpu_list) < 30:
            return
        sw_list = sorted(
            [n for n in self.nodes.values() if n.simple_type("SW")],
            key=lambda n: n.name()
        )

        gpus_per_rack = []
        for sw in sw_list:
            children = set([child.node.guid for child in sw.get_children(simple_type="GPU")])
            if children not in gpus_per_rack:
                gpus_per_rack.append(children)

        for index, gpus in enumerate(gpus_per_rack):
            for gpu_guid in gpus:
                gpu = self.nodes[gpu_guid]
                gpu.set_rack(index)

    def infere_plains(self):
        """
        Infere the plain for a port, only if it's a plained-architecture device
        """
        all_sw = [n for n in self.nodes.values()
            if n.simple_type("SW") and
            len(n.get_children(device_id_array=MULTI_PLAIN_DEVICES)) > 0
        ]
        leaf_sw = [n for n in all_sw
            if len(n.get_children(simple_type="HCA")) > 0
        ]

        if len(leaf_sw) == 0:
            #TODO: b2b scenario!
            return

        # CASE A #
        ##########
        # If a leaf switch is connected to HCAs with different srcports
        # (from HCA's perspective), we consider it a crocodile SW.
        for sw in leaf_sw:
            hca_srcport = set()
            for hca_edge in [ch for ch in sw.children.values()
                              if ch.node.simple_type("HCA") and ch.node.planeable()]:
                hca_srcport.add(hca_edge.dstport)

            if len(hca_srcport) > 1:
                sw.disable_plains()

        # CASE B #
        ##########
        # If a switch is conncted to multiple planes (ASICs) in another switch:
        for sw in all_sw:
            guid_to_systemguid = defaultdict(set)
            for connected_sw in [ch.node for ch in sw.children.values()
                            if ch.node.simple_type("SW") and
                                ch.node.system_guid != sw.system_guid]:
                guid_to_systemguid[connected_sw.system_guid].add(connected_sw.guid)

            for _, arr in guid_to_systemguid.items():
                if len(arr) > 1:
                    sw.disable_plains()

        for sw in leaf_sw:
            if not sw.device_id in MULTI_PLAIN_DEVICES:
                continue

            ports = {}
            for ch in sw.children.values():
                if (
                    ch.node.simple_type("HCA") and
                    ch.node.device_id in MULTI_PLAIN_DEVICES
                ):
                    ports[ch.dstport] = ports.get(ch.dstport, 0) + 1
            if len(ports) == 0:
                continue

            plain = max(ports, key=ports.get)
            sw.set_plain(plain)

    def infere_types(self):
        """
        Infere type of the switch, if it's LEAF, SPINE or CORE
        """
        # detect LEAF switches
        for _, n in self.nodes.items():
            if  n.inferred_type: # exclude the AGG nodes!
                continue

            hca_cnt = len(n.get_children(simple_type="HCA", exclude_guids=self.ufms.keys()))
            if hca_cnt > 1:
                n.inferred_type = "LEAF"

        # detect SPINE switches
        for _, n in self.nodes.items():
            if n.type == "HCA" or n.type == "GPU" or n.inferred_type:
                continue

            sw_cnt = len(n.get_children(simple_type="SW"))
            leaf_cnt = len(n.get_children(inferred_type="LEAF"))
            hca_cnt = len(n.get_children(simple_type="HCA", exclude_guids=self.ufms.keys()))

            if sw_cnt > 1 and leaf_cnt > 0 and hca_cnt == 0:
                n.inferred_type = "SPINE"

        # detect CORE switches
        for _, n in self.nodes.items():
            if n.type == "HCA" or n.type == "GPU" or n.inferred_type:
                continue

            sw_cnt = len(n.get_children(simple_type="SW"))
            spine_cnt = len(n.get_children(inferred_type="SPINE"))
            leaf_cnt = len(n.get_children(inferred_type="LEAF"))
            hca_cnt = len(n.get_children(simple_type="HCA", exclude_guids=self.ufms.keys()))

            if sw_cnt > 1 and spine_cnt > 1 and leaf_cnt == 0 and hca_cnt == 0:
                n.inferred_type = "CORE"

        previous_unknown_count = len(self.nodes)
        while True:
            current_unknown_cnt = self.num_unknown_sw()
            if previous_unknown_count == current_unknown_cnt or current_unknown_cnt == 0:
                break
            previous_unknown_count = current_unknown_cnt

            for _, n in self.nodes.items():
                if n.type in ["HCA", "GPU"] or n.inferred_type:
                    continue

                spine_cnt = len(n.get_children(inferred_type="SPINE"))
                leaf_cnt =  len(n.get_children(inferred_type="LEAF"))
                core_cnt =  len(n.get_children(inferred_type="CORE"))
                sw_cnt =    len(n.get_children(simple_type="SW"))
                nvl_cnt =   len(n.get_children(simple_type="GPU", exclude_guids=self.ufms.keys()))

                if nvl_cnt > 0:
                    n.inferred_type = "NVLinkSW"
                elif sw_cnt > 0 and core_cnt >= 0 and spine_cnt == 0 and leaf_cnt > 0:
                    n.inferred_type = "SPINE"
                elif sw_cnt > 0 and core_cnt == 0 and spine_cnt > 0 and leaf_cnt == 0:
                    n.inferred_type = "LEAF"
                elif sw_cnt > 0 and core_cnt > 0 and spine_cnt == 0:
                    n.inferred_type = "SPINE"

        for _, n in self.nodes.items():
            if n.type in ["HCA", "GPU"] or n.inferred_type:
                continue
            else:
                n.inferred_type = "Unknown"

    def num_unknown_sw(self):
        unknowns = [c for _, c in self.nodes.items() if c.simple_type() == "SW" and c.inferred_type is None]
        return len(unknowns)

    @staticmethod
    def weight_typed_based(row):
        inferred_type = row['InferredType']
        if inferred_type == "CORE":
            return 30
        if inferred_type == "SPINE":
            return 20
        if inferred_type == "LEAF":
            return 10
        return 1

    def to_dataframe(self, xmit=None):
        nodes_data = [{
            "ID": node.id,
            "Type": node.type,
            "InferredType": node.infere_type(),
            "Vendor": node.vendor(),
            "DeviceType": node.dev_type(),
            "GUID": node.guid,
            "Name": node.name(),
            "Rack": node.rack
        } for _, node in self.nodes.items()]

        ## EDGES ##
        # pbar.update() happens in the add_edge_... methods
        pbar_r(key="convert_g", desc="convert graph....", total=len(self.nodes))

        edges_data = []
        with ThreadPoolExecutor() as executor:
            _nodes = list(self.nodes.values())
            random.shuffle(_nodes)

            # Submit tasks to the executor
            if xmit:
                df = xmit.original_df.copy()
                df_dict = {  ## It's much faster to lookup from a dicts, than from a DataFrame.
                    (row['NodeGUID'], row['PortNumber']):
                        (row['PortXmitWaitTotal'], row['PortXmitDataTotal']) for index, row in df.iterrows()
                }
                futures = [executor.submit(add_edges_for_node_with_xmit, node, xmit.duration, df_dict) for node in _nodes]
            else:
                futures = [executor.submit(add_edges_for_node, node) for node in _nodes]

            # Progress bar setup
            for future in as_completed(futures):
                # Retrieve result and update the edges_data list
                edges_data.extend(future.result())

        edges = pd.DataFrame(edges_data)
        nodes = pd.DataFrame(nodes_data)

        if len(self.filtering_df) > 0:
            (nodes, edges) = accommodate_filter_in_graph(nodes=nodes, edges=edges, filtering_df=self.filtering_df)

        close_pbar("convert_g")
        return (nodes, edges)

    def node_title(self, row):
        title = f"Name: {row['Name']}\n"
        title += f"Inferred Type: {row['InferredType']}\n"
        title += f"Device Model: {row['DeviceType']}\n"
        title += f"GUID: {row['GUID']}\n"
        if 'HealthScore' in row and pd.notna(row['HealthScore']):
            title += f"Health: {row['HealthScore']}/100\n"
        if 'IssueCount' in row and pd.notna(row['IssueCount']) and row['IssueCount'] > 0:
            title += f"Issues: {row['IssueCount']}\n"
        return title

    def configure_html_edge(self, net, u, v, phy, **kwargs):
        net.add_edge(u, v, physics=phy)

    def calculate_node_health(self, nodes, issues=None):
        """Calculate health score for each node based on issues."""
        node_health = {}
        node_issues = {}

        if issues:
            for issue in issues:
                guid = issue.get('node_guid', '')
                if guid:
                    if guid not in node_issues:
                        node_issues[guid] = []
                    node_issues[guid].append(issue)

        for _, row in nodes.iterrows():
            guid = row['GUID']
            if guid in node_issues:
                issue_list = node_issues[guid]
                total_weight = sum(i.get('weight', 1) for i in issue_list)
                severity_penalty = sum(
                    3 if i.get('severity') == 'critical' else
                    1.5 if i.get('severity') == 'warning' else 0.5
                    for i in issue_list
                )
                health = max(0, 100 - int(total_weight * severity_penalty))
                node_health[guid] = health
                node_issues[guid] = len(issue_list)
            else:
                node_health[guid] = 100
                node_issues[guid] = 0

        nodes['HealthScore'] = nodes['GUID'].map(node_health)
        nodes['IssueCount'] = nodes['GUID'].map(node_issues)
        return nodes

    def get_health_color(self, health_score):
        """Get color based on health score."""
        if health_score >= 80:
            return '#22c55e'  # green
        elif health_score >= 60:
            return '#eab308'  # yellow
        elif health_score >= 40:
            return '#f97316'  # orange
        else:
            return '#ef4444'  # red

    def _setup_network(self):
        """
        Setup network configuration and prepare data for HTML visualization.
        
        Returns:
            tuple: (net, nodes, edges, leaf_switches)
        """
        nodes, edges = self.to_dataframe(xmit=self.xmit_m)
        leaf_switches = nodes.loc[nodes['InferredType'] == 'LEAF', 'Name'].unique().tolist()

        net = Network(
            height="1000px", width="100%",
            bgcolor="#FAEBD7", font_color="black",
            filter_menu=True, select_menu=False,
            layout=True,
            cdn_resources='in_line'
        )
        net.inherit_edge_colors(False)
        net.options.edges.smooth.enabled = False
        net.options.interaction.selectable = True

        return net, nodes, edges, leaf_switches

    def _set_node_levels(self, net, nodes, leaf_switches):
        """
        Add all nodes to the network with appropriate styling and positioning.
        
        Args:
            net: Network object to add nodes to
            nodes: DataFrame containing node information
            leaf_switches: List of leaf switch names
            zig_zag_levels: Number of zigzag levels for HCA positioning
        """
        pbar = pbar_r(key="add_node", desc="Add nodes ...", total=len(nodes))
        leaf_list, spine_list = [], []
        zigzag_cnt = {}  # Nodes of a single leaf in a zig-zag order for better label readability

        # Set number of Zig-Zag Levels
        zig_zag_levels = 2
        if len(leaf_switches) > 0:
            first_leaf = [n for _, n in self.nodes.items() if n.inferred_type == 'LEAF'][0]
            if first_leaf.num_child_hca() > 9:
                zig_zag_levels = 5

        # Iterate over all nodes
        for _, row in nodes.iterrows():
            pbar.update()
            group = row['InferredType']
            shape = "circle"
            phy = False
            add_later = False

            # UFM / AGG_NODE
            if row['InferredType'] in ["UFM", "AGG_NODE"]:
                # We don't show the AGG and UFM nodes
                net.add_node(
                    row['ID'],
                    group="UFM_AGG_NODE",
                    level=18, hidden=True,
                    label=row['Name']
                )
                continue
            # HCA
            if row['InferredType'] == "HCA":
                hca_guid = row['GUID']
                try:
                    leaf_sw = self.get_connection(hca_guid, "1")
                    if not leaf_sw:
                        # HCA is not connected to any switch: b2b scenario? 
                        # or missing plain of a NIC
                        net.add_node(
                            row['ID'],
                            label=row['Name'],
                            group=group,
                            title=self.node_title(row),
                            level=21
                        )
                        continue

                    if leaf_sw.guid not in zigzag_cnt:
                        zigzag_cnt[leaf_sw.guid] = 0
                    zigzag_cnt[leaf_sw.guid] += 1

                    level_index = zigzag_cnt[leaf_sw.guid] % zig_zag_levels
                    # HCAs connected to a leaf get unique colors. Also enables physics
                    group = f"HCA_{leaf_switches.index(leaf_sw.name())}"
                except ValueError:
                    level_index = 0
                except KeyError:
                    level_index = 0

                level = 20 + 0.3 * level_index
                shape = "dot"
                phy = True

            # LEAF
            elif row['InferredType'] == "LEAF":
                phy = True
                level = 17
                add_later = True

                leaf_list.append({
                    'name': row['Name'],
                    'inferred_type': row['InferredType'],
                    'node_id': row['ID'],
                    'level': level,
                    'physics': phy,
                    'shape': shape,
                    'title': self.node_title(row)
                })

            # SPINE
            elif row['InferredType'] == "SPINE":
                phy = True
                level = 13
                add_later = True

                spine_list.append({
                    'name': row['Name'],
                    'inferred_type': row['InferredType'],
                    'node_id': row['ID'],
                    'level': level,
                    'physics': phy,
                    'shape': shape,
                    'title': self.node_title(row)
                })

            # CORE
            elif row['InferredType'] == "CORE":
                level = 10

            # GPU (NVLink)
            elif row['Type'] == "GPU": # NVL nodes, not the switches
                level = 20 if pd.isna(row['Rack']) else 20 + 11* row['Rack']
                phy = True

            # NVLink Switch
            elif row['InferredType'] == "NVLinkSW": # NVL nodes, not the switches
                level = 25 + 2* int(row['Rack'])
                phy = True
            else:
                level = 27

            if len(nodes) > 1000:
                phy = False
                net.options.physics.enabled = False

            level_coeff = max(len(nodes)/500, 1)

            # Apply health color if available
            node_color = None
            if 'HealthScore' in row and pd.notna(row['HealthScore']):
                node_color = self.get_health_color(row['HealthScore'])

            if not add_later:
                node_params = {
                    'label': row['Name'],
                    'group': group,
                    'size': 15,
                    'level': level * level_coeff,
                    'shape': shape,
                    'title': self.node_title(row),
                    'physics': phy
                }
                if node_color:
                    node_params['color'] = node_color
                net.add_node(row['ID'], **node_params)

        # Group the leaf_list automatically based on naming patterns
        self._add_grouped_switch_nodes(net, leaf_list, spine_list, level_coeff)
        close_pbar("add_node")

    def _add_grouped_switch_nodes(self, net, leafs_list, spines_list, level_coeff):
        """
        Helper function to add grouped leaf and spine switch nodes to the network.
        It helps to keep the leaf and spine switches that belong to a single SU together. 
        """
        for _list in [leafs_list, spines_list]:
            if _list:
                grouped_list = group_switch_list(_list)
                if len(grouped_list) == 1:
                    grouped_list = grouped_list[0]
                    for i, item in enumerate(grouped_list, 1):
                        group_name = f"SW_{item['name']}_{i}"
                        net.add_node(
                            item['node_id'],
                            label=item['name'],
                            group=group_name,
                            size=15,
                            level=item['level'] * level_coeff,
                            shape=item['shape'],
                            title=item['title'],
                            physics=item['physics']
                        )
                else:
                    for i, group in enumerate(grouped_list, 1):
                        group_name = f"{_list[0]['inferred_type']}_{i}"
                        for item in group:
                            net.add_node(
                                item['node_id'],
                                label=item['name'],
                                group=group_name,
                                size=15,
                                level=item['level'] * level_coeff,
                                shape=item['shape'],
                                title=item['title'],
                                physics=item['physics']
                            )
                        for _u in [item['node_id'] for item in group]:
                            for _v in [item['node_id'] for item in group]:
                                if _u > _v:
                                    net.add_edge(_u, _v, physics=True, hidden=True)

                # print_switch_groups(grouped_list, f"Grouped {_list[0]['inferred_type']} Switches")

    def _add_edges_to_network(self, net, edges, edge_handler):
        """
        Add all edges to the network.
        
        Args:
            net: Network object to add edges to
            edges: DataFrame containing edge information
            edge_handler: Optional edge handler for custom edge configuration
        """
        edges = edges[edges['HTML Disabled'] == False] # we disable connection between plains
        if len(edges) > 0:
            compressed_edges = edges.groupby(['Source', 'Target'])

            pbar = pbar_r(key="add_edge", desc="Add edges ...", total=len(compressed_edges))
            for (_u, _v), group in compressed_edges:
                _u, _v = int(_u), int(_v)
                pbar.update()
                u = net.get_node(_u)
                v = net.get_node(_v)

                if u['group'].startswith('HCA') or v['group'].startswith('HCA'):
                    phy = True
                else:
                    phy = False

                if edge_handler:
                    edge_handler.configure_html_edge(
                        group=group,
                        all_edges=edges,
                        net=net,
                        u=_u, v=_v,
                        phy=phy
                    )
                else:
                    # no need to check if the edge is duplicated
                    net.add_edge(_u, _v, physics=phy)
        close_pbar("add_edge")

    def to_html(self, filename="nx.html", edge_handler=None, issues=None):
        """
        Generate HTML visualization of the network graph.

        Args:
            filename: Output HTML filename
            edge_handler: Optional custom edge handler
            issues: Optional list of issues for health coloring

        Returns:
            List containing the generated filename
        """
        # Setup network and prepare data
        net, nodes, edges, leaf_switches = self._setup_network()

        # Calculate node health if issues provided
        if issues:
            nodes = self.calculate_node_health(nodes, issues)

        # Add nodes to network with appropriate levels
        self._set_node_levels(net, nodes, leaf_switches)

        # Add edges to network
        self._add_edges_to_network(net, edges, edge_handler)

        # Create the HTML file with proper encoding
        try:
            # Try to use pyvis's built-in method first
            net.show(filename, local=False)
        except UnicodeEncodeError:
            # If encoding error occurs, manually write the HTML with UTF-8 encoding
            html_content = net.html
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(html_content)

        return [filename]

    def to_csv(self, csv_filename="edges.csv", extended_columns=None):
        if extended_columns:
            return [MSG[0]]

        _, edges = self.to_dataframe()
        edges.to_csv(csv_filename, index=False)
        return [csv_filename]

    def add_node(self, node):
        if node.system_guid in self.nodes:
            other_node = self.nodes[node.system_guid]
            if node.type == "HCA" and other_node.type == "SW" and node.system_guid != node.guid:
                self.nodes[node.guid] = node
                node.inferred_type = "AGG_NODE"
            else:
                self.nodes[node.guid] = node
        else:
            self.nodes[node.guid] = node
        node.id = len(self.nodes)

    def get_child(self, guid, port):
        guid = hex(int(guid, 16))  # remove extra zero in the beginning
        port = int(port)
        if guid in self.nodes:
            node = self.nodes[guid]
            if port in node.children:
                return node.children[port]
        return None

    def get_node(self, guid):
        try:
            guid = hex(int(guid, 16))  # remove extra zero in the beginning
            if guid in self.nodes:
                return self.nodes[guid]
        except (ValueError, TypeError):
            # Handle invalid GUID format
            return None
        return None

    def get_connection(self, guid, port):
        """
        returns neighbor of a node. 

        Parameters:
        - guid (str): The GUID of the node
        - port (int): node's port in which the neighbor is connected to. 

        Returns:
        - neighbor that is connected to the node's port number
        """
        try:
            guid = hex(int(guid, 16))  # remove extra zero in the beginning
            if (guid, port) in self.connections:
                return self.connections[(guid, port)]
        except (ValueError, TypeError):
            # Handle invalid GUID format
            return None
        return None

    ### PARSER FUNCTIONS ######

    def find_switches(self, filename):
        """
        Parse switches from the ibdiagnet files.
        Fill in {nodes}
        """
        pattern = re.compile(r'vendid=0x([0-9A-Fa-f]+)\n'
                             r'devid=0x([0-9A-Fa-f]+)\n'
                             r'sysimgguid=0x([0-9A-Fa-f]+)\n'
                             r'switchguid=0x([0-9A-Fa-f]+)(?:\(([0-9A-Fa-f]+)\))?\n'
                             r'Switch\s+(\d+)\s+(.*)')
        with open(filename, 'r', encoding="latin-1") as file:
            matches = pattern.findall(file.read())
            pbar = pbar_r(key="find_sw", desc="find switches...", total=len(matches))
            for match in matches:
                pbar.update()
                vendid, devid, sysimgguid, guid, _, num_port, desc = match
                node = Node(
                    typee="SW",
                    vendid=f"0x{vendid}",
                    devid=f"0x{devid}",
                    sysimgguid=f"0x{sysimgguid}",
                    guid=f"0x{guid}",
                    description=desc,
                    nport=num_port
                )
                self.add_node(node)
        close_pbar("find_sw")

    def find_hcas(self, filename):
        """
        Parse HCAs/NVLinks from the ibdiagnet files.
        Fill in {nodes}
        """
        pattern = re.compile(
            r'vendid=0x([0-9A-Fa-f]+)\n'
            r'devid=0x([0-9A-Fa-f]+)\n'
            r'sysimgguid=0x([0-9A-Fa-f]+)\n'
            r'caguid=0x([0-9A-Fa-f]+)(?:\(([0-9A-Fa-f]+)\))?\n'
            r'Ca\s+(\d+)\s+(.*)\n'
            r'(.*)\n'
        )
        with open(filename, encoding='latin-1', mode='r') as file:
            matches = pattern.findall(file.read())
            pbar = pbar_r(key="find_hca", desc="Find hca...", total=len(matches))
            for match in matches:
                pbar.update()

                vendid, devid, sysimgguid, caguid, _, num_port, desc, lidinfo = match
                node = Node(
                    vendid=f"0x{vendid}",
                    devid=f"0x{devid}",
                    sysimgguid=f"0x{sysimgguid}",
                    guid=f"0x{caguid}",
                    description=desc,
                    nport=num_port
                )

                # We don't set lid for NVLink Domain. In nvlink domain, each GPU
                # has multiple LID which currently we don't support! 
                # TODO: move lid from Node to Edge
                if node.type == "HCA":
                    # LID is unique among all the plains (not in NVLink).
                    # Therefore, we don't parse all the plains
                    lid = re.search(r'lid (\d+)', lidinfo).group(1)
                    node.set_lid(lid)
                self.add_node(node)
        close_pbar("find_hca")

    def find_ufms(self, filename):
        pattern = re.compile(r'GUID=(0x[a-fA-F0-9]+)')
        with open(filename, 'r', encoding='latin-1') as file:
            for line in file:
                # Check if the line starts with the desired prefixes.
                if line.startswith("Master SM:") or line.startswith("Standby SM:"):
                    # Search for the GUID pattern in the line.
                    match = pattern.search(line)
                    if match:
                        guid = match.group(1)
                        guid = hex(int(guid, 16))

                        # When UFM is indeed a SW, we don't want to exclude it
                        # from graphs or other things particullarly for the
                        # NVLink domain.
                        if self.get_node(guid).simple_type("HCA"):
                            self.ufms[guid] = self.get_node(guid)
                            self.get_node(guid).inferred_type = "UFM"

    def find_edges(self, filename):
        """
        Parse edges from the ibdiagnet files. 
        Fill in {nodes.children} and {connections}
        """
        switches = dict(filter(lambda item: item[1].type == "SW", self.nodes.items()))
        filecontent = open(filename, 'r', encoding="latin-1").read()

        pbar = pbar_r(key="find_links", desc="Find links...", total=len(switches))
        for guid, sw in switches.items():
            pbar.update()

            pattern = rf"switchguid={guid}(\(\S*\))?\n(.*?\n)\n"
            extracted_lines = re.findall(pattern, filecontent, re.DOTALL)
            if extracted_lines:
                items = extracted_lines[0][1].strip().split('\n')  # all the lines, relevant or not
                for line in items:
                    pattern = r'\[(?P<src_port>.*?)\].*?"[HS]-(?P<guid>.*?)"\[(?P<dst_port>.*?)\].*?lid (?P<lid>\d+) (?P<speed>\w+)'
                    match = re.search(pattern, line)
                    if match:
                        try:
                            edge = match.groupdict()
                            srcport = edge['src_port']
                            dstport = edge['dst_port']

                            if not (node := self.get_node(f"0x{edge['guid']}")):
                                continue

                            node.set_lid(edge['lid'])
                            disabled = is_intera_plain_link(sw, node)

                            edge1 = Edge(
                                node=node,
                                srcport=srcport,
                                dstport=dstport,
                                speed=edge['speed'],
                                disabled=disabled
                            )
                            sw.add_child(srcport, edge1)

                            edge2 = Edge(
                                node=sw,
                                srcport=dstport,
                                dstport=srcport,
                                speed=edge['speed'],
                                disabled=disabled
                            )
                            node.add_child(dstport, edge2)

                            self.connections[(sw.guid, srcport)] = node
                            self.connections[(node.guid, dstport)] = sw

                        except KeyError:
                            print("Error, unknown edge discovered:", f"0x{edge['guid']}")
        close_pbar("find_links")
