import socket
import threading
import argparse
import os
import time
from datetime import datetime

def handle_connection(sock, output_dir):
    prev_time = None
    log_file = os.path.join(output_dir, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(log_file, 'w') as f:
        f.write("packet_number,recv_time_ns,inter_packet_delay_ns\n")
        pkt_num = 0
        while True:
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

def run_server(ip, port, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, port))
    print(f"[+] Server listening on {ip}:{port}")

    handler = threading.Thread(target=handle_connection, args=(sock, output_dir))
    handler.start()
    handler.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output_dir", required=True)
    args = parser.parse_args()
    run_server(args.ip, args.port, args.output_dir)

