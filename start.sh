#!/bin/bash
set -e

# Create networks with explicit gateways (.254) to avoid conflict with router IPs
docker network create --subnet=10.0.1.0/24 --gateway=10.0.1.254 net_ab 2>/dev/null || true
docker network create --subnet=10.0.2.0/24 --gateway=10.0.2.254 net_bc 2>/dev/null || true
docker network create --subnet=10.0.3.0/24 --gateway=10.0.3.254 net_ac 2>/dev/null || true

# Build image
docker build -t my-router .

# Start Router A on net_ab, then attach net_ac
docker run -d --name router_a --privileged --cap-add NET_ADMIN \
  --sysctl net.ipv4.ip_forward=1 \
  --network net_ab --ip 10.0.1.1 \
  -e MY_IP=10.0.1.1 \
  -e MY_SUBNETS=10.0.1.0/24,10.0.3.0/24 \
  -e NEIGHBORS=10.0.1.2,10.0.3.2 \
  my-router
docker network connect --ip 10.0.3.1 net_ac router_a

# Start Router B on net_ab, then attach net_bc
docker run -d --name router_b --privileged --cap-add NET_ADMIN \
  --sysctl net.ipv4.ip_forward=1 \
  --network net_ab --ip 10.0.1.2 \
  -e MY_IP=10.0.1.2 \
  -e MY_SUBNETS=10.0.1.0/24,10.0.2.0/24 \
  -e NEIGHBORS=10.0.1.1,10.0.2.2 \
  my-router
docker network connect --ip 10.0.2.1 net_bc router_b

# Start Router C on net_bc, then attach net_ac
docker run -d --name router_c --privileged --cap-add NET_ADMIN \
  --sysctl net.ipv4.ip_forward=1 \
  --network net_bc --ip 10.0.2.2 \
  -e MY_IP=10.0.2.2 \
  -e MY_SUBNETS=10.0.2.0/24,10.0.3.0/24 \
  -e NEIGHBORS=10.0.2.1,10.0.3.1 \
  my-router
docker network connect --ip 10.0.3.2 net_ac router_c

echo "All routers started:"
docker ps --filter "name=router_"
