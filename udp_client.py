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

class UDPClient:
    def __init__(self, server_ip: str, server_port: int, num_flows: int,
                 duration: int, bandwidth_mbps: float, packet_size: int, log_file: str):
        self.server_ip = server_ip
        self.server_port = server_port
        self.num_flows = num_flows
        self.duration = duration
        self.bandwidth_mbps = bandwidth_mbps
        self.packet_size = packet_size
        self.log_file = log_file
        
        # Calculate packets per second per flow
        self.packets_per_second = (bandwidth_mbps * 1_000_000) / (packet_size * 8)
        self.packet_interval = 1.0 / self.packets_per_second
        
        self.stats = {
            'packets_sent': 0,
            'packets_received': 0,
            'bytes_sent': 0,
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
                    'flow_id',
                    'sequence_number',
                    'send_time',
                    'server_recv_time',
                    'ack_time',
                    'rtt_ms'
                ])
        except Exception as e:
            logger.error(f"Failed to initialize log file: {e}")
            sys.exit(1)

    class ClientProtocol(asyncio.DatagramProtocol):
        def __init__(self, client, flow_id: int):
            self.client = client
            self.flow_id = flow_id
            self.transport = None
            self.sequence_number = 0
            self.pending_packets = {}
            self.start_time = None
            self.is_running = False

        def connection_made(self, transport):
            self.transport = transport
            self.start_time = time.time()
            self.is_running = True
            logger.info(f"Flow {self.flow_id}: Connected to server {self.client.server_ip}:{self.client.server_port}")

        def datagram_received(self, data, addr):
            try:
                # Parse ACK packet
                seq_num, client_timestamp, server_timestamp = struct.unpack('!Qdd', data)
                
                # Calculate RTT
                current_time = time.time()
                rtt = (current_time - client_timestamp) * 1000  # Convert to milliseconds
                
                # Update statistics
                self.client.stats['packets_received'] += 1
                
                # Log ACK reception
                self.client.log_packet(
                    self.flow_id,
                    seq_num,
                    client_timestamp,
                    server_timestamp,
                    current_time,
                    rtt
                )
                
                # Remove from pending packets
                if seq_num in self.pending_packets:
                    del self.pending_packets[seq_num]
                
            except Exception as e:
                logger.error(f"Flow {self.flow_id}: Error processing ACK: {e}")

        async def send_packets(self):
            """Send packets at the specified rate"""
            if not self.is_running:
                logger.error(f"Flow {self.flow_id}: Protocol not connected")
                return

            next_send_time = time.time()
            logger.info(f"Flow {self.flow_id}: Starting to send packets at {self.client.packets_per_second:.2f} packets/sec")
            
            try:
                while time.time() - self.start_time < self.client.duration and self.is_running:
                    current_time = time.time()
                    
                    if current_time >= next_send_time:
                        # Create packet with sequence number and timestamp
                        packet_data = struct.pack('!Qd', self.sequence_number, current_time)
                        packet_data += b'x' * (self.client.packet_size - len(packet_data))
                        
                        # Send packet
                        self.transport.sendto(packet_data, (self.client.server_ip, self.client.server_port))
                        
                        # Update statistics
                        self.client.stats['packets_sent'] += 1
                        self.client.stats['bytes_sent'] += len(packet_data)
                        
                        # Store packet info for RTT calculation
                        self.pending_packets[self.sequence_number] = current_time
                        
                        # Update sequence number
                        self.sequence_number += 1
                        
                        # Calculate next send time
                        next_send_time += self.client.packet_interval
                    
                    # Small sleep to prevent busy waiting
                    await asyncio.sleep(0.0001)
                
                logger.info(f"Flow {self.flow_id}: Finished sending {self.sequence_number} packets")
                
            except Exception as e:
                logger.error(f"Flow {self.flow_id}: Error in send_packets: {e}")
                raise

    def log_packet(self, flow_id: int, seq_num: int, send_time: float,
                  server_recv_time: float, ack_time: float, rtt: float):
        """Log packet information to CSV file"""
        try:
            with open(self.log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    flow_id,
                    seq_num,
                    send_time,
                    server_recv_time,
                    ack_time,
                    rtt
                ])
        except Exception as e:
            logger.error(f"Failed to log packet: {e}")

    async def start(self):
        """Start the UDP client with multiple flows"""
        try:
            loop = asyncio.get_running_loop()
            
            self.stats['start_time'] = time.time()
            self.stats['last_stats_time'] = self.stats['start_time']
            
            # Create tasks for each flow
            tasks = []
            for flow_id in range(self.num_flows):
                # Create socket for this flow
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                
                # Increase socket buffer sizes
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024 * 1024)
                
                # Create protocol and transport
                protocol = self.ClientProtocol(self, flow_id)
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: protocol,
                    sock=sock
                )
                
                # Start sending packets
                task = asyncio.create_task(protocol.send_packets())
                tasks.append(task)
            
            # Start statistics reporting
            stats_task = asyncio.create_task(self.report_stats())
            
            logger.info(f"Starting {self.num_flows} flows to {self.server_ip}:{self.server_port}")
            logger.info(f"Target bandwidth: {self.bandwidth_mbps} Mbps per flow")
            logger.info(f"Test duration: {self.duration} seconds")
            
            # Wait for all flows to complete
            await asyncio.gather(*tasks)
            stats_task.cancel()
            
            # Print final statistics
            self.print_final_stats()
            
        except Exception as e:
            logger.error(f"Client error: {e}")
            raise

    async def report_stats(self):
        """Report client statistics periodically"""
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

    def print_final_stats(self):
        """Print final statistics after test completion"""
        total_time = time.time() - self.stats['start_time']
        total_bytes = self.stats['bytes_sent']
        total_packets = self.stats['packets_sent']
        
        avg_throughput = (total_bytes * 8) / (total_time * 1_000_000)  # Mbps
        avg_packets_per_sec = total_packets / total_time
        
        logger.info("\nFinal Statistics:")
        logger.info(f"Total duration: {total_time:.2f} seconds")
        logger.info(f"Total packets sent: {total_packets}")
        logger.info(f"Average throughput: {avg_throughput:.2f} Mbps")
        logger.info(f"Average packets per second: {avg_packets_per_sec:.2f}")

def main():
    parser = argparse.ArgumentParser(description='UDP Client for Traffic Testing')
    parser.add_argument('--server-ip', type=str, default='127.0.0.1',
                      help='Server IP address')
    parser.add_argument('--server-port', type=int, default=5000,
                      help='Server port')
    parser.add_argument('--flows', type=int, default=4,
                      help='Number of parallel flows')
    parser.add_argument('--duration', type=int, default=10,
                      help='Test duration in seconds')
    parser.add_argument('--bandwidth', type=float, default=50,
                      help='Target bandwidth per flow in Mbps')
    parser.add_argument('--packet-size', type=int, default=1400,
                      help='UDP packet size in bytes')
    parser.add_argument('--log-file', type=str, default='client_log.csv',
                      help='Output file for client logs')
    
    args = parser.parse_args()
    
    client = UDPClient(
        args.server_ip,
        args.server_port,
        args.flows,
        args.duration,
        args.bandwidth,
        args.packet_size,
        args.log_file
    )
    
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        logger.info("Client stopped by user")
    except Exception as e:
        logger.error(f"Client error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 