#!/usr/bin/env python3

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
from typing import Tuple, List
import base64
from io import BytesIO

def load_data(client_log: str, server_log: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load and preprocess client and server logs"""
    client_df = pd.read_csv(client_log)
    server_df = pd.read_csv(server_log)
    
    # Convert timestamp columns to datetime
    for df in [client_df, server_df]:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return client_df, server_df

def calculate_metrics(client_df: pd.DataFrame, server_df: pd.DataFrame) -> dict:
    """Calculate various network performance metrics"""
    metrics = {}
    
    # Calculate RTT statistics
    metrics['rtt_mean'] = client_df['rtt_ms'].mean()
    metrics['rtt_std'] = client_df['rtt_ms'].std()
    metrics['rtt_min'] = client_df['rtt_ms'].min()
    metrics['rtt_max'] = client_df['rtt_ms'].max()
    metrics['rtt_p95'] = client_df['rtt_ms'].quantile(0.95)
    metrics['rtt_p99'] = client_df['rtt_ms'].quantile(0.99)
    
    # Calculate packet loss
    total_packets = len(client_df)
    received_packets = len(server_df)
    metrics['packet_loss_rate'] = (total_packets - received_packets) / total_packets * 100
    
    # Calculate throughput
    duration = (client_df['timestamp'].max() - client_df['timestamp'].min()).total_seconds()
    total_bytes = client_df['sequence_number'].count() * 1400  # Assuming 1400 bytes per packet
    metrics['throughput_mbps'] = (total_bytes * 8) / (duration * 1_000_000)
    
    # Calculate jitter (standard deviation of RTT)
    metrics['jitter_ms'] = client_df['rtt_ms'].std()
    
    return metrics

def plot_to_base64(plt_figure):
    """Convert matplotlib figure to base64 string"""
    buf = BytesIO()
    plt_figure.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    img_str = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(plt_figure)
    return img_str

def plot_rtt_distribution(client_df: pd.DataFrame) -> str:
    """Plot RTT distribution and return as base64 string"""
    plt.figure(figsize=(10, 6))
    plt.hist(client_df['rtt_ms'], bins=50, density=True)
    plt.title('RTT Distribution')
    plt.xlabel('RTT (ms)')
    plt.ylabel('Density')
    plt.grid(True)
    return plot_to_base64(plt.gcf())

def plot_throughput_over_time(client_df: pd.DataFrame) -> str:
    """Plot throughput over time and return as base64 string"""
    # Calculate throughput for each second
    client_df['second'] = client_df['timestamp'].dt.floor('s')
    throughput = client_df.groupby('second').size() * 1400 * 8 / 1_000_000  # Mbps
    
    plt.figure(figsize=(12, 6))
    throughput.plot()
    plt.title('Throughput Over Time')
    plt.xlabel('Time')
    plt.ylabel('Throughput (Mbps)')
    plt.grid(True)
    return plot_to_base64(plt.gcf())

def plot_packet_loss(client_df: pd.DataFrame, server_df: pd.DataFrame) -> str:
    """Plot packet loss over time and return as base64 string"""
    # Calculate packet loss for each second
    client_df['second'] = client_df['timestamp'].dt.floor('s')
    server_df['second'] = server_df['timestamp'].dt.floor('s')
    
    client_packets = client_df.groupby('second').size()
    server_packets = server_df.groupby('second').size()
    
    # Align the series and calculate loss
    all_seconds = pd.concat([client_packets, server_packets]).index.unique()
    client_packets = client_packets.reindex(all_seconds, fill_value=0)
    server_packets = server_packets.reindex(all_seconds, fill_value=0)
    
    loss_rate = (client_packets - server_packets) / client_packets * 100
    
    plt.figure(figsize=(12, 6))
    loss_rate.plot()
    plt.title('Packet Loss Rate Over Time')
    plt.xlabel('Time')
    plt.ylabel('Loss Rate (%)')
    plt.grid(True)
    return plot_to_base64(plt.gcf())

def plot_flow_metrics(client_df: pd.DataFrame) -> Tuple[str, str]:
    """Plot metrics for each flow and return as base64 strings"""
    # Calculate metrics per flow
    flow_metrics = client_df.groupby('flow_id').agg({
        'rtt_ms': ['mean', 'std', 'min', 'max'],
        'sequence_number': 'count'
    }).reset_index()
    
    # Plot RTT statistics per flow
    plt.figure(figsize=(12, 6))
    plt.bar(flow_metrics['flow_id'], flow_metrics[('rtt_ms', 'mean')])
    plt.errorbar(flow_metrics['flow_id'], flow_metrics[('rtt_ms', 'mean')],
                yerr=flow_metrics[('rtt_ms', 'std')], fmt='none', color='black')
    plt.title('Average RTT per Flow')
    plt.xlabel('Flow ID')
    plt.ylabel('RTT (ms)')
    plt.grid(True)
    rtt_img = plot_to_base64(plt.gcf())
    
    # Plot packets per flow
    plt.figure(figsize=(12, 6))
    plt.bar(flow_metrics['flow_id'], flow_metrics[('sequence_number', 'count')])
    plt.title('Packets per Flow')
    plt.xlabel('Flow ID')
    plt.ylabel('Number of Packets')
    plt.grid(True)
    packets_img = plot_to_base64(plt.gcf())
    
    return rtt_img, packets_img

def generate_html_report(metrics: dict, images: dict, output_dir: str):
    """Generate an HTML report with all metrics and plots"""
    html_content = f"""
    <html>
    <head>
        <title>Network Performance Test Results</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .metric {{ margin: 10px 0; }}
            .plot {{ margin: 20px 0; }}
            .plot img {{ max-width: 100%; height: auto; }}
            .container {{ max-width: 1200px; margin: 0 auto; }}
            .metric-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
            .metric-card {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
            .metric-value {{ font-size: 1.2em; font-weight: bold; }}
            .metric-label {{ color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Network Performance Test Results</h1>
            
            <h2>Summary Metrics</h2>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-label">Average RTT</div>
                    <div class="metric-value">{metrics['rtt_mean']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">RTT Standard Deviation</div>
                    <div class="metric-value">{metrics['rtt_std']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Minimum RTT</div>
                    <div class="metric-value">{metrics['rtt_min']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Maximum RTT</div>
                    <div class="metric-value">{metrics['rtt_max']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">95th Percentile RTT</div>
                    <div class="metric-value">{metrics['rtt_p95']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">99th Percentile RTT</div>
                    <div class="metric-value">{metrics['rtt_p99']:.2f} ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Packet Loss Rate</div>
                    <div class="metric-value">{metrics['packet_loss_rate']:.2f}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Average Throughput</div>
                    <div class="metric-value">{metrics['throughput_mbps']:.2f} Mbps</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Jitter</div>
                    <div class="metric-value">{metrics['jitter_ms']:.2f} ms</div>
                </div>
            </div>
            
            <h2>Plots</h2>
            <div class="plot">
                <h3>RTT Distribution</h3>
                <img src="data:image/png;base64,{images['rtt_dist']}" alt="RTT Distribution">
            </div>
            <div class="plot">
                <h3>Throughput Over Time</h3>
                <img src="data:image/png;base64,{images['throughput']}" alt="Throughput Over Time">
            </div>
            <div class="plot">
                <h3>Packet Loss Rate</h3>
                <img src="data:image/png;base64,{images['loss']}" alt="Packet Loss Rate">
            </div>
            <div class="plot">
                <h3>Flow Metrics</h3>
                <img src="data:image/png;base64,{images['flow_rtt']}" alt="Flow RTT">
                <img src="data:image/png;base64,{images['flow_packets']}" alt="Flow Packets">
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(os.path.join(output_dir, 'report.html'), 'w') as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description='Analyze UDP traffic test results')
    parser.add_argument('--client-log', type=str, required=True,
                      help='Path to client log file')
    parser.add_argument('--server-log', type=str, required=True,
                      help='Path to server log file')
    parser.add_argument('--output-dir', type=str, default='results',
                      help='Directory to save analysis results')
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Load data
    client_df, server_df = load_data(args.client_log, args.server_log)
    
    # Calculate metrics
    metrics = calculate_metrics(client_df, server_df)
    
    # Generate plots and convert to base64
    images = {
        'rtt_dist': plot_rtt_distribution(client_df),
        'throughput': plot_throughput_over_time(client_df),
        'loss': plot_packet_loss(client_df, server_df)
    }
    
    # Get flow metrics plots
    flow_rtt_img, flow_packets_img = plot_flow_metrics(client_df)
    images['flow_rtt'] = flow_rtt_img
    images['flow_packets'] = flow_packets_img
    
    # Generate HTML report
    generate_html_report(metrics, images, args.output_dir)
    
    print(f"Analysis complete. Results saved in {args.output_dir}")
    print(f"Open {os.path.join(args.output_dir, 'report.html')} in your web browser to view the results.")

if __name__ == '__main__':
    main() 