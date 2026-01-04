import re
from collections import defaultdict
from typing import List


def group_switch_list(switch_list: List[dict]) -> List[List[dict]]:
    """
    Group switch_list items automatically based on common prefix patterns.
    
    Args:
        switch_list: List of switch items (dicts with keys 'name', 'inferred_type', 'node_id', etc.)
        
    Returns:
        List of lists, where each inner list contains grouped items
    """
    if not switch_list:
        return []

    if len(switch_list) == 1:
        return [switch_list]

    # Extract names from dicts
    names = [item['name'] for item in switch_list]
    name_to_item = {item['name']: item for item in switch_list}

    # Group by common prefix
    grouped_names = _group_by_common_prefix(names)

    # Convert back to original format
    result = []
    for group_names in grouped_names:
        group_items = [name_to_item[name] for name in group_names]
        result.append(group_items)

    return result


def _group_by_common_prefix(names: List[str]) -> List[List[str]]:
    """Group names by common prefix pattern."""
    groups = defaultdict(list)

    for name in names:
        # Handle patterns like "grla-gaia-su1-l1", "grla-gaia-su2-l1", etc.
        # Find the pattern by removing the last distinguishing part

        # Try different patterns
        patterns = [
            r'^(.+-su\d+)-l\d+$',        # grla-gaia-su1-l1 -> grla-gaia-su1
            r'^(.+_[a-zA-Z]+)_\d+$',     # switch_a_1 -> switch_a
            r'^(.+)-l\d+$',              # any-name-l1 -> any-name
            r'^(.+)_\d+$',               # any_name_1 -> any_name
            r'^(.+)-\d+$',               # any-name-1 -> any-name
        ]

        grouped = False
        for pattern in patterns:
            match = re.match(pattern, name)
            if match:
                base_pattern = match.group(1)
                groups[base_pattern].append(name)
                grouped = True
                break

        if not grouped:
            # Fallback: group by everything except the last part
            parts = re.split(r'[-_]', name)
            if len(parts) > 1:
                base_pattern = '-'.join(parts[:-1]) if '-' in name else '_'.join(parts[:-1])
                groups[base_pattern].append(name)
            else:
                groups[name].append(name)

    return [sorted(group) for group in groups.values()]


def print_switch_groups(groups: List[List], title: str = "Switch Groups"):
    """Pretty print the switch groups."""
    print(f"\n{title}:")
    print("=" * len(title))

    for i, group in enumerate(groups, 1):
        print(f"Group {i} ({len(group)} items):")
        for item in group:
            if isinstance(item, dict):
                print(f"  - {item['name']} (Type: {item['inferred_type']}, ID: {item['node_id']})")
            else:
                print(f"  - {item}")
        print()

    print(f"Total groups: {len(groups)}")
    total_items = sum(len(group) for group in groups)
    print(f"Total items: {total_items}")
