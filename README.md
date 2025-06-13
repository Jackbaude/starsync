# UDP Traffic Testing System

A high-performance UDP-based traffic testing system for measuring network performance metrics.

## Features

- Multi-threaded UDP client and server
- Configurable number of parallel flows
- Detailed packet-level metrics collection
- Real-time performance monitoring
- Post-processing analysis and visualization
- Support for high-throughput testing (200+ Mbps)

## Requirements

- Python 3.8+
- Linux OS (recommended for optimal performance)
- Required Python packages (see requirements.txt)

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the Server

```bash
python udp_server.py --port 5000 --log-file server_log.csv
```

### Running the Client

```bash
python udp_client.py --server-ip 127.0.0.1 --server-port 5000 --flows 4 --duration 10 --rate 50
```

### Analyzing Results

```bash
python analyze_results.py --client-log client_log.csv --server-log server_log.csv
```

## Configuration Options

### Server Options
- `--port`: UDP port to listen on (default: 5000)
- `--log-file`: Output file for server logs (default: server_log.csv)

### Client Options
- `--server-ip`: Server IP address (default: 127.0.0.1)
- `--server-port`: Server port (default: 5000)
- `--flows`: Number of parallel flows (default: 4)
- `--duration`: Test duration in seconds (default: 10)
- `--rate`: Target rate per flow in Mbps (default: 50)
- `--packet-size`: UDP packet size in bytes (default: 1400)
- `--log-file`: Output file for client logs (default: client_log.csv)

## Output

The system generates two main log files:
1. Server log: Contains packet reception and ACK transmission details
2. Client log: Contains packet transmission and ACK reception details

Analysis results are saved in the `results` directory, including:
- Throughput over time
- Packet loss statistics
- RTT distribution
- Jitter analysis
- Flow-specific metrics

## Performance Considerations

- For optimal performance, run on Linux systems
- Adjust system UDP buffer sizes if needed
- Consider using multiple network interfaces for higher throughput
- Monitor system resources during high-load tests 