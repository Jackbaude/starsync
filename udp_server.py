#!/usr/bin/env python3

import asyncio
import argparse
import csv
import logging
import socket
import struct
import time
from datetime import datetime
from typing import Dict, List, Optional
import os
import sys
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UDPServer:
    def __init__(self, host: str, port: int, packet_size: int, log_file: str):
        self.host = host
        self.port = port
        self.packet_size = packet_size
        self.log_file = log_file
        
        self.stats = {
            'packets_sent': 0,
            'bytes_sent': 0,
            'start_time': None,
            'last_stats_time': None,
            'client_stats': {}
        }
        
        # Create results directory if it doesn't exist
        os.makedirs('results', exist_ok=True)
        
        # Initialize log file with headers
        try:
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'client_addr',
                    'sequence_number',
                    'request_time',
                    'send_time',
                    'ack_time',
                    'rtt_ms'
                ])
        except Exception as e:
            logger.error(f"Failed to initialize log file: {e}")
            sys.exit(1)

    class ServerProtocol(asyncio.DatagramProtocol):
        def __init__(self, server):
            self.server = server
            self.transport = None
            self.pending_packets = {}  # Track packets waiting for ACK
            self.client_sequence_numbers = {}  # Track sequence numbers per client

        def connection_made(self, transport):
            self.transport = transport
            logger.info(f"Server listening on {self.server.host}:{self.server.port}")

        def datagram_received(self, data, addr):
            try:
                if len(data) == 16:  # Request packet
                    # Parse request packet
                    seq_num, request_time = struct.unpack('!Qd', data)
                    
                    # Get or initialize client sequence number
                    if addr not in self.client_sequence_numbers:
                        self.client_sequence_numbers[addr] = 0
                    
                    # Create data packet
                    current_time = time.time()
                    packet_data = struct.pack('!Qdd', seq_num, request_time, current_time)
                    # Add payload to reach desired packet size
                    packet_data += b'x' * (self.server.packet_size - len(packet_data))
                    
                    # Send data packet
                    self.transport.sendto(packet_data, addr)
                    
                    # Update statistics
                    self.server.stats['packets_sent'] += 1
                    self.server.stats['bytes_sent'] += len(packet_data)
                    
                    # Store packet info for RTT calculation
                    self.pending_packets[(addr, seq_num)] = {
                        'request_time': request_time,
                        'send_time': current_time
                    }
                    
                    # Log packet send
                    self.server.log_packet(
                        addr,
                        seq_num,
                        request_time,
                        current_time,
                        None,  # ACK time not yet received
                        None   # RTT not yet calculated
                    )
                    
                elif len(data) == 16:  # ACK packet
                    # Parse ACK packet
                    seq_num, ack_time = struct.unpack('!Qd', data)
                    
                    # Calculate RTT
                    if (addr, seq_num) in self.pending_packets:
                        packet_info = self.pending_packets[(addr, seq_num)]
                        rtt = (ack_time - packet_info['request_time']) * 1000  # Convert to milliseconds
                        
                        # Update log with ACK time and RTT
                        self.server.update_packet_log(
                            addr,
                            seq_num,
                            ack_time,
                            rtt
                        )
                        
                        # Remove from pending packets
                        del self.pending_packets[(addr, seq_num)]
                
            except Exception as e:
                logger.error(f"Error processing packet from {addr}: {e}")

    def log_packet(self, client_addr: tuple, seq_num: int, request_time: float,
                  send_time: float, ack_time: Optional[float], rtt: Optional[float]):
        """Log packet information to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    f"{client_addr[0]}:{client_addr[1]}",
                    seq_num,
                    request_time,
                    send_time,
                    ack_time if ack_time is not None else '',
                    rtt if rtt is not None else ''
                ])
        except Exception as e:
            logger.error(f"Failed to log packet: {e}")

    def update_packet_log(self, client_addr: tuple, seq_num: int, ack_time: float, rtt: float):
        """Update existing log entry with ACK time and RTT"""
        try:
            # Read all lines
            with open(self.log_file, 'r', newline='') as f:
                lines = list(csv.reader(f))
            
            # Find and update the matching entry
            for i, line in enumerate(lines[1:], 1):  # Skip header
                if (line[1] == f"{client_addr[0]}:{client_addr[1]}" and 
                    int(line[2]) == seq_num):
                    lines[i][5] = str(ack_time)  # ACK time
                    lines[i][6] = str(rtt)       # RTT
                    break
            
            # Write back all lines
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(lines)
                
        except Exception as e:
            logger.error(f"Failed to update packet log: {e}")

    async def start(self):
        """Start the UDP server"""
        try:
            loop = asyncio.get_running_loop()
            
            self.stats['start_time'] = time.time()
            self.stats['last_stats_time'] = self.stats['start_time']
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Increase socket buffer sizes
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
            
            # Bind socket
            sock.bind((self.host, self.port))
            
            # Create protocol and transport
            protocol = self.ServerProtocol(self)
            transport, _ = await loop.create_datagram_endpoint(
                lambda: protocol,
                sock=sock
            )
            
            # Start statistics reporting
            stats_task = asyncio.create_task(self.report_stats())
            
            logger.info(f"Server started on {self.host}:{self.port}")
            logger.info(f"Packet size: {self.packet_size} bytes")
            
            # Keep server running
            while True:
                await asyncio.sleep(1)
            
        except Exception as e:
            logger.error(f"Server error: {e}")
            raise

    async def report_stats(self):
        """Report server statistics periodically"""
        while True:
            try:
                await asyncio.sleep(5)  # Report every 5 seconds
                
                current_time = time.time()
                elapsed = current_time - self.stats['last_stats_time']
                
                if elapsed > 0:
                    packets_per_sec = self.stats['packets_sent'] / elapsed
                    bytes_per_sec = self.stats['bytes_sent'] / elapsed
                    mbps = (bytes_per_sec * 8) / 1_000_000
                    
                    logger.info(f"Stats: {packets_per_sec:.2f} packets/sec, {mbps:.2f} Mbps")
                    
                    # Reset counters
                    self.stats['packets_sent'] = 0
                    self.stats['bytes_sent'] = 0
                    self.stats['last_stats_time'] = current_time
            except Exception as e:
                logger.error(f"Error in stats reporting: {e}")

def main():
    parser = argparse.ArgumentParser(description='UDP Server for Traffic Testing')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                      help='Server host address')
    parser.add_argument('--port', type=int, default=5000,
                      help='Server port')
    parser.add_argument('--packet-size', type=int, default=1400,
                      help='UDP packet size in bytes')
    parser.add_argument('--log-file', type=str, default='server_log.csv',
                      help='Output file for server logs')
    
    args = parser.parse_args()
    
    server = UDPServer(
        args.host,
        args.port,
        args.packet_size,
        args.log_file
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 