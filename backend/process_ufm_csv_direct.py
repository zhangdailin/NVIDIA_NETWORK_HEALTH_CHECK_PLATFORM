#!/usr/bin/env python3
"""
Direct UFM CSV Processing Script

Bypasses HTTP upload and processes CSV files directly.
"""
import sys
import json
import pandas as pd
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.ufm_csv_service import UFMCSVService

def main():
    if len(sys.argv) < 2:
        print("Usage: python process_ufm_csv_direct.py <csv_file>")
        print("Example: python process_ufm_csv_direct.py ../test/low_freq_debug.csv")
        sys.exit(1)

    csv_file = Path(sys.argv[1])

    if not csv_file.exists():
        print(f"Error: File not found: {csv_file}")
        sys.exit(1)

    # Read with latin-1 (can decode any byte sequence)
    print(f"Reading {csv_file}...")
    print(f"File size: {csv_file.stat().st_size / 1024 / 1024:.2f} MB")

    df = pd.read_csv(csv_file, encoding='latin-1')
    print(f"SUCCESS: Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Create service
    print("\nInitializing UFM CSV service...")
    service = UFMCSVService()
    service.df = df
    service.file_path = csv_file

    # Analyze
    print("Performing analysis...")
    results = service.get_full_analysis()

    # Save results
    output_file = Path("ufm_analysis_result.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to {output_file}")

    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)

    # BER Analysis
    ber = results['ber_analysis']
    print(f"\nBER Analysis:")
    print(f"  Critical ports (BER > 1e-6): {len(ber['critical_ports'])}")
    print(f"  Warning ports (BER > 1e-9): {len(ber['warning_ports'])}")

    # Link Status
    link = results['link_status']
    print(f"\nLink Status:")
    print(f"  Links down: {link['summary'].get('links_down', 0)}")
    print(f"  Error recovery events: {link['summary'].get('error_recovery_events', 0)}")

    # Temperature
    temp = results['temperature']
    if temp.get('summary'):
        print(f"\nTemperature:")
        print(f"  Average: {temp['summary'].get('avg_temp', 0):.1f}°C")
        print(f"  Maximum: {temp['summary'].get('max_temp', 0):.1f}°C")
        print(f"  Hot ports (> 60°C): {len(temp.get('hot_ports', []))}")

    # Cables
    cables = results['cables']
    print(f"\nCable Information:")
    print(f"  Cables identified: {cables['summary'].get('cables_identified', 0):,}")
    print(f"  Cable types: {len(cables.get('cable_types', []))}")

    # Port Errors
    errors = results['port_errors']
    print(f"\nPort Errors:")
    for error_type, stats in errors['summary'].items():
        print(f"  {error_type}: {stats['ports_with_errors']} ports")

    print("\n" + "=" * 60)
    print("Analysis complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
