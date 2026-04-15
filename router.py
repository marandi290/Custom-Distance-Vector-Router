import socket
import json
import threading
import time
import os

MY_IP = os.getenv("MY_IP", "127.0.0.1")
NEIGHBORS = [n for n in os.getenv("NEIGHBORS", "").split(",") if n]
PORT = 5000
INF = 9999
UPDATE_INTERVAL = 5

# { subnet: [distance, next_hop] }
routing_table = {}
table_lock = threading.Lock()

def get_directly_connected():
    """Parse directly connected subnets from MY_SUBNETS env var."""
    subnets = os.getenv("MY_SUBNETS", "")
    return [s.strip() for s in subnets.split(",") if s.strip()]

def init_routing_table():
    for subnet in get_directly_connected():
        routing_table[subnet] = [0, "0.0.0.0"]

def build_packet(exclude_neighbor=None):
    """Build DV-JSON packet, applying Split Horizon."""
    routes = []
    with table_lock:
        for subnet, (dist, next_hop) in routing_table.items():
            # Split Horizon: don't advertise a route back to the neighbor it came from
            if next_hop == exclude_neighbor:
                continue
            routes.append({"subnet": subnet, "distance": dist})
    return json.dumps({"router_id": MY_IP, "version": 1.0, "routes": routes}).encode()

def broadcast_updates():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        for neighbor in NEIGHBORS:
            try:
                packet = build_packet(exclude_neighbor=neighbor)
                sock.sendto(packet, (neighbor, PORT))
            except Exception as e:
                print(f"[WARN] Could not send to {neighbor}: {e}")
        time.sleep(UPDATE_INTERVAL)

def listen_for_updates():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", PORT))
    print(f"[INFO] Listening on port {PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(4096)
            packet = json.loads(data.decode())
            neighbor_ip = packet.get("router_id", addr[0])
            update_logic(neighbor_ip, packet.get("routes", []))
        except Exception as e:
            print(f"[WARN] Receive error: {e}")

def update_logic(neighbor_ip, routes_from_neighbor):
    changed = False
    with table_lock:
        for route in routes_from_neighbor:
            subnet = route["subnet"]
            new_dist = route["distance"] + 1

            if new_dist >= INF:
                continue

            current = routing_table.get(subnet)
            if current is None or new_dist < current[0]:
                routing_table[subnet] = [new_dist, neighbor_ip]
                os.system(f"ip route replace {subnet} via {neighbor_ip}")
                print(f"[UPDATE] {subnet} via {neighbor_ip} dist={new_dist}")
                changed = True
            elif current[1] == neighbor_ip and new_dist > current[0]:
                # Neighbor increased cost — update
                routing_table[subnet] = [new_dist, neighbor_ip]
                os.system(f"ip route replace {subnet} via {neighbor_ip}")
                print(f"[UPDATE] {subnet} via {neighbor_ip} dist={new_dist} (cost increased)")
                changed = True

    if changed:
        print_table()

def print_table():
    print("\n--- Routing Table ---")
    for subnet, (dist, hop) in routing_table.items():
        print(f"  {subnet:20s} dist={dist}  via={hop}")
    print("---------------------\n")

if __name__ == "__main__":
    init_routing_table()
    print(f"[INFO] Router started: MY_IP={MY_IP}, NEIGHBORS={NEIGHBORS}")
    print_table()
    threading.Thread(target=broadcast_updates, daemon=True).start()
    listen_for_updates()
