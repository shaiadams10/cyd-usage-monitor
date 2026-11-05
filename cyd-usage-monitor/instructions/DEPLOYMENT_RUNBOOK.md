# Secure Deployment Runbook

Record real hostnames, filesystem paths, private addresses, emails, and tokens
only in ignored `.env` and `include/secrets.h` files.

## Runtime boundary

- Run the application, collector, and `cloudflared` together on the
  operator-selected Linux monitor server.
- Cloudflare Tunnel routes only the public dashboard hostname to
  `http://cyd-monitor-app:8000`, followed by a `http_status:404` catch-all.
- Compose does not publish dashboard port 8000. Cloudflare Access restricts
  the dashboard to explicitly allowed identities; Basic auth remains a second
  layer.
- The separate device listener is container port 8001. Compose publishes it
  only on `CYD_LAN_BIND_ADDRESS:CYD_LAN_PORT`, where the bind address is the
  server's private LAN IPv4 address from ignored `.env`.
- Never route, NAT-forward, or Tunnel the device listener to the Internet.

The two HTTP surfaces are route-isolated: dashboard/admin paths exist only on
8000, while `/api/v1/cyd-status`, `/api/v1/next-account`, and
`/api/v1/display-command` exist only on 8001 and require `CYD_API_TOKEN`.

## Dashboard login

Cloudflare Access first verifies an allowed email identity. The application
then requests HTTP Basic authentication with username `admin`. The password is
the non-empty `MONITOR_ADMIN_PASSWORD` from remote `.env`, or otherwise the
generated `/app/data/.monitor-admin-password`.

To read the generated password directly on the server:

```sh
docker compose exec -T cyd-monitor-app python3 -c \
  'from pathlib import Path; print(Path("/app/data/.monitor-admin-password").read_text().strip())'
```

Manage allowed identities in **Zero Trust > Access > Applications > CYD Usage
Monitor Dashboard > Policies**.

## Deploy and verify

Back up source and private state, preserve CLI profiles, then deploy source
without `.env`, `include/secrets.h`, build output, data, or profiles.

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Verify:

- the application is healthy and collector/cloudflared are running;
- host port 8000 is not published;
- port 8001 is listening only on the configured private LAN address;
- the public dashboard requires Cloudflare Access and Basic auth;
- device paths on the public dashboard hostname return `404`;
- the private device endpoint returns `401` without the Bearer token and `200`
  with it;
- dashboard/admin paths on private port 8001 return `404`;
- telemetry and CLI profiles survived deployment.
- if SMTP fallback is configured, **Alerts → Test fallback email** is accepted
  by the SMTP server and arrives at the intended operator mailbox;
- **Show on CYD** switches both the browser LVGL preview and physical display
  to OpenRouter, then a CLI profile selection switches both back to Usage.

Email can be configured after deployment under **Alerts → Email integration**.
Use Gmail/Google Workspace with an app password or a dedicated transactional
TLS SMTP credential. The dashboard writes `email-secret.json` only to the
private data volume. If `CYD_MONITOR_SMTP_*` environment variables are set,
they override this file and the dashboard correctly shows host-managed mode.

Keep a timestamped rollback copy until the operator approves the deployment.
Before any commit or push, run tests, the firmware build, Compose validation,
`brain check`, secret scans, and review the final diff with the operator.

## Boot recovery and maintenance

Docker's `restart: always` is insufficient if a container cannot bind its
configured private address while the host is acquiring its LAN lease. A failed
startup can also leave the app without its bridge attachment after `docker start`.
Keep the reserved LAN address and private binding; install recovery on the
selected Linux deployment host, as the existing Docker-capable deployment user:

```sh
# One-time prerequisite, requiring host administrator authorization if needed:
loginctl enable-linger "$USER"
# From the deployed project directory, after docker compose up:
python3 scripts/recover-monitor.py --project-dir "$PWD" --install
systemctl --user start cyd-monitor-recovery.service
systemctl --user is-enabled cyd-monitor-recovery.timer
systemctl --user status cyd-monitor-recovery.timer
loginctl show-user "$USER" -p Linger
```

The installer requires `Linger=yes`, installs a private helper under
`~/.local/lib/cyd-usage-monitor/`, and writes user units under
`~/.config/systemd/user/`. The timer activates 15 seconds after starting and
runs again 60 seconds after each completed check. Docker/network failures retry
on later runs. No provider authentication or model request is involved.

Only the app, collector and tunnel in the selected Compose project are checked.
Stopped containers and running containers missing their configured bridge are
recreated with `--no-deps --no-build --pull never --force-recreate`. This restores
port bindings and networking while retaining configured data/profile mounts.
Healthy, starting, paused and actively restarting containers are preserved.
Unhealthy containers are recreated only after five minutes of uptime to bound
restart frequency. Missing or scaled services require operator intervention;
the helper never creates an undeployed stack. Captured Docker error details are
not printed because they can contain private addresses or configuration values.

Pause recovery before intentional stops, edits to deployment configuration or
rollback, then resume it when maintenance finishes:

```sh
systemctl --user stop cyd-monitor-recovery.timer cyd-monitor-recovery.service
# Perform maintenance, then:
systemctl --user start cyd-monitor-recovery.timer
journalctl --user -u cyd-monitor-recovery.service --since today
```

To remove automatic recovery, run
`systemctl --user disable --now cyd-monitor-recovery.timer` and stop the service.
The containers retain their ordinary Docker restart policies.

For acceptance testing, stop only the monitor app while the timer is active.
Confirm it is recreated automatically, has its bridge and private port binding,
and becomes healthy. Recheck anonymous device requests (`401`), Bearer device
requests (`200`), dashboard authentication and device/dashboard route isolation.
Observe the physical CYD resume successful polling. This controlled service-stop
test verifies the timer; a full host power-cycle is a separate disruptive test.
