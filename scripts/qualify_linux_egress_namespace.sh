#!/usr/bin/env bash
# Runs only on a disposable GitHub-hosted runner. Never changes host firewall policy.
set -Eeuo pipefail

NS="apaa-egress-qual"
HOST_VETH="apaa-egress-host"
WORKER_VETH="apaa-egress-peer"
HOST_IP="198.18.0.1"
WORKER_IP="198.18.0.2"
HOST_V6="fd42:aa:19::1"
WORKER_V6="fd42:aa:19::2"
PROXY_PORT="3128"
SINK_PID=""

cleanup() {
  if [[ -n "${SINK_PID}" ]]; then
    kill "${SINK_PID}" 2>/dev/null || true
    wait "${SINK_PID}" 2>/dev/null || true
  fi
  sudo ip netns del "${NS}" 2>/dev/null || true
  sudo ip link del "${HOST_VETH}" 2>/dev/null || true
}
trap cleanup EXIT

for cmd in ip nft python3; do
  command -v "$cmd" >/dev/null || { echo "missing required command: $cmd" >&2; exit 2; }
done
sudo -n true

# Isolated namespace + veth. No host firewall chains or rules are edited.
sudo ip netns add "${NS}"
sudo ip link add "${HOST_VETH}" type veth peer name "${WORKER_VETH}"
sudo ip link set "${WORKER_VETH}" netns "${NS}"
sudo ip addr add "${HOST_IP}/30" dev "${HOST_VETH}"
sudo ip -6 addr add "${HOST_V6}/64" dev "${HOST_VETH}"
sudo ip link set "${HOST_VETH}" up
sudo ip -n "${NS}" addr add "${WORKER_IP}/30" dev "${WORKER_VETH}"
sudo ip -n "${NS}" -6 addr add "${WORKER_V6}/64" dev "${WORKER_VETH}"
sudo ip -n "${NS}" link set lo up
sudo ip -n "${NS}" link set "${WORKER_VETH}" up
sudo ip -n "${NS}" route add default via "${HOST_IP}"

# Host-side sink detects any prohibited TCP connection or UDP datagram.
python3 - <<'PY' &
import selectors, socket, sys, time
sel = selectors.DefaultSelector()
sockets = []
for family, host, ports, kind in [
    (socket.AF_INET, "198.18.0.1", (443, 53, 3129), socket.SOCK_STREAM),
    (socket.AF_INET, "198.18.0.1", (53, 443), socket.SOCK_DGRAM),
    (socket.AF_INET6, "fd42:aa:19::1", (3128,), socket.SOCK_STREAM),
]:
    for port in ports:
        s = socket.socket(family, kind)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            if kind == socket.SOCK_STREAM:
                s.listen(4)
            s.setblocking(False)
            sel.register(s, selectors.EVENT_READ)
            sockets.append(s)
        except OSError as exc:
            print(f"cannot bind test sink {host}:{port}: {exc}", file=sys.stderr)
            sys.exit(2)
deadline = time.monotonic() + 5
try:
    while time.monotonic() < deadline:
        for key, _ in sel.select(0.2):
            sock = key.fileobj
            if sock.type & socket.SOCK_STREAM:
                conn, _ = sock.accept()
                conn.close()
            else:
                sock.recvfrom(2048)
            print("FAIL: prohibited packet reached host-side sink", file=sys.stderr)
            sys.exit(1)
finally:
    for s in sockets:
        s.close()
PY
SINK_PID=$!
sleep 0.3

# The only accepted worker output is TCP to the exact proxy endpoint.
sudo ip netns exec "${NS}" nft -f - <<NFT
table inet apaa_egress {
  chain output {
    type filter hook output priority 0; policy drop;
    ip daddr ${HOST_IP} tcp dport ${PROXY_PORT} counter accept
  }
}
NFT

python3 - <<'PY' &
import socket
s = socket.socket()
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("198.18.0.1", 3128))
s.listen(2)
s.settimeout(4)
c, _ = s.accept()
c.close()
s.close()
PY
PROXY_PID=$!
sleep 0.2
sudo ip netns exec "${NS}" python3 -c 'import socket; s=socket.create_connection(("198.18.0.1",3128),timeout=2); s.close()'
wait "${PROXY_PID}"

# Prohibited IPv4 TCP/UDP and IPv6 TCP attempts must not reach the host sink.
sudo ip netns exec "${NS}" python3 - <<'PY'
import socket
probes = [
    (socket.AF_INET, socket.SOCK_STREAM, "198.18.0.1", 443),
    (socket.AF_INET, socket.SOCK_STREAM, "198.18.0.1", 53),
    (socket.AF_INET, socket.SOCK_STREAM, "198.18.0.1", 3129),
    (socket.AF_INET, socket.SOCK_DGRAM, "198.18.0.1", 53),
    (socket.AF_INET, socket.SOCK_DGRAM, "198.18.0.1", 443),
    (socket.AF_INET6, socket.SOCK_STREAM, "fd42:aa:19::1", 3128),
]
for family, kind, host, port in probes:
    s = socket.socket(family, kind)
    s.settimeout(0.5)
    try:
        if kind == socket.SOCK_STREAM:
            try:
                s.connect((host, port))
            except OSError:
                pass
            else:
                raise SystemExit(f"FAIL: unexpected connection to {host}:{port}")
        else:
            s.sendto(b"blocked-egress-probe", (host, port))
    finally:
        s.close()
PY

# If any forbidden TCP connection or UDP packet escaped, the sink exits nonzero.
wait "${SINK_PID}"
SINK_PID=""
sudo ip netns exec "${NS}" nft list chain inet apaa_egress output
echo "PASS: disposable namespace allowed exact TCP proxy only; direct TCP, DNS, UDP/QUIC and IPv6 probes were blocked."
