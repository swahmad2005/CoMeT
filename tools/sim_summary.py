#!/usr/bin/env python3
"""
sim_summary.py - CoMeT Simulation Summary Report Generator

This tool parses raw `.trace` outputs from CoMeT thermal/power simulations
and generates a human-readable summary report. It computes peak temperatures, 
identifies thermal hotspots, checks for threshold violations, and compares 
multiple architecture configurations.

Usage:
  # Analyze a single simulation result
  python sim_summary.py comet_results/gainestown_3D

  # Compare multiple configurations side-by-side
  python sim_summary.py comet_results/gainestown_DDR comet_results/gainestown_3D

  # Specify a custom temperature threshold (default is 80.0 C)
  python sim_summary.py comet_results/gainestown_3D --threshold 85.0

  # Export the computed summary statistics to a CSV file
  python sim_summary.py comet_results/gainestown_3D --csv results.csv
"""

import sys
import os
import argparse
import csv


def parse_trace_file(filepath):
    """
    Parse a CoMeT .trace file into headers, data, and component indices.

    Args:
        filepath (str): Path to the .trace file.

    Returns:
        dict: A dictionary containing 'headers' (list), 'data' (2D list),
              'cores' (list of tuples), 'banks' (list of tuples), and
              'epochs' (int). Returns None if the file is invalid or missing.
    """
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
    """
    Compute min, max, mean, and standard deviation for a list of numbers.

    Args:
        values (list of float): The list of numerical values.

    Returns:
        dict: A dictionary with 'min', 'max', 'avg', and 'stddev' keys.
    """
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

ARCH_LABELS = {
    'gainestown_DDR': '2D Off-chip DDR Memory',
    'gainestown_2_5D': '2.5D Interposer',
    'gainestown_3Dmem': '3D Stacked Memory (Logic base)',
    'gainestown_3D': '3D Stacked (Cores on Memory)'
}


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
    config_name = ARCH_LABELS.get(dir_name, dir_name)

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
    print("  Configuration:  {}".format(config_name))

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
        'name': config_name,
        'temp_trace': temp_trace,
        'power_trace': power_trace,
    }


# ─── Comparison Report ─────────────────────────────────────────────────────────

def generate_comparison_report(result_dirs, threshold=80.0):
    """Generate a comparative summary report across multiple simulation directories."""
    reports = []
    
    for d in result_dirs:
        # We temporarily silence the single-report printouts to just extract data
        # In a real refactor we'd split parsing from printing, but this works
        temp_file = os.path.join(d, 'combined_temperature.trace')
        power_file = os.path.join(d, 'combined_power.trace')
        
        temp_trace = parse_trace_file(temp_file)
        power_trace = parse_trace_file(power_file)
        
        dir_name = os.path.basename(os.path.normpath(d))
        config_name = ARCH_LABELS.get(dir_name, dir_name)
        
        if temp_trace or power_trace:
            reports.append({
                'dir': d,
                'name': config_name,
                'temp_trace': temp_trace,
                'power_trace': power_trace
            })
            
    if not reports:
        print("Error: No valid simulation data found in any provided directory.")
        return None

    # Report header
    print("\n{}".format(THICK_SEP))
    print("  CoMeT COMPARATIVE SIMULATION REPORT")
    print(THICK_SEP)

    # Configuration Overview
    print("\n  {:<24} {:>8} {:>8} {:>8}".format('Configuration', 'Epochs', 'Cores', 'Banks'))
    print("  {} {} {} {}".format("-" * 24, "-" * 8, "-" * 8, "-" * 8))
    for r in reports:
        if r['temp_trace']:
            print("  {:<24} {:>8} {:>8} {:>8}".format(
                r['name'], r['temp_trace']['epochs'], 
                len(r['temp_trace']['cores']), len(r['temp_trace']['banks'])))
        else:
            print("  {:<24} {:>8} {:>8} {:>8}".format(r['name'], "N/A", "N/A", "N/A"))

    # Core Temperature Comparison
    print_header("CORE TEMPERATURE COMPARISON (C)")
    print("  {:<24} {:>8} {:>8} {:>8} {:>8}  {:<8}".format(
        'Config', 'Min', 'Avg', 'Max', 'StdDev', 'Hottest'))
    print("  {} {} {} {} {}  {}".format(
        "-" * 24, "-" * 8, "-" * 8, "-" * 8, "-" * 8, "-" * 8))
        
    hot_configs = []
    min_avg = float('inf')
    max_avg = -float('inf')
    coolest_config = None
    hottest_config = None
    
    for r in reports:
        if r['temp_trace']:
            agg = get_aggregate_stats(r['temp_trace'], r['temp_trace']['cores'])
            core_stats = get_component_stats(r['temp_trace'], r['temp_trace']['cores'])
            hottest_name, _ = find_hotspot(core_stats)
            
            warning = "  [!] HOT" if agg['max'] > threshold else ""
            if agg['max'] > threshold:
                hot_configs.append(r['name'])
                
            if agg['avg'] < min_avg:
                min_avg = agg['avg']
                coolest_config = (r['name'], agg)
            if agg['avg'] > max_avg:
                max_avg = agg['avg']
                hottest_config = (r['name'], agg)

            print("  {:<24} {:>8.1f} {:>8.1f} {:>8.1f} {:>8.1f}  {:<8}{}".format(
                r['name'], agg['min'], agg['avg'], agg['max'], agg['stddev'], 
                hottest_name, warning))

    # Power Comparison
    power_reports = [r for r in reports if r['power_trace']]
    if power_reports:
        print_header("ESTIMATED POWER CONSUMPTION (W)")
        print("  {:<24} {:>10} {:>10} {:>12}".format(
            'Config', 'Core Pwr', 'Bank Pwr', 'Total Pwr'))
        print("  {} {} {} {}".format("-" * 24, "-" * 10, "-" * 10, "-" * 12))
        
        for r in power_reports:
            p_trace = r['power_trace']
            core_pow = 0; bank_pow = 0
            if p_trace['cores']:
                core_agg = get_aggregate_stats(p_trace, p_trace['cores'])
                core_pow = core_agg['avg'] * len(p_trace['cores'])
            if p_trace['banks']:
                bank_agg = get_aggregate_stats(p_trace, p_trace['banks'])
                bank_pow = bank_agg['avg'] * len(p_trace['banks'])
                
            print("  {:<24} {:>10.2f} {:>10.2f} {:>12.2f}".format(
                r['name'], core_pow, bank_pow, core_pow + bank_pow))

    # Key Findings
    print_header("KEY FINDINGS")
    if hottest_config:
        print("  1. Hottest configuration: {} (avg {:.1f} C, peak {:.1f} C)".format(
            hottest_config[0], hottest_config[1]['avg'], hottest_config[1]['max']))
        if coolest_config and coolest_config[0] != hottest_config[0]:
            print("  2. Coolest configuration: {} (avg {:.1f} C, peak {:.1f} C)".format(
                coolest_config[0], coolest_config[1]['avg'], coolest_config[1]['max']))
            diff = hottest_config[1]['avg'] - coolest_config[1]['avg']
            print("  3. Temperature difference between hottest and coolest: {:.1f} C average".format(diff))
    
    if hot_configs:
        print("  4. [!] Configurations with core thermal violations: {}".format(", ".join(hot_configs)))
    else:
        print("  4. [OK] No configuration experienced thermal violations above {} C.".format(threshold))

    print("\n{}\n".format(THICK_SEP))
    return reports


