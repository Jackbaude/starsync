import socket
import threading
import argparse
import time
import os

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

def run_client(ip, port, connections, bandwidth, duration):
    total_bandwidth_bps = bandwidth * 1_000_000
    bw_per_thread = total_bandwidth_bps / connections

    threads = []
    for i in range(connections):
        t = threading.Thread(target=send_packets, args=(ip, port, bw_per_thread, i, duration))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--connections", type=int, default=1)
    parser.add_argument("--bandwidth", type=float, required=True, help="Total bandwidth in Mbps")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds")
    args = parser.parse_args()
    run_client(args.ip, args.port, args.connections, args.bandwidth, args.duration)

