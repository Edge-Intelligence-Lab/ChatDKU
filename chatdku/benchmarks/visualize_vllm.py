import argparse
from pathlib import Path
import os
import re
import sys
import json
import matplotlib.pyplot as plt


def extract_qps_and_filenames(directory):
    filenames = []
    qpss = []

    # List all files in the directory
    for filename in os.listdir(directory):
        if filename.endswith(".json"):  # Assuming only JSON files are of interest
            # Use a regular expression to find the floating-point number before 'qps'
            match = re.search(r"(\d+\.\d+)qps", filename)
            if match:
                qps = float(match.group(1))
                filenames.append(filename)
                qpss.append(qps)

    return filenames, qpss


def visualize_ttft_tpot_throughput(filenames, qpss, directory, output_path):
    # Prepare data structures for TTFT, TPOT, Request Throughput, and Output Throughput
    ttft_mean, ttft_median, ttft_p99 = [], [], []
    tpot_mean, tpot_median, tpot_p99 = [], [], []
    request_throughput, output_throughput = [], []

    # Sort filenames and qpss based on ascending QPS values
    qpss, filenames = zip(*sorted(zip(qpss, filenames)))

    # Loop through each filename and extract the relevant data
    for filename in filenames:
        # Construct the full file path
        file_path = os.path.join(directory, filename)

        # Open and load the JSON file
        with open(file_path, "r") as f:
            data = json.load(f)

        # Extract TTFT and TPOT metrics
        ttft_mean.append(data.get("mean_ttft_ms", None))
        ttft_median.append(data.get("median_ttft_ms", None))
        ttft_p99.append(data.get("p99_ttft_ms", None))

        tpot_mean.append(data.get("mean_tpot_ms", None))
        tpot_median.append(data.get("median_tpot_ms", None))
        tpot_p99.append(data.get("p99_tpot_ms", None))

        # Extract throughput metrics
        request_throughput.append(data.get("request_throughput", None))
        output_throughput.append(data.get("output_throughput", None))

    # Create a 2x2 subplot grid
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))

    # Plot for TTFT
    axs[0, 0].plot(qpss, ttft_mean, marker="o", label="Mean TTFT")
    axs[0, 0].plot(qpss, ttft_median, marker="s", label="Median TTFT")
    axs[0, 0].plot(qpss, ttft_p99, marker="^", label="P99 TTFT")
    axs[0, 0].set_xlabel("QPS")
    axs[0, 0].set_ylabel("Time to First Token (ms)")
    axs[0, 0].set_title("TTFT (Time to First Token)")
    axs[0, 0].legend()
    axs[0, 0].grid(True)

    # Plot for TPOT
    axs[0, 1].plot(qpss, tpot_mean, marker="o", label="Mean TPOT")
    axs[0, 1].plot(qpss, tpot_median, marker="s", label="Median TPOT")
    axs[0, 1].plot(qpss, tpot_p99, marker="^", label="P99 TPOT")
    axs[0, 1].set_xlabel("QPS")
    axs[0, 1].set_ylabel("Time per Output Token (ms)")
    axs[0, 1].set_title("TPOT (Time per Output Token)")
    axs[0, 1].legend()
    axs[0, 1].grid(True)

    # Plot for Request Throughput
    axs[1, 0].plot(
        qpss, request_throughput, marker="o", color="b", label="Request Throughput"
    )
    axs[1, 0].set_xlabel("QPS")
    axs[1, 0].set_ylabel("Throughput (requests/s)")
    axs[1, 0].set_title("Request Throughput")
    axs[1, 0].legend()
    axs[1, 0].grid(True)

    # Plot for Output Throughput
    axs[1, 1].plot(
        qpss, output_throughput, marker="o", color="g", label="Output Throughput"
    )
    axs[1, 1].set_xlabel("QPS")
    axs[1, 1].set_ylabel("Throughput (tokens/s)")
    axs[1, 1].set_title("Output Throughput")
    axs[1, 1].legend()
    axs[1, 1].grid(True)

    # Adjust layout and save the plots to an SVG file
    plt.tight_layout()
    plt.savefig(output_path, format="svg")


if __name__ == "__main__":
    # Use argparse for command-line argument parsing
    parser = argparse.ArgumentParser(
        description="Visualize TTFT and TPOT from JSON files."
    )
    parser.add_argument("directory", type=Path, help="Directory containing JSON files.")
    parser.add_argument(
        "output_file", type=str, help="Output filename for the SVG plot."
    )

    # Parse the arguments
    args = parser.parse_args()

    # Ensure the directory exists and is a directory
    if not args.directory.is_dir():
        print(f"Error: {args.directory} is not a valid directory")
        sys.exit(1)

    # Extract the QPS values and filenames from the directory
    filenames, qpss = extract_qps_and_filenames(args.directory)

    # Visualize and save the plot to the output file
    visualize_ttft_tpot_throughput(filenames, qpss, args.directory, args.output_file)
