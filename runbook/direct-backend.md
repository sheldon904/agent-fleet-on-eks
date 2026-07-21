# Direct backend — Docker Compose or systemd

The fleet doesn't require Kubernetes. A customer's platform team may standardise on **Docker, Kubernetes, OR
direct**, here are the same services on plain Docker and on systemd. Same images, same env
contract, same trust flow — you lose the cluster-level network policy and CSI secret mounting,
so you enforce isolation and secret handling with host tooling instead.

## Option A — Docker Compose

The compose file is the whole fleet: [`services/docker-compose.yml`](../services/docker-compose.yml).

```bash
cd services
export GOV_HMAC_SECRET=$(openssl rand -hex 32)
export NOTIFY_HMAC_SECRET=$(openssl rand -hex 32)   # shared by runner + notify-bridge

docker compose up --build -d
docker compose ps

# enqueue a ticket
curl -sS -XPOST localhost:8083/enqueue -d '{"id":"TCK-1","title":"demo","body":"hello"}'
docker compose logs governance-mcp | tail            # token.issued -> token.consumed
```

Ports: governance `8081`, notify-bridge `8080`, runner `8082`, scheduler `8083`. The internal
DNS names (`governance-mcp`, etc.) resolve on the compose network exactly like in-cluster
service names, so no env changes are needed between Docker and Kubernetes.

Tear down: `docker compose down -v`.

### Isolation on Docker
The Kubernetes default-deny NetworkPolicy has no direct Docker equivalent. Approximate it with
a dedicated user-defined bridge network (compose creates one) and by **not** publishing ports
you don't need externally — publish only the scheduler's `8083` and keep governance/runner
internal by removing their `ports:` mappings.

## Option B — systemd (no container runtime)

Run the services directly under systemd on a host. Secrets come from an
`EnvironmentFile` with `0600` permissions instead of the CSI driver.

`/etc/agent-fleet/governance.env` (mode 0600):
```ini
GOV_HMAC_SECRET=<hex>
TRUST_LADDER={"scheduler":["open_pr"]}
AUDIT_LOG_PATH=/var/lib/agent-fleet/audit.log
PORT=8081
```

`/etc/systemd/system/agent-governance.service`:
```ini
[Unit]
Description=agent-fleet governance-mcp
After=network-online.target

[Service]
Type=simple
User=agent
EnvironmentFile=/etc/agent-fleet/governance.env
WorkingDirectory=/opt/agent-fleet/governance-mcp
ExecStart=/usr/bin/python3 app.py
Restart=on-failure
# hardening (host-level equivalents of the pod securityContext)
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/agent-fleet

[Install]
WantedBy=multi-user.target
```

The runner and scheduler follow the same pattern (`ExecStart=/usr/bin/python3 app.py`, their own
env files pointing `GOVERNANCE_URL`/`RUNNER_URL`/`NOTIFY_URL` at `http://localhost:<port>`). The
notify-bridge is a single static Go binary:

`/etc/systemd/system/agent-notify.service`:
```ini
[Unit]
Description=agent-fleet notify-bridge
After=network-online.target

[Service]
Type=simple
User=agent
EnvironmentFile=/etc/agent-fleet/notify.env
ExecStart=/opt/agent-fleet/bin/notify-bridge
Restart=on-failure
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now agent-governance agent-notify agent-runner agent-scheduler
sudo journalctl -u agent-governance -f       # the audit stream
```

### Isolation on systemd
Use the `systemd` sandboxing directives shown (`ProtectSystem`, `NoNewPrivileges`, etc.) plus
host firewall rules (nftables/iptables) to replicate the default-deny egress: allow only
loopback between services and 443 out to GitHub/ntfy/Telegram.

## Which to use

| | Kubernetes | Docker Compose | systemd |
|---|---|---|---|
| Network default-deny | NetworkPolicy (built in) | manual (bridge + no published ports) | host firewall |
| Secret delivery | Secrets Store CSI | env / compose secrets | `EnvironmentFile` 0600 |
| Scaling / self-heal | HPA + node autoscale + probes | `restart:` policy | `Restart=on-failure` |
| Best for | production fleets | a single-box demo or dev | an appliance / air-gapped host |
