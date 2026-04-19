#!/usr/bin/env python3
"""
sim_summary.py - CoMeT Simulation Summary Report Generator
"""

import sys
import os
import argparse


def parse_trace_file(filepath):
    """Parse a CoMeT .trace file into headers and a data matrix."""
    if not os.path.exists(filepath):
        return None

    headers = []
    data = []

    with open(filepath, 'r') as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            parts = line.split()

            if idx == 0:
                headers = parts
            else:
                try:
                    row = [float(val) for val in parts]
                    if len(row) == len(headers):
                        data.append(row)
                except ValueError:
                    continue

    if not headers or not data:
        return None

    cores = [(h, i) for i, h in enumerate(headers) if h.startswith('C_')]
    banks = [(h, i) for i, h in enumerate(headers) if h.startswith('B_')]

    return {
        'headers': headers,
        'data': data,
        'cores': cores,
        'banks': banks,
        'epochs': len(data),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate a human-readable summary report from CoMeT simulation results.",
        epilog="""Examples:
  %(prog)s comet_results/gainestown_3D
  %(prog)s comet_results/gainestown_DDR comet_results/gainestown_3D
  %(prog)s comet_results/gainestown_3D --threshold 85 --csv""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'result_dirs', nargs='+',
        help="One or more simulation result directories to analyze."
    )
    parser.add_argument(
        '--threshold', type=float, default=80.0,
        help="Temperature threshold (°C) for violation detection (default: 80)"
    )
    parser.add_argument(
        '--csv', metavar='FILE', nargs='?', const='sim_summary.csv',
        help="Export statistics to CSV file (default name: sim_summary.csv)"
    )

    args = parser.parse_args()

    # Validate directories
    valid_dirs = []
    for d in args.result_dirs:
        if os.path.isdir(d):
            valid_dirs.append(d)
        else:
            print("  Warning: '{}' is not a valid directory, skipping.".format(d))

    if not valid_dirs:
        print("Error: No valid directories provided.")
        sys.exit(1)

    # Parse and report on each directory
    for d in valid_dirs:
        temp_file = os.path.join(d, 'combined_temperature.trace')
        power_file = os.path.join(d, 'combined_power.trace')

        temp_trace = parse_trace_file(temp_file)
        power_trace = parse_trace_file(power_file)

        print("\nDirectory: {}".format(d))
        if temp_trace:
            print("  Temperature trace: {} epochs, {} cores, {} banks".format(
                temp_trace['epochs'], len(temp_trace['cores']), len(temp_trace['banks'])))
        else:
            print("  Temperature trace: not found")
        if power_trace:
            print("  Power trace: {} epochs, {} cores, {} banks".format(
                power_trace['epochs'], len(power_trace['cores']), len(power_trace['banks'])))
        else:
            print("  Power trace: not found")


if __name__ == '__main__':
    main()
