import argparse
import csv
import sys
from pathlib import Path


def parse_trace(path):
    """Read a CoMeT .trace file. Returns (header, rows)."""
    with open(path, "r") as f:
        lines = [line.rstrip("\n").rstrip("\t") for line in f if line.strip()]

    if not lines:
        raise ValueError(f"{path} is empty")

    header = lines[0].split("\t")
    rows = []
    for i, line in enumerate(lines[1:], start=1):
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ValueError(
                f"{path}: row {i} has {len(cells)} columns, "
                f"expected {len(header)} (header mismatch)"
            )
        rows.append(cells)
    return header, rows


def classify(col_name):
    """Map a column name like 'C_3' or 'B_17' to (component_type, id)."""
    if col_name.startswith("C_"):
        return "core", col_name[2:]
    if col_name.startswith("B_"):
        return "bank", col_name[2:]
    return "other", col_name


def write_wide(header, rows, out_path, epoch_us, include_time):
    """Write CSV with the same shape as the input, optionally with a time column."""
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        if include_time:
            writer.writerow(["time_us"] + header)
            for i, row in enumerate(rows):
                writer.writerow([(i + 1) * epoch_us] + row)
        else:
            writer.writerow(header)
            writer.writerows(rows)


def write_long(header, rows, out_path, epoch_us, value_name):
    """Write tidy CSV: time_us, component_type, component_id, <value_name>."""
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_us", "component_type", "component_id", value_name])
        for i, row in enumerate(rows):
            t = (i + 1) * epoch_us
            for col_name, cell in zip(header, row):
                ctype, cid = classify(col_name)
                writer.writerow([t, ctype, cid, cell])


def main():
    p = argparse.ArgumentParser(
        description="Convert CoMeT .trace files to CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("-i", "--input", required=True, help="Input .trace file")
    p.add_argument(
        "-o", "--output", help="Output .csv file (default: <input>.csv)"
    )
    p.add_argument(
        "--format",
        choices=["wide", "long"],
        default="wide",
        help="Output layout. 'wide' preserves the original column structure; "
        "'long' produces tidy data with one row per (time, component). "
        "Default: wide.",
    )
    p.add_argument(
        "--epoch-us",
        type=float,
        default=1000.0,
        help="Sampling interval in microseconds (default: 1000, matching "
        "CoMeT's default sampling_interval=1000000 ns).",
    )
    p.add_argument(
        "--value-name",
        default="value",
        help="Name of the value column in long format (e.g. 'temperature_c' "
        "or 'power_w'). Default: 'value'.",
    )
    p.add_argument(
        "--no-time",
        action="store_true",
        help="In wide format, omit the computed time_us column.",
    )
    args = p.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"error: input file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output) if args.output else in_path.with_suffix(".csv")

    try:
        header, rows = parse_trace(in_path)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.format == "wide":
        write_wide(header, rows, out_path, args.epoch_us, not args.no_time)
    else:
        write_long(header, rows, out_path, args.epoch_us, args.value_name)

    print(
        f"Converted {in_path} -> {out_path} "
        f"({len(rows)} epochs, {len(header)} components, format={args.format})"
    )


if __name__ == "__main__":
    main()
