import os
import shutil
import argparse
import numpy as np
import json
from glob import glob
from datetime import datetime

def merge_folders(folder1, folder2, output_folder):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    seen_files = set()
    for folder in [folder1, folder2]:
        for file in os.listdir(folder):
            src_path = os.path.join(folder, file)
            if os.path.isdir(src_path): continue
            dest_path = os.path.join(output_folder, file)
            if file in seen_files:
                base, ext = os.path.splitext(file)
                file = f"{base}_copy{ext}"
                dest_path = os.path.join(output_folder, file)
            shutil.copy2(src_path, dest_path)
            seen_files.add(file)
            print(f"Copied {src_path} to {dest_path}")
    print(f"Merging complete. Files saved in: {output_folder}")

def compute_difference_scan(scan1_dir, scan2_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    files1 = sorted(glob(os.path.join(scan1_dir, "*.npy")))

    for file1_path in files1:
        base_name = "_".join(os.path.basename(file1_path).split("_")[:5])
        matching_files2 = glob(os.path.join(scan2_dir, f"{base_name}_*.npy"))
        if not matching_files2:
            print(f"⚠️ No match found for {base_name}")
            continue

        file2_path = matching_files2[0]
        pl1 = np.load(file1_path)
        pl2 = np.load(file2_path)
        diff = pl1 - pl2

        ts1 = float(file1_path.split("_")[-1].split(".")[0])
        ts2 = float(file2_path.split("_")[-1].split(".")[0])
        avg_ts = str(round((ts1 + ts2) / 2))
        out_base = f"{base_name}_{avg_ts}"

        np.save(os.path.join(output_dir, out_base + ".npy"), diff)

        json1_path = file1_path.replace(".npy", ".json")
        if os.path.exists(json1_path):
            with open(json1_path, "r") as f:
                metadata = json.load(f)
            metadata["measurement_type"] = "PL difference"
            metadata["scan1_source"] = file1_path
            metadata["scan2_source"] = file2_path
            with open(os.path.join(output_dir, out_base + ".json"), "w") as f:
                json.dump(metadata, f, indent=4)

    print(f"PL difference scan saved to: {output_dir}")

def combine_into_npz(scan1_dir, scan2_dir, output_file="combined_data.npz"):
    combined_data = {}
    files1 = sorted(glob(os.path.join(scan1_dir, "*.npy")))
    files2 = sorted(glob(os.path.join(scan2_dir, "*.npy")))

    for file in files1:
        key = "scan1_" + "_".join(os.path.basename(file).split("_")[3:5])  # y and z
        combined_data[key] = np.load(file)

    for file in files2:
        key = "scan2_" + "_".join(os.path.basename(file).split("_")[3:5])  # y and z
        combined_data[key] = np.load(file)

    np.savez(output_file, **combined_data)
    print(f"Combined data saved to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge, diff, or combine two scan folders.")
    parser.add_argument('folder1', help="Path to the first folder.")
    parser.add_argument('folder2', help="Path to the second folder.")
    parser.add_argument('output_folder', nargs='?', default=f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        help="Output folder where files will be stored.")
    parser.add_argument('--difference', action='store_true', help="Compute PL difference between scans.")
    parser.add_argument('--combine', action='store_true', help="Combine both scan folders into a .npz file.")

    args = parser.parse_args()

    if args.combine:
        combine_into_npz(args.folder1, args.folder2, os.path.join(args.output_folder, "combined_data.npz"))
    elif args.difference:
        compute_difference_scan(args.folder1, args.folder2, args.output_folder)
    else:
        merge_folders(args.folder1, args.folder2, args.output_folder)
