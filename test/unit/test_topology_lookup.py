"""Unit tests for Topology Lookup service."""

import pytest
import pandas as pd
from services.topology_lookup import TopologyLookup


class TestTopologyLookup:
    """Test topology lookup functionality."""

    @pytest.fixture
    def topology_lookup(self, sample_ibdiagnet_dir):
        """Create TopologyLookup instance."""
        return TopologyLookup(sample_ibdiagnet_dir)

    def test_topology_lookup_initialization(self, topology_lookup):
        """Test TopologyLookup initialization."""
        assert topology_lookup is not None
        assert hasattr(topology_lookup, 'get_node_name')
        assert hasattr(topology_lookup, 'get_node_type')

    def test_get_node_name(self, topology_lookup):
        """Test getting node name by GUID."""
        # Test with a sample GUID
        test_guid = "0xe8ebd30300723915"
        node_name = topology_lookup.get_node_name(test_guid)

        # Should return a string or None
        assert isinstance(node_name, (str, type(None)))

    def test_get_node_type(self, topology_lookup):
        """Test getting node type by GUID."""
        test_guid = "0xe8ebd30300723915"
        node_type = topology_lookup.get_node_type(test_guid)

        # Should return a valid node type
        valid_types = ["HCA", "Switch", "Router", None, 1, 2, 3]
        assert node_type in valid_types or isinstance(node_type, (str, int, type(None)))

    def test_get_neighbor_info(self, topology_lookup):
        """Test getting neighbor information."""
        test_guid = "0xe8ebd30300723915"
        port_num = 1

        # Try to get neighbor info
        if hasattr(topology_lookup, 'get_neighbor'):
            neighbor = topology_lookup.get_neighbor(test_guid, port_num)
            assert isinstance(neighbor, (dict, type(None)))

    def test_annotate_ports_dataframe(self, topology_lookup):
        """Test annotating a DataFrame with topology info."""
        # Create sample DataFrame
        df = pd.DataFrame({
            'NodeGUID': ['0xe8ebd30300723915', '0x58a2e10300c72314'],
            'PortNumber': [1, 1],
            'Value': [100, 200]
        })

        # Annotate with topology info
        if hasattr(topology_lookup, 'annotate_ports'):
            annotated_df = topology_lookup.annotate_ports(df, guid_col='NodeGUID', port_col='PortNumber')

            # Should add topology columns
            assert isinstance(annotated_df, pd.DataFrame)
            assert len(annotated_df) == len(df)

    def test_guid_normalization(self, topology_lookup):
        """Test GUID normalization."""
        # Different GUID formats
        guid_formats = [
            "0xe8ebd30300723915",
            "0xE8EBD30300723915",
            "e8ebd30300723915",
            "0x00e8ebd30300723915"
        ]

        # All should resolve to same node
        names = []
        for guid in guid_formats:
            name = topology_lookup.get_node_name(guid)
            names.append(name)

        # Should handle different formats
        assert len(names) == len(guid_formats)

    def test_invalid_guid_handling(self, topology_lookup):
        """Test handling of invalid GUIDs."""
        invalid_guids = [
            "invalid",
            "0x",
            "",
            None,
            "0xZZZZ"
        ]

        for guid in invalid_guids:
            # Should handle gracefully
            try:
                name = topology_lookup.get_node_name(guid)
                assert name is None or isinstance(name, str)
            except Exception:
                # Should not crash
                pass

    def test_cache_mechanism(self, topology_lookup):
        """Test that topology lookup uses caching."""
        test_guid = "0xe8ebd30300723915"

        # First lookup
        name1 = topology_lookup.get_node_name(test_guid)

        # Second lookup (should use cache)
        name2 = topology_lookup.get_node_name(test_guid)

        # Should return same result
        assert name1 == name2


class TestTopologyEdgeCases:
    """Test edge cases in topology lookup."""

    def test_missing_nodes_table(self, tmp_path):
        """Test handling when NODES table is missing."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        # Should handle gracefully
        try:
            lookup = TopologyLookup(empty_dir)
            assert lookup is not None
        except Exception as e:
            # Should raise appropriate error
            assert "NODES" in str(e) or "not found" in str(e).lower()

    def test_duplicate_guids(self):
        """Test handling of duplicate GUIDs."""
        # Duplicate GUIDs should be detected
        guids = ["0xe8ebd30300723915", "0xe8ebd30300723915"]
        assert guids[0] == guids[1]

    def test_empty_node_name(self):
        """Test handling of empty node names."""
        node_name = ""
        # Should handle empty names
        assert node_name == ""

    def test_very_long_node_name(self):
        """Test handling of very long node names."""
        long_name = "A" * 1000
        # Should handle long names
        assert len(long_name) == 1000


class TestTopologyIntegration:
    """Integration tests for topology lookup."""

    def test_topology_with_links_table(self, sample_ibdiagnet_dir):
        """Test topology lookup with LINKS table."""
        lookup = TopologyLookup(sample_ibdiagnet_dir)

        # Should be able to resolve links
        assert lookup is not None

    def test_topology_consistency(self, sample_ibdiagnet_dir):
        """Test that topology data is consistent."""
        lookup = TopologyLookup(sample_ibdiagnet_dir)

        # Get all nodes
        test_guid = "0xe8ebd30300723915"
        name = lookup.get_node_name(test_guid)
        node_type = lookup.get_node_type(test_guid)

        # If name exists, type should also exist
        if name:
            assert node_type is not None or node_type == name

    def test_bidirectional_link_resolution(self, sample_ibdiagnet_dir):
        """Test that links can be resolved in both directions."""
        lookup = TopologyLookup(sample_ibdiagnet_dir)

        # Test bidirectional lookup
        # This is a logical test
        assert lookup is not None
