#!/usr/bin/env python3
import sys
import os
import argparse
import matplotlib.pyplot as plt

def main():
    parser = argparse.ArgumentParser(description="Plot a trace (.trace) file.")
    parser.add_argument("trace_file", help="Path to the trace file")
    parser.add_argument("-o", "--output", default="trace_to_plot.png", help="Output image file name (default: trace_to_plot.png)")
    parser.add_argument("--epoch-us", default=None, help="Sampling interval in microseconds")
    args = parser.parse_args()

    if not os.path.exists(args.trace_file):
        print(f"Error: Trace file '{args.trace_file}' not found.")
        sys.exit(1)

    # Read data
    headers = []
    data_matrix = []
    
    print(f"\nReading trace file: {args.trace_file}")
    with open(args.trace_file, 'r') as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            if idx == 0:
                headers = parts
            else:
                try:
                    row_values = [float(val) for val in parts]
                    if len(row_values) == len(headers):
                        data_matrix.append(row_values)
                except ValueError:
                    continue

    if not headers or not data_matrix:
        print("Error: The file is empty or improperly formatted.")
        sys.exit(1)

    print(f"\nTIME SAMPLES: {len(data_matrix)}")

    # Sort out cores and banks
    core_indices = [(h, i) for i, h in enumerate(headers) if h.startswith('C_')]
    bank_indices = [(h, i) for i, h in enumerate(headers) if h.startswith('B_')]

    if not core_indices and not bank_indices:
        print("Error: No headers starting with 'C_' (Cores) or 'B_' (Banks) were found.")
        sys.exit(1)

    print(f"CORES: {len(core_indices)}")
    print(f"BANKS: {len(bank_indices)}")

    # Time series construction (min, avg, max dynamically at each time step)
    min_core_series = []
    avg_core_series = []
    max_core_series = []
    
    min_bank_series = []
    avg_bank_series = []
    max_bank_series = []

    for row in data_matrix:
        if core_indices:
            core_vals = [row[i] for _, i in core_indices]
            min_core_series.append(min(core_vals))
            avg_core_series.append(sum(core_vals) / len(core_vals))
            max_core_series.append(max(core_vals))
            
        if bank_indices:
            bank_vals = [row[i] for _, i in bank_indices]
            min_bank_series.append(min(bank_vals))
            avg_bank_series.append(sum(bank_vals) / len(bank_vals))
            max_bank_series.append(max(bank_vals))

    # Plotting
    print("\nGenerating plot...")
    plt.figure(figsize=(12, 7))
    plt.style.use('dark_background')
    
    time_steps = range(len(data_matrix))
    if args.epoch_us:
        time_steps = [x * int(args.epoch_us) / 1000 for x in range(len(data_matrix))]

    unit = "Unit"
    if "temp" in args.trace_file:
        unit = "Temperature"
    elif "power" in args.trace_file:
        unit = "Power"

    if core_indices:
        plt.plot(time_steps, min_core_series, label=f"Min Core {unit}", color='cyan', linestyle='-', linewidth=2)
        plt.plot(time_steps, max_core_series, label=f"Max Core {unit}", color='blue', linestyle='-', linewidth=2)
        plt.plot(time_steps, avg_core_series, label=f"Avg Core {unit}", color='dodgerblue', linestyle='--', linewidth=2)

    if bank_indices:
        plt.plot(time_steps, min_bank_series, label=f"Min Bank {unit}", color='lime', linestyle='-', linewidth=2)
        plt.plot(time_steps, max_bank_series, label=f"Max Bank {unit}", color='green', linestyle='-', linewidth=2)
        plt.plot(time_steps, avg_bank_series, label=f"Avg Bank {unit}", color='forestgreen', linestyle='--', linewidth=2)

    plt.title(f'Core & Bank {unit} Analytics')
    if args.epoch_us:
        plt.xlabel('Time (in ms)')
    else:
        plt.xlabel('Simulation Epoch')
    plt.ylabel(unit)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()

    # Save
    plt.savefig(args.output, dpi=150)
    print(f"Plot successfully saved as '{args.output}'\n")

if __name__ == "__main__":
    main()
