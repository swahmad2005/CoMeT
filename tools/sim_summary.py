#!/usr/bin/env python3
"""
sim_summary.py - CoMeT Simulation Summary Report Generator
"""

import sys
import os
import argparse


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

    # TODO: Route to single or comparison mode
    print("Directories to analyze: {}".format(len(valid_dirs)))
    for d in valid_dirs:
        print("  - {}".format(d))
    print("Threshold: {}°C".format(args.threshold))
    if args.csv:
        print("CSV export: {}".format(args.csv))


if __name__ == '__main__':
    main()
