# UDP Bandwidth Test Tool

A simple tool for testing UDP bandwidth and packet timing between a client and server.

## Requirements

- Python 3.x
- No additional dependencies required

## Usage

### Server

Start the server first:

```bash
python udp_server.py --ip <IP_ADDRESS> --port <PORT> --output_dir <OUTPUT_DIRECTORY>
```

Example:
```bash
python udp_server.py --ip 0.0.0.0 --port 5000 --output_dir logs
```

The server will create CSV log files in the specified output directory containing packet timing information.

### Client

Run the client to send test traffic:

```bash
python udp_client.py --ip <SERVER_IP> --port <SERVER_PORT> --bandwidth <BANDWIDTH_MBPS> [--connections <NUM_CONNECTIONS>] [--duration <SECONDS>]
```

Example:
```bash
python udp_client.py --ip 127.0.0.1 --port 5000 --bandwidth 100 --connections 4 --duration 30
```

Parameters:
- `--ip`: Server IP address
- `--port`: Server port
- `--bandwidth`: Total bandwidth in Mbps
- `--connections`: Number of parallel connections (default: 1)
- `--duration`: Test duration in seconds (default: 10)

## Output

The server generates CSV log files with the following columns:
- packet_number: Sequential packet number
- recv_time_ns: Reception timestamp in nanoseconds
- inter_packet_delay_ns: Time between consecutive packets in nanoseconds
