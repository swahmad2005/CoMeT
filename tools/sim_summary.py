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


def compute_stats(values):
    """Compute min, max, mean, and standard deviation for a list of numbers."""
    if not values:
        return {'min': 0, 'max': 0, 'avg': 0, 'stddev': 0}

    n = len(values)
    avg = sum(values) / n
    min_val = min(values)
    max_val = max(values)

    if n > 1:
        variance = sum((x - avg) ** 2 for x in values) / (n - 1)
        stddev = variance ** 0.5
    else:
        stddev = 0.0

    return {
        'min': round(min_val, 2),
        'max': round(max_val, 2),
        'avg': round(avg, 2),
        'stddev': round(stddev, 2),
    }


def get_component_series(trace, col_index):
    """Extract all values for a single component (column) across all epochs."""
    return [row[col_index] for row in trace['data']]


def get_component_stats(trace, components):
    """Compute per-component statistics including peak epoch.

    Args:
        trace: parsed trace dict from parse_trace_file()
        components: list of (name, col_index) tuples (e.g., trace['cores'])

    Returns:
        dict mapping component name -> stats dict with peak_epoch
    """
    result = {}
    for name, col_idx in components:
        series = get_component_series(trace, col_idx)
        stats = compute_stats(series)
        stats['peak_epoch'] = series.index(max(series)) + 1
        result[name] = stats
    return result


def get_aggregate_stats(trace, components):
    """Compute overall statistics across ALL components of a type.

    For example, the overall min/max/avg across all cores combined.
    """
    all_values = []
    for name, col_idx in components:
        all_values.extend(get_component_series(trace, col_idx))
    return compute_stats(all_values)


def find_hotspot(component_stats):
    """Find the component with the highest peak value.

    Args:
        component_stats: dict from get_component_stats()

    Returns:
        tuple of (component_name, peak_value), or (None, 0) if empty
    """
    if not component_stats:
        return None, 0

    hottest = max(component_stats.items(), key=lambda x: x[1]['max'])
    return hottest[0], hottest[1]['max']


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
