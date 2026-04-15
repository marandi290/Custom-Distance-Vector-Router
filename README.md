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

| Network  | Subnet       | Connected Routers |
|----------|--------------|-------------------|
| net_ab   | 10.0.1.0/24  | A, B              |
| net_bc   | 10.0.2.0/24  | B, C              |
| net_ac   | 10.0.3.0/24  | A, C              |

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

```bash
# Build and start all routers
docker compose up --build -d

# Run tests (convergence + failover)
bash test.sh
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
```

## Environment Variables

| Variable    | Description                              | Example                  |
|-------------|------------------------------------------|--------------------------|
| MY_IP       | Router's primary IP (used as router_id) | 10.0.1.1                 |
| MY_SUBNETS  | Directly connected subnets (comma-sep)  | 10.0.1.0/24,10.0.3.0/24 |
| NEIGHBORS   | Neighbor IPs to send updates to         | 10.0.1.2,10.0.3.2        |

## Files

```
router.py          # Routing daemon
Dockerfile         # Alpine + python3 + iproute2
docker-compose.yml # Full triangle topology
test.sh            # Convergence and failover tests
```
