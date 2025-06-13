import socket
import threading
import argparse
import os
import time
from datetime import datetime

def handle_connection(sock, output_dir, reverse=False, bandwidth_bps=None, duration=None):
    if not reverse:
        # Original receive mode
        prev_time = None
        log_file = os.path.join(output_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        with open(log_file, 'w') as f:
            f.write("packet_number,recv_time_ns,inter_packet_delay_ns\n")
            pkt_num = 0
            while True:
                try:
                    data, addr = sock.recvfrom(2048)
                    recv_time = time.time_ns()
                    delay = recv_time - prev_time if prev_time else 0
                    prev_time = recv_time
                    f.write(f"{pkt_num},{recv_time},{delay}\n")
                    pkt_num += 1
                except Exception as e:
                    print(f"Error: {e}")
                    break
    else:
        # Reverse mode - send data
        packet_size = 1400
        interval = (packet_size * 8) / bandwidth_bps
        start_time = time.time()
        next_send = time.time()
        count = 0
        
        while time.time() - start_time < duration:
            current = time.time()
            if current >= next_send:
                timestamp = time.time_ns()
                payload = f"{count},{timestamp}".encode()
                payload = payload.ljust(packet_size, b'x')
                sock.sendto(payload, (sock.getpeername()[0], sock.getpeername()[1]))
                count += 1
                next_send += interval

def run_server(ip, port, output_dir, reverse=False, bandwidth=None, duration=None):
    os.makedirs(output_dir, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(f"[+] Server listening on {ip}:{port}")

    if reverse:
        # In reverse mode, wait for client to connect first
        print("[+] Waiting for client connection...")
        data, addr = sock.recvfrom(2048)
        sock.connect(addr)
        print(f"[+] Connected to client {addr[0]}:{addr[1]}")
        handler = threading.Thread(target=handle_connection, args=(sock, output_dir, True, bandwidth * 1_000_000, duration))
    else:
        handler = threading.Thread(target=handle_connection, args=(sock, output_dir))

    handler.start()
    handler.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("-R", "--reverse", action="store_true", help="Run in reverse mode (server sends data)")
    parser.add_argument("--bandwidth", type=float, help="Bandwidth in Mbps (required for reverse mode)")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds (for reverse mode)")
    args = parser.parse_args()
    
    if args.reverse and not args.bandwidth:
        parser.error("--bandwidth is required in reverse mode")
    
    run_server(args.ip, args.port, args.output_dir, args.reverse, args.bandwidth, args.duration)

