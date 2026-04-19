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


def count_violations(trace, components, threshold):
    """Count epochs where any component exceeds the given threshold.

    Args:
        trace: parsed trace dict
        components: list of (name, col_index) tuples
        threshold: temperature threshold in degrees C

    Returns:
        dict with:
            'total_epochs' - number of epochs with at least one violation
            'components'   - dict mapping violating component names to their violation count
    """
    violating_epochs = set()
    component_violations = {}

    for name, col_idx in components:
        series = get_component_series(trace, col_idx)
        count = 0
        for epoch_idx, val in enumerate(series):
            if val > threshold:
                count += 1
                violating_epochs.add(epoch_idx)
        if count > 0:
            component_violations[name] = count

    return {
        'total_epochs': len(violating_epochs),
        'components': component_violations,
    }


# --- Report Formatting --------------------------------------------------------

SEPARATOR = "-" * 72
THICK_SEP = "=" * 72


def print_header(title):
    """Print a section header with a separator line."""
    print("\n{}".format(SEPARATOR))
    print("  {}".format(title))
    print(SEPARATOR)


def print_stats_table(component_stats, unit, top_n=None):
    """Print a formatted table of per-component statistics.

    Args:
        component_stats: dict mapping name -> stats dict
        unit: string like 'C' or 'W' (for display context)
        top_n: if set, only show the top N highest components
    """
    if not component_stats:
        print("  No data available.")
        return

    # Sort by max value descending (hottest/highest first)
    sorted_items = sorted(component_stats.items(),
                          key=lambda x: x[1]['max'], reverse=True)

    if top_n and len(sorted_items) > top_n:
        sorted_items = sorted_items[:top_n]
        print("  (Showing top {} of {} components)\n".format(
            top_n, len(component_stats)))

    # Table header
    print("  {:<12} {:>8} {:>8} {:>8} {:>8} {:>12}".format(
        'Component', 'Min', 'Avg', 'Max', 'StdDev', 'Peak@Epoch'))
    print("  {} {} {} {} {} {}".format(
        "-" * 12, "-" * 8, "-" * 8, "-" * 8,
        "-" * 8, "-" * 12))

    # Table rows
    for name, stats in sorted_items:
        print("  {:<12} {:>8.2f} {:>8.2f} {:>8.2f} {:>8.2f} {:>12}".format(
            name, stats['min'], stats['avg'], stats['max'],
            stats['stddev'], stats['peak_epoch']))


# ─── Single Directory Report ─────────────────────────────────────────────────

