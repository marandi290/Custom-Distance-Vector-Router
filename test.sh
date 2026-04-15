#!/bin/bash
# Test 1: Verify initial convergence
echo "=== Waiting for convergence (15s) ==="
sleep 15

echo ""
echo "=== Router A routing table ==="
docker exec router_a ip route show

echo ""
echo "=== Router B routing table ==="
docker exec router_b ip route show

echo ""
echo "=== Router C routing table ==="
docker exec router_c ip route show

# Test 2: Connectivity ping
echo ""
echo "=== Ping: Router A -> 10.0.2.0/24 (via B or C) ==="
docker exec router_a ping -c 3 10.0.2.1

echo ""
echo "=== Ping: Router A -> 10.0.3.2 (Router C direct) ==="
docker exec router_a ping -c 3 10.0.3.2

# Test 3: Failover — stop Router C
echo ""
echo "=== Stopping Router C to simulate link failure ==="
docker stop router_c

echo "=== Waiting for re-convergence (30s) ==="
sleep 30

echo ""
echo "=== Router A routing table after Router C stops ==="
docker exec router_a ip route show

echo ""
echo "=== Router B routing table after Router C stops ==="
docker exec router_b ip route show

echo ""
echo "=== Ping: Router A -> 10.0.2.1 (should still work via B) ==="
docker exec router_a ping -c 3 10.0.2.1

echo ""
echo "=== Test complete ==="