# --- CSV Export ---------------------------------------------------------------

def export_csv(reports, output_path, threshold):
    """Export summary statistics to a CSV file."""
    if not isinstance(reports, list):
        reports = [reports]

    if not reports:
        return

    try:
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            # Header
            writer.writerow([
                'Configuration', 'Epochs', 'Cores', 'Banks', 
                'Core_Temp_Avg', 'Core_Temp_Peak', 'Hottest_Core', 'Core_Violations',
                'Bank_Temp_Avg', 'Bank_Temp_Peak', 'Hottest_Bank', 'Bank_Violations',
                'Est_Total_Power_W'
            ])
            
            for r in reports:
                row = [r['name']]
                
                temp_trace = r.get('temp_trace')
                power_trace = r.get('power_trace')
                
                if temp_trace:
                    row.extend([temp_trace['epochs'], len(temp_trace['cores']), len(temp_trace['banks'])])
                    
                    # Core stats
                    core_agg = get_aggregate_stats(temp_trace, temp_trace['cores'])
                    core_stats = get_component_stats(temp_trace, temp_trace['cores'])
                    hottest_core, _ = find_hotspot(core_stats)
                    core_viols = count_violations(temp_trace, temp_trace['cores'], threshold)
                    
                    row.extend([
                        round(core_agg['avg'], 2), 
                        round(core_agg['max'], 2), 
                        hottest_core, 
                        core_viols['total_epochs']
                    ])
                    
                    # Bank stats
                    if temp_trace['banks']:
                        bank_agg = get_aggregate_stats(temp_trace, temp_trace['banks'])
                        bank_stats = get_component_stats(temp_trace, temp_trace['banks'])
                        hottest_bank, _ = find_hotspot(bank_stats)
                        bank_viols = count_violations(temp_trace, temp_trace['banks'], threshold)
                        
                        row.extend([
                            round(bank_agg['avg'], 2), 
                            round(bank_agg['max'], 2), 
                            hottest_bank, 
                            bank_viols['total_epochs']
                        ])
                    else:
                        row.extend(['', '', '', ''])
                else:
                    row.extend(['', '', '', '', '', '', '', '', '', '', ''])
                    
                # Power stats
                est_power = ''
                if power_trace:
                    total_pow = 0
                    if power_trace['cores']:
                        c_pow = get_aggregate_stats(power_trace, power_trace['cores'])
                        total_pow += c_pow['avg'] * len(power_trace['cores'])
                    if power_trace['banks']:
                        b_pow = get_aggregate_stats(power_trace, power_trace['banks'])
                        total_pow += b_pow['avg'] * len(power_trace['banks'])
                    est_power = round(total_pow, 2)
                    
                row.append(est_power)
                writer.writerow(row)
                
        print("  [OK] CSV summary exported to: {}".format(output_path))
    except Exception as e:
        print("  ERROR: Failed to write CSV file: {}".format(e))


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
    reports = []
    if len(valid_dirs) == 1:
        res = generate_single_report(valid_dirs[0], threshold=args.threshold)
        if res:
            reports.append(res)
    else:
        res = generate_comparison_report(valid_dirs, threshold=args.threshold)
        if res:
            reports = res

    if args.csv and reports:
        export_csv(reports, args.csv, threshold=args.threshold)


if __name__ == '__main__':
    main()

