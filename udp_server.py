#!/usr/bin/env python3

import asyncio
import argparse
import csv
import json
import logging
import socket
import struct
import time
from datetime import datetime
from typing import Dict, Optional
import os
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UDPServer:
    def __init__(self, port: int, log_file: str):
        self.port = port
        self.log_file = log_file
        self.transport = None
        self.protocol = None
        self.stats = {
            'packets_received': 0,
            'packets_sent': 0,
            'bytes_received': 0,
            'start_time': None,
            'last_stats_time': None,
            'flow_stats': {}
        }
        
        # Create results directory if it doesn't exist
        os.makedirs('results', exist_ok=True)
        
        # Initialize log file with headers
        try:
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'source_ip',
                    'source_port',
                    'sequence_number',
                    'client_timestamp',
                    'server_timestamp',
                    'payload_length'
                ])
        except Exception as e:
            logger.error(f"Failed to initialize log file: {e}")
            sys.exit(1)

    class ServerProtocol(asyncio.DatagramProtocol):
        def __init__(self, server):
            self.server = server
            self.transport = None

        def connection_made(self, transport):
            self.transport = transport
            logger.info(f"Server started and listening on port {self.server.port}")

        def datagram_received(self, data, addr):
            try:
                # Parse packet header (sequence number and timestamp)
                seq_num, client_timestamp = struct.unpack('!Qd', data[:16])
                payload = data[16:]
                
                # Get current timestamp
                server_timestamp = time.time()
                
                # Create ACK packet
                ack_data = struct.pack('!Qdd', seq_num, client_timestamp, server_timestamp)
                
                # Send ACK
                self.transport.sendto(ack_data, addr)
                
                # Update statistics
                self.server.stats['packets_received'] += 1
                self.server.stats['bytes_received'] += len(data)
                
                # Update flow statistics
                flow_key = f"{addr[0]}:{addr[1]}"
                if flow_key not in self.server.stats['flow_stats']:
                    self.server.stats['flow_stats'][flow_key] = {
                        'packets_received': 0,
                        'bytes_received': 0,
                        'last_seq': None
                    }
                
                flow_stats = self.server.stats['flow_stats'][flow_key]
                flow_stats['packets_received'] += 1
                flow_stats['bytes_received'] += len(data)
                
                # Check for packet reordering
                if flow_stats['last_seq'] is not None and seq_num < flow_stats['last_seq']:
                    logger.warning(f"Packet reordering detected: seq {seq_num} after {flow_stats['last_seq']}")
                flow_stats['last_seq'] = seq_num
                
                # Log packet information
                self.server.log_packet(addr, seq_num, client_timestamp, server_timestamp, len(data))
                
            except Exception as e:
                logger.error(f"Error processing packet: {e}")

    def log_packet(self, addr, seq_num, client_timestamp, server_timestamp, payload_length):
        """Log packet information to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    addr[0],
                    addr[1],
                    seq_num,
                    client_timestamp,
                    server_timestamp,
                    payload_length
                ])
        except Exception as e:
            logger.error(f"Failed to log packet: {e}")

    async def start(self):
        """Start the UDP server"""
        try:
            loop = asyncio.get_running_loop()
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Increase socket buffer sizes
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)  # 1MB receive buffer
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)  # 1MB send buffer
            
            # Bind socket
            sock.bind(('0.0.0.0', self.port))
            
            # Create protocol and transport
            self.protocol = self.ServerProtocol(self)
            self.transport, _ = await loop.create_datagram_endpoint(
                lambda: self.protocol,
                sock=sock
            )
            
            self.stats['start_time'] = time.time()
            self.stats['last_stats_time'] = self.stats['start_time']
            
            logger.info(f"UDP Server started on port {self.port}")
            
            # Start statistics reporting
            asyncio.create_task(self.report_stats())
            
            # Keep the server running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Server error: {e}")
            if self.transport:
                self.transport.close()
            raise

    async def report_stats(self):
        """Report server statistics periodically"""
        while True:
            try:
                await asyncio.sleep(5)  # Report every 5 seconds
                
                current_time = time.time()
                elapsed = current_time - self.stats['last_stats_time']
                
                if elapsed > 0:
                    packets_per_sec = self.stats['packets_received'] / elapsed
                    bytes_per_sec = self.stats['bytes_received'] / elapsed
                    mbps = (bytes_per_sec * 8) / 1_000_000
                    
                    logger.info(f"Stats: {packets_per_sec:.2f} packets/sec, {mbps:.2f} Mbps")
                    
                    # Reset counters
                    self.stats['packets_received'] = 0
                    self.stats['bytes_received'] = 0
                    self.stats['last_stats_time'] = current_time
            except Exception as e:
                logger.error(f"Error in stats reporting: {e}")

def main():
    parser = argparse.ArgumentParser(description='UDP Server for Traffic Testing')
    parser.add_argument('--port', type=int, default=5000, help='UDP port to listen on')
    parser.add_argument('--log-file', type=str, default='server_log.csv',
                      help='Output file for server logs')
    
    args = parser.parse_args()
    
    server = UDPServer(args.port, args.log_file)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 