import socket
import threading
import argparse
import time
import os
from datetime import datetime

def send_packets(ip, port, bandwidth_bps, thread_id, duration, packet_size=1400):
    interval = (packet_size * 8) / bandwidth_bps  # seconds between packets
    addr = (ip, port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    start_time = time.time()
    next_send = time.time()
    count = 0

    while time.time() - start_time < duration:
        current = time.time()
        if current >= next_send:
            timestamp = time.time_ns()
            payload = f"{count},{timestamp}".encode()
            payload = payload.ljust(packet_size, b'x')
            sock.sendto(payload, addr)
            count += 1
            next_send += interval

def receive_packets(ip, port, output_dir, thread_id, duration):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    
    # Send initial packet to establish connection
    sock.sendto(b'start', (ip, port))
    
    log_file = os.path.join(output_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{thread_id}.csv")
    with open(log_file, 'w') as f:
        f.write("packet_number,recv_time_ns,inter_packet_delay_ns\n")
        prev_time = None
        pkt_num = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                data, _ = sock.recvfrom(2048)
                recv_time = time.time_ns()
                delay = recv_time - prev_time if prev_time else 0
                prev_time = recv_time
                f.write(f"{pkt_num},{recv_time},{delay}\n")
                pkt_num += 1
            except Exception as e:
                print(f"Error: {e}")
                break

def run_client(ip, port, connections, bandwidth, duration, reverse=False):
    if not reverse:
        # Original send mode
        total_bandwidth_bps = bandwidth * 1_000_000
        bw_per_thread = total_bandwidth_bps / connections

        threads = []
        for i in range(connections):
            t = threading.Thread(target=send_packets, args=(ip, port, bw_per_thread, i, duration))
            t.start()
            threads.append(t)
    else:
        # Reverse mode - receive data
        os.makedirs("logs", exist_ok=True)
        threads = []
        for i in range(connections):
            t = threading.Thread(target=receive_packets, args=(ip, port, "logs", i, duration))
            t.start()
            threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--connections", type=int, default=1)
    parser.add_argument("--bandwidth", type=float, help="Total bandwidth in Mbps (required for send mode)")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    parser.add_argument("-R", "--reverse", action="store_true", help="Run in reverse mode (client receives data)")
    args = parser.parse_args()
    
    if not args.reverse and not args.bandwidth:
        parser.error("--bandwidth is required in send mode")
    
    run_client(args.ip, args.port, args.connections, args.bandwidth, args.duration, args.reverse)

