# Pyttyd

**English** | [中文](README.zh-CN.md)

A web-based terminal sharing tool. Built with FastAPI and xterm.js, featuring authentication, splittable multi-pane terminals, a toolbar, and in-browser configuration management.

> **Security notice**: A web terminal is equivalent to remote shell access. Use a strong password, deploy only on trusted networks, and put HTTPS reverse proxy in front for production.

## Features

- Modern login page with session authentication
- Horizontally / vertically splittable multi-terminal layout
- Toolbar: new, split, clear, copy/paste, reconnect, font size, theme toggle
- CLI initialization and config management (`pyttyd init` / `pyttyd config`)
- Web settings panel with save and one-click server restart
- Docker / Docker Compose deployment
- PTY window resize sync

## Quick Start

### pip install

```bash
pip install pyttyd

# Initialize (generates username, password, listen address, etc.)
pyttyd init

# Start the server
pyttyd
```

After initialization you should see output similar to:

```text
Config file : ~/.config/pyttyd/config.json
Listen      : http://0.0.0.0:8221
Username    : admin_abc123
Password    : xxxxx
```

Open `http://<host>:8221` in your browser and sign in.

### Docker Compose

```bash
git clone https://github.com/zhanglaiya/pyttyd.git
cd pyttyd

docker compose up -d --build
```

On first start, `pyttyd init` runs automatically. To view generated credentials:

```bash
docker compose logs pyttyd
# or exec into the container
docker compose exec pyttyd pyttyd config show
```

Port `8221` is mapped by default. Override with an environment variable:

```bash
PYTTYD_PORT=9000 docker compose up -d
```

### Mount host directories (optional)

To access host files from inside the container, uncomment the `$HOME` volume in `docker-compose.yml` and set `user: "${UID}:${GID}"`.

## CLI

| Command | Description |
|---------|-------------|
| `pyttyd` | Start the web terminal server |
| `pyttyd init` | Initialize config with random username/password |
| `pyttyd init --username admin --password secret` | Set credentials explicitly |
| `pyttyd config show` | Show current configuration |
| `pyttyd config show --json` | Output as JSON |
| `pyttyd config set host 0.0.0.0` | Update a single setting |
| `pyttyd config set port 9000` | Change listen port |
| `pyttyd config edit` | Open config file in `$EDITOR` |
| `pyttyd config path` | Print config file path |
| `pyttyd config reset-password` | Reset login password |
| `pyttyd version` | Show version |

### Configuration file

Default path: `~/.config/pyttyd/config.json`

Override with an environment variable:

```bash
export PYTTYD_CONFIG=/etc/pyttyd/config.json
pyttyd
```

Main fields:

| Field | Description | Default |
|-------|-------------|---------|
| `host` | Listen address | `0.0.0.0` |
| `port` | Listen port | `8221` |
| `username` | Login username | Generated on init |
| `password_hash` | Password hash | Generated on init |
| `shell` | Default shell | `/bin/bash` |
| `cwd` | Working directory | User home |
| `title` | Page title | `Pyttyd` |
| `max_terminals` | Max concurrent terminals | `4` |

Changes to `host` / `port` require a server restart (one-click restart in the web settings page).

## Web UI

After login, the toolbar provides:

- **New** — open a new terminal
- **Split H / Split V** — split the active pane horizontally or vertically
- **Close** — close the active pane
- **Clear / Copy / Paste / Reconnect** — common actions
- **Settings** — edit config in the browser; click **Restart server** to apply

## Production recommendations

1. **Reverse proxy + HTTPS**: Terminate TLS with Nginx or Caddy to avoid sending passwords and terminal data in plain text.
2. **Restrict access**: Allow only trusted IPs in your firewall; do not expose the service directly to the public internet.
3. **Strong passwords**: Rotate credentials regularly with `pyttyd config reset-password`.
4. **Process supervision**: Use systemd or Docker `restart: unless-stopped` to keep the service running.

### systemd example

```ini
[Unit]
Description=Pyttyd Web Terminal
After=network.target

[Service]
Type=simple
User=your-user
Environment=PYTTYD_CONFIG=/home/your-user/.config/pyttyd/config.json
ExecStart=/usr/local/bin/pyttyd
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### Nginx reverse proxy example

```nginx
location / {
    proxy_pass http://127.0.0.1:8221;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
}
```

## Development

```bash
git clone https://github.com/zhanglaiya/pyttyd.git
cd pyttyd
pip install -e .

pyttyd init --force
pyttyd
```

Health check: `GET /health`

## Platform

Linux and macOS only (requires POSIX PTY). Native Windows is not supported.

## Tech stack

- Backend: FastAPI, uvicorn
- Frontend: xterm.js, vanilla JS/CSS
- Terminal: POSIX PTY + bash

## Related projects

- [ttyd](https://github.com/tsl0922/ttyd) — mature C implementation
- [gotty](https://github.com/yudai/gotty) — Go implementation

## License

Apache 2.0
