from ib_analysis.utils import xmit_wait2bw_gbps, xmit_data2bw_gbps
from ib_analysis.pbar import pbar_r


class Edge:
    def __init__(self, node, srcport, dstport, speed, disabled):
        self.srcport = srcport
        self.dstport = dstport
        self.speed = speed
        self.node = node
        self.disabled = disabled
        self.plain = None # plain=None --> no plain device/architecture.

    def set_plain(self, plain):
        if self.plain:
            assert self.plain == plain, f'Inconsistency in setting the plain. old={self.plain}, new={plain}, {self}'
            return
        self.plain = plain

    def __repr__(self):
        srcp = self.srcport
        dstp = self.dstport
        node = self.node
        plain = self.plain

        return f"{srcp=}, {dstp=}, {plain=},    {node=}"

def add_edges_for_node(node):
    pbar_r(key="convert_g").update()
    edges_data = []
    for edge in node.children.values():
        edges_data.append({
            "Source": node.id,
            "Target": edge.node.id,
            "Source Port": int(edge.srcport),
            "Target Port": int(edge.dstport),
            "Speed": edge.speed,
            "Source Name": node.name(),
            "Target Name": edge.node.name(),
            "Source Degree": len(node.children),
            "Source GUID": node.guid,
            "Target GUID": edge.node.guid,
            "HTML Disabled": edge.disabled,
            "Plain": edge.plain,
            "Rack": node.rack,
            "Target Rack": edge.node.rack,
            "Source Inferred Type": node.infere_type(),
            "Target Inferred Type": edge.node.infere_type(),
        })
    return edges_data


def add_edges_for_node_with_xmit(node, duration, df_dict):
    pbar_r(key="convert_g").update()
    edges_data = []
    for edge in node.children.values():
        key = (node.guid, int(edge.srcport))
        if key in df_dict:
            xwait, xdata = df_dict[key]
            xmit_wait = float(xmit_wait2bw_gbps(xwait, duration))
            xmit_data = float(xmit_data2bw_gbps(xdata, duration))
        else:
            # In ByteDance ibdiagnet data, there exists many switches and nodes with no
            # counters in PM_DELTA table. To the best of my knowledge, the reason is that
            # all the counters are zero for the specific node. Therefore, we consider xmit
            # to be zero as well.
            xmit_wait = 0.0
            xmit_data = 0.0

        edges_data.append({
            "Source": node.id,
            "Target": edge.node.id,
            "Source Port": int(edge.srcport),
            "Target Port": int(edge.dstport),
            "Speed": edge.speed,
            "Xmit Wait": xmit_wait,
            "Xmit Data": xmit_data,
            "Source Name": node.name(),
            "Target Name": edge.node.name(),
            "Source Inferred Type": node.infere_type(),
            "Target Inferred Type": edge.node.infere_type(),
            "Source GUID": node.guid,
            "Target GUID": edge.node.guid,
            "HTML Disabled": edge.disabled,
            "Plain": edge.plain,
            "Rack": node.rack,
            "Target Rack": edge.node.rack,
        })
    return edges_data
