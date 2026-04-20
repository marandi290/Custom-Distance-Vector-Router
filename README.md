# Custom Distance-Vector Router

A simplified Distance-Vector routing daemon implementing Bellman-Ford with Split Horizon, deployed in Docker containers forming a triangle topology.

## Topology

```
Router A (10.0.1.1, 10.0.3.1)
    |               \
  net_ab           net_ac
    |                 \
Router B (10.0.1.2, 10.0.2.1) --- net_bc --- Router C (10.0.2.2, 10.0.3.2)
```

| Network  | Subnet       | Gateway      | Connected Routers |
|----------|--------------|--------------|-------------------|
| net_ab   | 10.0.1.0/24  | 10.0.1.254   | A, B              |
| net_bc   | 10.0.2.0/24  | 10.0.2.254   | B, C              |
| net_ac   | 10.0.3.0/24  | 10.0.3.254   | A, C              |

> Gateways are set to `.254` to avoid conflicts with router IPs (`.1`, `.2`).

## Design

- **Protocol**: UDP port 5000, DV-JSON format (version 1.0)
- **Algorithm**: Bellman-Ford — each router picks the minimum-cost path per subnet
- **Loop Prevention**: Split Horizon — a route learned from neighbor X is never advertised back to X
- **Update interval**: every 5 seconds

### How Split Horizon prevents count-to-infinity

When Router C goes down, Router A stops receiving updates for `10.0.2.0/24` via C.
Router B knows `10.0.2.0/24` directly (dist=0) and advertises it to A.
Because A learned `10.0.3.0/24` via C (not via B), B will not advertise `10.0.3.0/24` back to A — preventing a routing loop where A and B would increment each other's stale route indefinitely.

## Quick Start

> `docker compose up` has a known issue on Docker Desktop with WSL2 when attaching containers to multiple networks simultaneously. Use `start.sh` instead.

```bash
# Build image and start all routers
bash start.sh

# Run convergence + failover tests
bash test.sh
```

## Teardown

```bash
docker rm -f router_a router_b router_c
docker network rm net_ab net_bc net_ac
```

## Manual Commands

```bash
# View live logs
docker logs -f router_a

# Check routing table inside a container
docker exec router_a ip route show

# Simulate Router C failure
docker stop router_c

# Restore Router C
docker start router_c
docker network connect --ip 10.0.3.2 net_ac router_c
docker network connect --ip 10.0.2.2 net_bc router_c
```

## Environment Variables

| Variable    | Description                              | Example                  |
|-------------|------------------------------------------|-----------------------------|
| MY_IP       | Router's primary IP (used as router_id) | 10.0.1.1                 |
| MY_SUBNETS  | Directly connected subnets (comma-sep)  | 10.0.1.0/24,10.0.3.0/24 |
| NEIGHBORS   | Neighbor IPs to send updates to         | 10.0.1.2,10.0.3.2        |

## Verified Test Results

**After convergence (15s):**
```
Router A:  10.0.2.0/24 via 10.0.1.2   (learned from B, dist=1)
Router B:  10.0.3.0/24 via 10.0.2.2   (learned from C, dist=1)
Router C:  10.0.2.0/24, 10.0.3.0/24   (both directly connected)
```

**After stopping Router C (30s):**
```
Router A:  10.0.2.0/24 via 10.0.1.2   (still reachable via B) ✔
Router B:  10.0.1.0/24, 10.0.2.0/24   (direct links only)
```

## Files

```
router.py          # Routing daemon (Bellman-Ford + Split Horizon)
Dockerfile         # Alpine + python3 + iproute2
docker-compose.yml # Triangle topology (reference)
start.sh           # Recommended startup script (WSL2-compatible)
test.sh            # Convergence and failover tests
```
