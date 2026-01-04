"""Test topology with health coloring"""
import sys
from pathlib import Path

# Test if we can import and use the health coloring
try:
    from ib_analysis.graph import Graph
    from ib_analysis.health_score import Issue, Severity

    print("[OK] Imports successful")

    # Create mock issues
    test_issues = [
        {
            'severity': 'critical',
            'category': 'ber',
            'description': 'High BER detected',
            'node_guid': '0x7cfe9003009ce5b0',
            'port_number': 1,
            'weight': 10.0,
        },
        {
            'severity': 'warning',
            'category': 'congestion',
            'description': 'High congestion',
            'node_guid': '0x7cfe9003009ce5b1',
            'port_number': 2,
            'weight': 5.0,
        }
    ]

    print(f"[OK] Created {len(test_issues)} test issues")

    # Test health color function
    g = Graph.__new__(Graph)  # Create instance without __init__

    colors = {
        100: g.get_health_color(100),
        80: g.get_health_color(80),
        60: g.get_health_color(60),
        40: g.get_health_color(40),
        20: g.get_health_color(20),
    }

    print("[OK] Health color mapping:")
    for score, color in colors.items():
        print(f"  Score {score}: {color}")

    print("\n[OK] All tests passed!")

except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
