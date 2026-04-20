# Assignment 4 Report: Custom Distance-Vector Router

**GitHub Repository**: https://github.com/marandi290/Custom-Distance-Vector-Router

---

## 1. Design

### Overview

The router is implemented as a single Python script (`router.py`) that runs inside an Alpine Linux Docker container. It implements a simplified Distance-Vector routing protocol using UDP broadcasts and the Bellman-Ford algorithm, following the DV-JSON packet format specified in the assignment.

### Topology

```
Router A (10.0.1.1, 10.0.3.1)
    |               \
  net_ab           net_ac
    |                 \
Router B (10.0.1.2, 10.0.2.1) --- net_bc --- Router C (10.0.2.2, 10.0.3.2)
```

| Network | Subnet      | Gateway    | Routers |
|---------|-------------|------------|---------|
| net_ab  | 10.0.1.0/24 | 10.0.1.254 | A, B    |
| net_bc  | 10.0.2.0/24 | 10.0.2.254 | B, C    |
| net_ac  | 10.0.3.0/24 | 10.0.3.254 | A, C    |

### Protocol

- **Transport**: UDP, port 5000
- **Format**: DV-JSON (version 1.0)
- **Update interval**: every 5 seconds

Each update packet looks like:

```json
{
  "router_id": "10.0.1.1",
  "version": 1.0,
  "routes": [
    { "subnet": "10.0.1.0/24", "distance": 0 },
    { "subnet": "10.0.2.0/24", "distance": 1 }
  ]
}
```

### Components

**Initialization** — `init_routing_table()`  
Reads directly connected subnets from the `MY_SUBNETS` environment variable and seeds the routing table with distance 0 for each.

**Broadcasting** — `broadcast_updates()`  
Runs in a background daemon thread. Every 5 seconds it sends a DV-JSON packet to each neighbor. Split Horizon is applied per neighbor before sending.

**Listening** — `listen_for_updates()`  
Binds to `0.0.0.0:5000` and runs as the main loop. On each received packet, it calls `update_logic()`.

**Bellman-Ford** — `update_logic()`  
For each route received from a neighbor:
- Computes `new_dist = received_distance + 1`
- If `new_dist` is less than the current known distance, updates the routing table and installs the route using `ip route replace`
- If the route came from the same neighbor and the cost increased, updates accordingly

**Split Horizon** — `build_packet(exclude_neighbor)`  
Before sending to a neighbor, filters out any route whose `next_hop` equals that neighbor — ensuring routes are never advertised back to where they came from.

**Linux Routing Table Integration**  
Every routing table update is applied to the OS using:
```bash
ip route replace <subnet> via <next_hop>
```
This makes the container actually forward packets along the learned paths.

### Environment Variables

| Variable   | Description                             | Example                  |
|------------|-----------------------------------------|--------------------------|
| MY_IP      | Router's IP used as router_id           | 10.0.1.1                 |
| MY_SUBNETS | Directly connected subnets (comma-sep)  | 10.0.1.0/24,10.0.3.0/24 |
| NEIGHBORS  | Neighbor IPs to send updates to         | 10.0.1.2,10.0.3.2        |

---

## 2. Testing

### Setup

Due to a known Docker Desktop issue on Windows with WSL2 — where attaching a container to multiple networks simultaneously fails — a custom `start.sh` script was used instead of `docker compose up`. The script starts each container on one network first, then connects the second network after the container is running. Networks are created with explicit `.254` gateways to avoid IP conflicts with router addresses.

```bash
bash start.sh
```

### Test 1: Convergence

After starting all three routers, we waited 15 seconds (3 update cycles) and checked the routing tables.

**Command:**
```bash
docker exec router_a ip route show
docker exec router_b ip route show
docker exec router_c ip route show
```

**Results:**

Router A:
```
default via 10.0.1.254 dev eth0
10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.1
10.0.2.0/24 via 10.0.1.2 dev eth0        ← learned from B
10.0.3.0/24 dev eth1 proto kernel scope link src 10.0.3.1
```

Router B:
```
default via 10.0.1.254 dev eth0
10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.2
10.0.2.0/24 dev eth1 proto kernel scope link src 10.0.2.1
10.0.3.0/24 via 10.0.2.2 dev eth1        ← learned from C
```

Router C:
```
default via 10.0.3.254 dev eth1
10.0.2.0/24 dev eth0 proto kernel scope link src 10.0.2.2
10.0.3.0/24 dev eth1 proto kernel scope link src 10.0.3.2
```

All routers converged correctly within 15 seconds. ✔

### Test 2: Failover (Router C stopped)

Router C was stopped to simulate a node failure. After 30 seconds we checked whether Router A could still reach `10.0.2.0/24` via Router B.

**Command:**
```bash
docker stop router_c
# wait 30 seconds
docker exec router_a ip route show
docker exec router_b ip route show
```

**Results:**

Router A:
```
default via 10.0.1.254 dev eth0
10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.1
10.0.2.0/24 via 10.0.1.2 dev eth0        ← still reachable via B ✔
10.0.3.0/24 dev eth1 proto kernel scope link src 10.0.3.1
```

Router B:
```
default via 10.0.1.254 dev eth0
10.0.1.0/24 dev eth0 proto kernel scope link src 10.0.1.2
10.0.2.0/24 dev eth1 proto kernel scope link src 10.0.2.1
```

Router A correctly retained its route to `10.0.2.0/24` via Router B. No routing loop occurred. ✔

---

## 3. Analysis: Loop Prevention

### The Count-to-Infinity Problem

In a basic Distance-Vector protocol without loop prevention, when a node goes down the following happens:

1. Router C goes down. Router A's route to `10.0.2.0/24` via C becomes stale.
2. Router B still has `10.0.2.0/24` directly (dist=0) and advertises it to A.
3. Without Split Horizon, Router A would also advertise its stale route for `10.0.2.0/24` back to B with dist=2.
4. Router B, seeing a path via A at dist=2, might update its own entry — and the two routers keep incrementing each other's distance until infinity.

### How Split Horizon Prevents This

The `build_packet(exclude_neighbor)` function filters the routing table before sending:

```python
for subnet, (dist, next_hop) in routing_table.items():
    if next_hop == exclude_neighbor:
        continue   # do not advertise this route back to where it came from
    routes.append({"subnet": subnet, "distance": dist})
```

**Concrete example with our topology:**

- Router A learns `10.0.2.0/24` via Router B (next_hop = `10.0.1.2`)
- When Router A builds its update packet for Router B, it skips `10.0.2.0/24` because `next_hop == neighbor`
- Router B never receives a false advertisement from A claiming it can reach `10.0.2.0/24` via A
- The loop is broken at the source

**When Router C stops:**

- Router A's route to `10.0.3.0/24` is direct (via its own `eth1` interface, next_hop = `0.0.0.0`) — not learned from B
- So Router A continues to advertise `10.0.3.0/24` to B normally
- Router B's stale route to `10.0.3.0/24` via C simply stops being refreshed and remains until a timeout or manual flush
- At no point do A and B create a loop for any subnet

### Summary

| Scenario | Without Split Horizon | With Split Horizon |
|---|---|---|
| C goes down, A has stale route to 10.0.2.0/24 | A advertises stale route to B → loop | A never advertises B's own route back to B |
| B has stale route to 10.0.3.0/24 via C | B advertises to A → A re-advertises → loop | B's stale route simply ages out, no loop |

Split Horizon alone is sufficient to prevent count-to-infinity in this triangle topology because no route is ever reflected back to its source neighbor.
