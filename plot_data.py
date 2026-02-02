"""
Plot anomalies and raw data from CSV files.
"""

import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import argparse


def convert_timestamp(timestamp_ms):
    """Converts Unix timestamp in milliseconds to a readable datetime format"""
    timestamp_sec = timestamp_ms / 1000
    dt = datetime.fromtimestamp(timestamp_sec)
    return dt


def plot_raw_data(csv_file, value_name='Value', out_file=None):
    """Plots raw data values"""
    
    print(f"Loading raw data from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Convert timestamps
    df['datetime'] = df['timestamp'].apply(convert_timestamp)
    
    # Create plot
    plt.figure(figsize=(14, 6))
    plt.plot(df['datetime'], df['value'], marker='o', linestyle='-', 
             markersize=3, linewidth=1, color='steelblue', label=value_name)
    
    # Formatting
    plt.title(f'{value_name} - Raw Data Plot', fontsize=14, fontweight='bold')
    plt.xlabel('Time', fontsize=12)
    plt.ylabel(value_name, fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    plt.tight_layout()
    
    if out_file:
        plt.savefig(out_file)
        print(f"Plot saved to {out_file}")
    else:
        plt.show()


def plot_anomalies(csv_file, value_name='Value', show_anomaly_values=False, out_file=None):
    """Plots data with marked anomalies and background shading"""
    
    print(f"Loading anomaly data from {csv_file}...")
    df = pd.read_csv(csv_file)
    
    # Convert timestamps
    df['datetime'] = df['timestamp'].apply(convert_timestamp)
    
    # Convert boolean values (if needed)
    df['isAnomaly'] = df['isAnomaly'].astype(bool)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Find continuous anomaly regions
    anomaly_regions = []
    in_anomaly = False
    start_idx = None
    
    for idx, row in enumerate(df.itertuples(index=False)):
        if row.isAnomaly and not in_anomaly:
            # Start of an anomaly region
            in_anomaly = True
            start_idx = idx
        elif not row.isAnomaly and in_anomaly:
            # End of an anomaly region
            in_anomaly = False
            anomaly_regions.append((start_idx, idx - 1))
    
    # Handle case where data ends with an anomaly
    if in_anomaly:
        anomaly_regions.append((start_idx, len(df) - 1))
    
    # Add red background for anomaly regions
    for start_idx, end_idx in anomaly_regions:
        start_time = df.iloc[start_idx]['datetime']
        end_time = df.iloc[end_idx]['datetime']
        ax.axvspan(start_time, end_time, alpha=0.2, color='red', zorder=0)
    
    # Plot all values as continuous line
    ax.plot(df['datetime'], df['value'], marker='o', linestyle='-', 
            markersize=3, linewidth=1, color='steelblue', label=value_name, zorder=2)
    
    # Color anomaly points differently
    anomalies = df[df['isAnomaly']]
    ax.scatter(anomalies['datetime'], anomalies['value'], 
              color='red', s=80, marker='o', label='Anomaly', zorder=3)
    
    # Optionally plot anomaly scores
    if show_anomaly_values:
        # Create secondary y-axis for anomaly scores
        ax2 = ax.twinx()
        
        # Plot anomaly score as line with markers
        ax2.plot(df['datetime'], df['anomalyScore'], marker='s', linestyle='--', 
                markersize=3, linewidth=1, color='orange', label='Anomaly Score', zorder=2, alpha=0.7)
        
        # Format secondary axis
        ax2.set_ylabel('Anomaly Score', fontsize=12, color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        
        # Combine legends from both axes
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Formatting
    ax.set_title(f'{value_name} with Anomaly Detection', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel(value_name, fontsize=12)
    ax.grid(True, alpha=0.3)
    
    if not show_anomaly_values:
        ax.legend()
    
    plt.tight_layout()
    
    if out_file:
        plt.savefig(out_file)
        print(f"Plot saved to {out_file}")
    else:
        plt.show()


def main():
    """Main function with argument parser"""
    
    parser = argparse.ArgumentParser(
        description='Plots data from CSV files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python plot_data.py --raw cpu_usage_raw.csv --value-name "CPU Usage"
  python plot_data.py --anomalies cpu_anomalies.csv --value-name "CPU Usage"
  python plot_data.py --anomalies cpu_anomalies.csv --value-name "CPU Usage" --show-anomaly-values
  python plot_data.py --raw data.csv --value-name "Temperature"
        """
    )
    
    # Define arguments
    parser.add_argument('--raw', type=str, metavar='FILE',
                       help='Plots raw data')
    parser.add_argument('--anomalies', type=str, metavar='FILE',
                       help='Plots data with anomaly detection')
    parser.add_argument('--value-name', type=str, metavar='NAME', default='Value',
                       help='Name of the values being plotted (e.g., CPU Usage, Memory, Temperature)')
    parser.add_argument('--show-anomaly-values', action='store_true',
                       help='Show anomaly scores on a secondary y-axis')
    parser.add_argument('--out', type=str, metavar='FILE',
                       help='Output file to save the plot')
    
    args = parser.parse_args()
    
    # At least one option must be chosen
    if not args.raw and not args.anomalies:
        print("Error: At least one of --raw or --anomalies must be specified")
        print()
        parser.print_help()
        return
    
    # Plot data
    if args.raw:
        plot_raw_data(args.raw, args.value_name, args.out)
    
    if args.anomalies:
        plot_anomalies(args.anomalies, args.value_name, args.show_anomaly_values, args.out)


if __name__ == "__main__":
    main()
