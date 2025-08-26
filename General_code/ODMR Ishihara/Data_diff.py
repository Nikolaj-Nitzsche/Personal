#!/usr/bin/env python3
"""
Script to compute photoluminescence (PL) difference between two 3D measurement folders:
RF-off and RF-on. Each folder contains .npy arrays and corresponding .json metadata files
for a 40x40 grid of x-scans. Filenames include y and z coordinates and a timestamp.

Usage:
    python compute_pl_difference.py /path/to/rf_off /path/to/rf_on /path/to/output

The script matches each RF-off file by its y,z coordinates to the corresponding RF-on file
(ignoring timestamp differences), computes `PL_off - PL_on`, and writes the results
using the original scan filenames (so that downstream code expecting "X_PL_scan" in the
filenames will pick up the difference arrays). Metadata JSON is updated with reference
fields and written under the same JSON filename.
"""
import argparse
import json
import re
from pathlib import Path
import numpy as np

def find_matching_file(folder_on: Path, y: str, z: str) -> Path:
    """
    Find the first RF-on .npy file in folder_on matching the y,z coordinates.
    """
    pattern = f"X_PL_scan_y{y}_z{z}_*.npy"
    matches = list(folder_on.glob(pattern))
    return matches[0] if matches else None


def compute_difference(folder_off: Path, folder_on: Path, output_folder: Path):
    output_folder.mkdir(parents=True, exist_ok=True)

    for file_off in sorted(folder_off.glob('X_PL_scan_y*_z*_*.npy')):
        m = re.match(r"X_PL_scan_y(?P<y>[\d\.]+)_z(?P<z>[\d\.]+)_\d+\.npy", file_off.name)
        if not m:
            print(f"Warning: filename {file_off.name} doesn't match expected pattern, skipping.")
            continue

        y, z = m.group('y'), m.group('z')
        file_on = find_matching_file(folder_on, y, z)
        if not file_on:
            print(f"Warning: RF-on file not found for y={y}, z={z}, skipping.")
            continue

        pl_off = np.load(file_off)
        pl_on  = np.load(file_on)
        pl_diff = pl_off - pl_on

        # Save difference array using the original scan filename
        out_npy = output_folder / file_off.name
        np.save(out_npy, pl_diff)

        # Update and save metadata JSON under the same filename
        metadata = {}
        json_off = file_off.with_suffix('.json')
        if json_off.exists():
            metadata = json.loads(json_off.read_text())

        metadata.update({
            'rf_off_file': file_off.name,
            'rf_on_file': file_on.name,
            'difference_computed': True
        })

        out_json = output_folder / json_off.name
        with open(out_json, 'w') as f:
            json.dump(metadata, f, indent=4)


def main():
    parser = argparse.ArgumentParser(
        description='Compute PL difference (RF_off - RF_on) for each x-scan in a 3D grid.'
    )
    parser.add_argument('folder_off',     type=Path, help='Directory with RF-off .npy/.json files')
    parser.add_argument('folder_on',      type=Path, help='Directory with RF-on  .npy/.json files')
    parser.add_argument('output_folder', type=Path, help='Directory to store difference files')
    args = parser.parse_args()

    compute_difference(args.folder_off, args.folder_on, args.output_folder)

if __name__ == '__main__':
    main()