def generate_single_report(result_dir, threshold=80.0):
    """Generate a full summary report for a single simulation result directory."""
    dir_name = os.path.basename(os.path.normpath(result_dir))

    # Find and parse trace files
    temp_file = os.path.join(result_dir, 'combined_temperature.trace')
    power_file = os.path.join(result_dir, 'combined_power.trace')

    temp_trace = parse_trace_file(temp_file)
    power_trace = parse_trace_file(power_file)

    if not temp_trace and not power_trace:
        print("\n  ERROR: No valid trace files found in '{}'".format(result_dir))
        return None

    # Report header
    print("\n{}".format(THICK_SEP))
    print("  CoMeT SIMULATION SUMMARY REPORT")
    print(THICK_SEP)
    print("\n  Directory:      {}".format(result_dir))
    print("  Configuration:  {}".format(dir_name))

    if temp_trace:
        print("  Epochs:         {}".format(temp_trace['epochs']))
        print("  Cores:          {}".format(len(temp_trace['cores'])))
        print("  Memory Banks:   {}".format(len(temp_trace['banks'])))

    # Temperature analysis
    if temp_trace:
        core_temp_stats = get_component_stats(temp_trace, temp_trace['cores'])
        bank_temp_stats = get_component_stats(temp_trace, temp_trace['banks'])

        # Core temperatures
        if core_temp_stats:
            print_header("CORE TEMPERATURES (C)")
            print_stats_table(core_temp_stats, 'C')
            hotspot_name, hotspot_val = find_hotspot(core_temp_stats)
            agg = get_aggregate_stats(temp_trace, temp_trace['cores'])
            print("\n  Overall:  avg = {:.2f} C,  peak = {:.2f} C ({})".format(
                agg['avg'], agg['max'], hotspot_name))

        # Bank temperatures
        if bank_temp_stats:
            print_header("MEMORY BANK TEMPERATURES (C)")
            print_stats_table(bank_temp_stats, 'C', top_n=10)
            hotspot_name, hotspot_val = find_hotspot(bank_temp_stats)
            agg = get_aggregate_stats(temp_trace, temp_trace['banks'])
            print("\n  Overall:  avg = {:.2f} C,  peak = {:.2f} C ({})".format(
                agg['avg'], agg['max'], hotspot_name))

        # Thermal violations
        print_header("THERMAL VIOLATIONS (Threshold: {} C)".format(threshold))

        core_violations = count_violations(temp_trace, temp_trace['cores'], threshold)
        bank_violations = count_violations(temp_trace, temp_trace['banks'], threshold)

        if core_violations['total_epochs'] == 0 and bank_violations['total_epochs'] == 0:
            print("\n  [OK] No thermal violations detected. All components stayed below {} C.".format(
                threshold))
        else:
            if core_violations['components']:
                print("\n  Core violations ({} epochs affected):".format(
                    core_violations['total_epochs']))
                for comp, count in sorted(core_violations['components'].items(),
                                          key=lambda x: x[1], reverse=True):
                    pct = (count / temp_trace['epochs']) * 100
                    print("    [!] {}: {} epochs above {} C ({:.1f}% of simulation)".format(
                        comp, count, threshold, pct))
            if bank_violations['components']:
                print("\n  Bank violations ({} epochs affected):".format(
                    bank_violations['total_epochs']))
                violating = sorted(bank_violations['components'].items(),
                                   key=lambda x: x[1], reverse=True)[:5]
                for comp, count in violating:
                    pct = (count / temp_trace['epochs']) * 100
                    print("    [!] {}: {} epochs above {} C ({:.1f}% of simulation)".format(
                        comp, count, threshold, pct))
                remaining = len(bank_violations['components']) - 5
                if remaining > 0:
                    print("    ... and {} more banks with violations".format(remaining))

    # Power analysis
    if power_trace:
        core_power_stats = get_component_stats(power_trace, power_trace['cores'])
        bank_power_stats = get_component_stats(power_trace, power_trace['banks'])

        if core_power_stats:
            print_header("CORE POWER CONSUMPTION (W)")
            print_stats_table(core_power_stats, 'W')

        if bank_power_stats:
            print_header("MEMORY BANK POWER CONSUMPTION (W)")
            print_stats_table(bank_power_stats, 'W', top_n=10)

    # Key findings
    print_header("KEY FINDINGS")

    findings = []
    if temp_trace:
        core_agg = get_aggregate_stats(temp_trace, temp_trace['cores'])
        bank_agg = get_aggregate_stats(temp_trace, temp_trace['banks'])
        hottest_core, hottest_core_val = find_hotspot(
            get_component_stats(temp_trace, temp_trace['cores']))
        hottest_bank, hottest_bank_val = find_hotspot(
            get_component_stats(temp_trace, temp_trace['banks']))

        findings.append("Peak core temperature: {:.1f} C ({})".format(
            hottest_core_val, hottest_core))
        if hottest_bank:
            findings.append("Peak bank temperature: {:.1f} C ({})".format(
                hottest_bank_val, hottest_bank))

        if core_agg['max'] > bank_agg['max']:
            diff = core_agg['max'] - bank_agg['max']
            findings.append("Cores run {:.1f} C hotter than memory banks on average peak".format(diff))
        elif bank_agg['max'] > core_agg['max']:
            diff = bank_agg['max'] - core_agg['max']
            findings.append("Memory banks run {:.1f} C hotter than cores on average peak".format(diff))

        total_violations = core_violations['total_epochs'] + bank_violations['total_epochs']
        if total_violations > 0:
            findings.append("[!] {} epoch(s) with thermal violations above {} C".format(
                total_violations, threshold))
        else:
            findings.append("[OK] No thermal violations (all below {} C)".format(threshold))

    if power_trace and power_trace['cores']:
        core_pow_agg = get_aggregate_stats(power_trace, power_trace['cores'])
        total_avg = core_pow_agg['avg'] * len(power_trace['cores'])
        if power_trace['banks']:
            bank_pow_agg = get_aggregate_stats(power_trace, power_trace['banks'])
            total_avg += bank_pow_agg['avg'] * len(power_trace['banks'])
        findings.append("Estimated total average power: {:.2f} W".format(total_avg))

    for i, finding in enumerate(findings, 1):
        print("  {}. {}".format(i, finding))

    print("\n{}\n".format(THICK_SEP))

    return {
        'dir': result_dir,
        'name': dir_name,
        'temp_trace': temp_trace,
        'power_trace': power_trace,
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
        help="Temperature threshold (C) for violation detection (default: 80)"
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

    # Route to single or comparison mode
    if len(valid_dirs) == 1:
        generate_single_report(valid_dirs[0], threshold=args.threshold)
    else:
        # TODO: Comparison mode (commit 9)
        for d in valid_dirs:
            generate_single_report(d, threshold=args.threshold)


if __name__ == '__main__':
    main()

