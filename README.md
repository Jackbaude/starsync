# UDP Bandwidth Test Tool

A simple tool for testing UDP bandwidth and packet timing between a client and server.

## Requirements

- Python 3.x
- No additional dependencies required

## Usage

### Server

Start the server first:

```bash
python udp_server.py --ip <IP_ADDRESS> --port <PORT> --output_dir <OUTPUT_DIRECTORY> [-R] [--bandwidth <BANDWIDTH_MBPS>] [--duration <SECONDS>]
```

Examples:
```bash
# Normal mode (server receives data)
python udp_server.py --ip 0.0.0.0 --port 5000 --output_dir logs

# Reverse mode (server sends data)
python udp_server.py --ip 0.0.0.0 --port 5000 --output_dir logs -R --bandwidth 100 --duration 30
```

### Client

Run the client to send or receive test traffic:

```bash
python udp_client.py --ip <SERVER_IP> --port <SERVER_PORT> [--bandwidth <BANDWIDTH_MBPS>] [--connections <NUM_CONNECTIONS>] [--duration <SECONDS>] [-R]
```

Examples:
```bash
# Normal mode (client sends data)
python udp_client.py --ip 127.0.0.1 --port 5000 --bandwidth 100 --connections 4 --duration 30

# Reverse mode (client receives data)
python udp_client.py --ip 127.0.0.1 --port 5000 --connections 4 --duration 30 -R
```

Parameters:
- `--ip`: Server IP address
- `--port`: Server port
- `--bandwidth`: Total bandwidth in Mbps (required in send mode)
- `--connections`: Number of parallel connections (default: 1)
- `--duration`: Test duration in seconds (default: 10)
- `-R, --reverse`: Run in reverse mode (client receives data)

## Output

The server/client generates CSV log files with the following columns:
- packet_number: Sequential packet number
- recv_time_ns: Reception timestamp in nanoseconds
- inter_packet_delay_ns: Time between consecutive packets in nanoseconds

## Modes

1. Normal Mode (default):
   - Client sends data to server
   - Server receives and logs data
   - Requires bandwidth specification on client

2. Reverse Mode (-R):
   - Server sends data to client
   - Client receives and logs data
   - Requires bandwidth specification on server
