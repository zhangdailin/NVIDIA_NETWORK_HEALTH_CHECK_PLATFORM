import re

from ib_analysis.const import (
    SWITCH_DICT,
    HCA_DICT,
    VENDOR_ID,
    NVLINK_DICT,
    MULTI_PLAIN_DEVICES,
)


class Node:
    def __init__(self, vendid, devid, sysimgguid, guid, description, nport, lid=None, typee=None):
        self.children = {} # port -> Edge
        self.id = 0

        self.type = typee
        if devid in SWITCH_DICT:
            self.type = "SW" # LEAF/SPINE/CORE/NVLinkSW
            assert lid is None
        elif devid in HCA_DICT:
            self.type = "HCA" # HCA
        elif devid in NVLINK_DICT:
            self.type = "GPU" # NVLink GPU, such as GB100
            assert lid is None

        assert (self.type in ["SW", "HCA", "GPU"])
        self.inferred_type = None
        self.rack = None # for NVLink domain only
        self.vendor_id = vendid
        self.device_id = devid
        self.system_guid = hex(int(sysimgguid, 16)) # remove extra zero in the beginning
        self.guid = hex(int(guid, 16))              # remove extra zero in the beginning
        self.desc = description
        self.lid = lid
        self.nport = nport
        self.has_plains = devid in MULTI_PLAIN_DEVICES

        # is used as cache for the self.name() function
        self.name_cache = None

    def planeable(self):
        return self.device_id in MULTI_PLAIN_DEVICES

    def get_children(self, simple_type=None, inferred_type=None, device_id_array=None, exclude_guids=None, exclude_agg_nodes=True):
        """
        by default, doesn't return the AGG_NODE nodes
        """
        if exclude_guids is None:
            exclude_guids = []

        valid_children = [
            c for c in self.children.values()
            if c.node.guid not in exclude_guids and not c.disabled
        ]

        if exclude_agg_nodes:
            valid_children = [c for c in valid_children if c.node.inferred_type != "AGG_NODE"]

        if simple_type:
            return [c for c in valid_children if c.node.simple_type(simple_type)]
        elif inferred_type:
            return [c for c in valid_children if c.node.inferred_type == inferred_type]
        elif device_id_array:
            return [c for c in valid_children if c.node.device_id in device_id_array]
        else:
            return valid_children

    def set_rack(self, rack):
        assert self.simple_type("GPU")
        self.rack = rack
        for child in self.children.values():
            if child.node.simple_type("SW"):
                child.node.rack = rack

    def disable_plains(self):
        self.has_plains = False

    def set_plain(self, plain):
        # We have a single Node instance per HCA (not per plain). We set the
        # plain for the edge connecting this HCA to all the swtiches from the
        # switch side.
        if self.simple_type("HCA"):
            return
        if not self.has_plains:
            return

        other_side_nodes = set()
        for edge in self.children.values():
            if edge.disabled or edge.node.device_id not in MULTI_PLAIN_DEVICES:
                continue

            other_side_edge = edge.node.children[int(edge.dstport)]
            if not other_side_edge.plain and edge.node.simple_type("SW"):
                other_side_nodes.add(edge.node)

            edge.set_plain(plain)
            other_side_edge.set_plain(plain)

        for node in other_side_nodes:
            node.set_plain(plain)

    def set_lid(self, lid):
        # NVL have different LIDs per port! TODO: move LID to Edge
        if self.type == "GPU":
            if not self.lid:
                self.lid = []
            self.lid.append(lid)
        elif self.lid:
            assert self.lid == lid, "Inconsistency in reading the LID information from the ibnetdiscover file!"
        else:
            self.lid = lid

    def infere_type(self):
        if not self.inferred_type:
            return self.type
        return self.inferred_type

    def simple_type(self, s_type=None):
        if not s_type:
            return self.type
        return self.type == s_type

    def vendor(self):
        if self.vendor_id in VENDOR_ID:
            return VENDOR_ID[self.vendor_id]
        return self.vendor_id

    def num_child_hca(self):
        return sum(1 for child in self.children.values() if child.node.type == "HCA")

    def num_child(self, inferred_type):
        return sum(1 for child in self.children.values() if child.node.inferred_type == inferred_type)

    def name(self):
        if self.name_cache:
            return self.name_cache

        # Attempt patterns in order
        for pattern, idx in [(r";(.*):", 0), (r"# \"(.*)\"", 0), (r"\"(.*?)\"", -1)]:
            matches = re.findall(pattern, self.desc)
            if matches:
                self.name_cache = matches[idx].strip()
                break
        else:
            # If none matched, use the original desc
            self.name_cache = self.desc.strip()

        # Remove the phrase "Nvidia Technologies"
        self.name_cache = re.sub(r'Nvidia Technologies', '', self.name_cache).strip()
        self.name_cache = re.sub(r'Mellanox Technologies', '', self.name_cache).strip()

        return self.name_cache

    def dev_type(self):
        """
            translates devid into the device type
        """
        if self.type == "SW":
            if self.device_id in SWITCH_DICT:
                return SWITCH_DICT[self.device_id]
        elif self.type == "HCA":
            if self.device_id in HCA_DICT:
                return HCA_DICT[self.device_id]
        elif self.type == "GPU":
            if self.device_id in NVLINK_DICT:
                return NVLINK_DICT[self.device_id]
        return self.device_id

    def __repr__(self):
        sysimgguid = self.system_guid
        switchguid = self.guid
        name = self.name()
        dev = self.dev_type()
        lid = self.lid
        simple_type = self.type
        inferred_type = self.inferred_type
        return f"{name=}, {dev=}, {switchguid=}, {sysimgguid=}, {lid=}, {simple_type=}, {inferred_type=}"

    def add_child(self, srcport, edge):
        self.children[int(srcport)] = edge
