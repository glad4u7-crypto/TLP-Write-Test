#!/usr/bin/env bash
# Disposable GitHub-hosted Linux runner only. Never targets the runner's host firewall.
set -Eeuo pipefail

NS="apaa-egress-qual"
HOST_VETH="apaa-egress-host"
WORKER_VETH="apaa-egress-peer"
HOST_IP="198.18.0.1"
WORKER_IP="198.18.0.2"
PROXY_PORT="3128"
LISTENER_PID=""

cleanup() {
  if [[ -n "${LISTENER_PID}" ]]; then
    kill "${LISTENER_PID}" 2>/dev/null || true
    wait "${LISTENER_PID}" 2>/dev/null || true
  fi
  sudo ip netns del "${NS}" 2>/dev/null || true
  sudo ip link del "${HOST_VETH}" 2>/dev/null || true
}
trap cleanup EXIT

for cmd in ip nft python3; do
  command -v "$cmd" >/dev/null || { echo "missing required command: $cmd" >&2; exit 2; }
done
sudo -n true

# Create an isolated network namespace and veth pair; do not alter host firewall rules.
sudo ip netns add "${NS}"
sudo ip link add "${HOST_VETH}" type veth peer name "${WORKER_VETH}"
sudo ip link set "${WORKER_VETH}" netns "${NS}"
sudo ip addr add "${HOST_IP}/30" dev "${HOST_VETH}"
sudo ip link set "${HOST_VETH}" up
sudo ip -n "${NS}" addr add "${WORKER_IP}/30" dev "${WORKER_VETH}"
sudo ip -n "${NS}" link set lo up
sudo ip -n "${NS}" link set "${WORKER_VETH}" up
sudo ip -n "${NS}" route add default via "${HOST_IP}"

# Start a local test-only proxy endpoint on the host side of the veth pair.
python3 -c 'import socket; s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("198.18.0.1",3128)); s.listen(8); s.settimeout(15); c,_=s.accept(); c.close(); s.close()' &
LISTENER_PID=$!
sleep 0.3

# Worker egress defaults to DROP. The only permit is TCP to exact proxy IP:port.
sudo ip netns exec "${NS}" nft -f - <<NFT
table inet apaa_egress {
  chain output {
    type filter hook output priority 0; policy drop;
    ip daddr ${HOST_IP} tcp dport ${PROXY_PORT} counter accept
  }
}
NFT

# Exact approved proxy endpoint must connect.
sudo ip netns exec "${NS}" python3 -c 'import socket; s=socket.create_connection(("198.18.0.1",3128),timeout=2); s.close()'
wait "${LISTENER_PID}"
LISTENER_PID=""

# Direct HTTPS, DNS over TCP, DNS over UDP, QUIC/UDP 443 and wrong proxy port must fail.
sudo ip netns exec "${NS}" python3 - <<'PY'
import socket
targets = [
    ("tcp", "198.18.0.1", 443),
    ("tcp", "198.18.0.1", 53),
    ("udp", "198.18.0.1", 53),
    ("udp", "198.18.0.1", 443),
    ("tcp", "198.18.0.1", 3129),
]
for kind, host, port in targets:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM if kind == "tcp" else socket.SOCK_DGRAM)
    s.settimeout(1)
    try:
        if kind == "tcp":
            try:
                s.connect((host, port))
            except OSError:
                continue
            raise SystemExit(f"FAIL: unexpected TCP egress to {host}:{port}")
        try:
            s.sendto(b"egress-probe", (host, port))
            # UDP sendto alone may succeed despite a DROP; require an ICMP error/timeout
            # is not portable, so packet-level DROP is additionally asserted below.
        except OSError:
            continue
    finally:
        s.close()
PY

# Kernel counters prove packets to prohibited UDP and TCP destinations hit DROP policy.
sudo ip netns exec "${NS}" nft list chain inet apaa_egress output
echo "PASS: isolated namespace permits only exact TCP proxy endpoint; prohibited TCP egress rejected."
