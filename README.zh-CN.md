# Pyttyd

[English](README.md) | **中文**

在浏览器中共享**本机**终端的 Web 工具。直接在物理机/服务器上运行，暴露真实的 Shell 与环境。基于 FastAPI + xterm.js，支持登录认证、可拆分多终端、工具栏与在线配置管理。

> **安全提示**：Web 终端等同于远程 Shell 访问，请务必设置强密码，仅在可信网络中使用，生产环境建议配合 HTTPS 反向代理。

## 特性

- 现代化登录界面与会话认证
- 可横向/纵向拆分的多终端面板
- 终端工具栏：新建、拆分、清屏、复制/粘贴、重连、字体调节、主题切换
- 命令行初始化与配置管理（`pyttyd init` / `pyttyd config`）
- Web 端设置面板，支持保存配置与一键重启服务
- PTY 窗口尺寸同步（resize）

## 快速开始

### pip 安装

```bash
pip install pyttyd

# 初始化（生成用户名、密码、监听地址等）
pyttyd init

# 启动服务
pyttyd
```

初始化后会输出类似：

```text
Config file : ~/.config/pyttyd/config.json
Listen      : http://0.0.0.0:8221
Username    : admin_abc123
Password    : xxxxx
```

浏览器访问 `http://<host>:8221` 登录即可。

```bash
# 前台运行（Ctrl+C 停止）
pyttyd

# 后台运行
pyttyd start
pyttyd status
pyttyd stop
```

日志：`~/.config/pyttyd/pyttyd.log`

> Pyttyd 设计为在**宿主机**上直接运行（pip 安装或源码安装），共享本机真实的 Shell、主目录与环境，而非隔离的容器环境。

## 命令行

| 命令 | 说明 |
|------|------|
| `pyttyd` | 启动 Web 终端服务（前台） |
| `pyttyd start` | 后台启动 |
| `pyttyd stop` | 停止后台进程 |
| `pyttyd status` | 查看后台运行状态 |
| `pyttyd init` | 初始化配置，生成随机用户名/密码 |
| `pyttyd init --username admin --password secret` | 指定账号密码 |
| `pyttyd config show` | 查看当前配置 |
| `pyttyd config show --json` | JSON 格式输出 |
| `pyttyd config set host 0.0.0.0` | 修改单项配置 |
| `pyttyd config set port 9000` | 修改端口 |
| `pyttyd config edit` | 用 `$EDITOR` 打开配置文件 |
| `pyttyd config path` | 显示配置文件路径 |
| `pyttyd config reset-password` | 重置密码 |
| `pyttyd version` | 显示版本 |

### 配置文件

默认路径：`~/.config/pyttyd/config.json`

可通过环境变量覆盖：

```bash
export PYTTYD_CONFIG=/etc/pyttyd/config.json
pyttyd
```

主要字段：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `host` | 监听地址 | `0.0.0.0` |
| `port` | 监听端口 | `8221` |
| `username` | 登录用户名 | 初始化时生成 |
| `password_hash` | 密码哈希 | 初始化时生成 |
| `shell` | 默认 Shell | `/bin/bash` |
| `cwd` | 工作目录 | 用户主目录 |
| `title` | 页面标题 | `Pyttyd` |
| `max_terminals` | 最大并发终端数 | `4` |

修改 `host` / `port` 后需重启服务（Web 设置页可一键重启）。

## Web 界面

登录后可用工具栏：

- **New** — 新建终端
- **Split H / Split V** — 横向/纵向拆分当前面板
- **Close** — 关闭当前面板
- **Clear / Copy / Paste / Reconnect** — 常用操作
- **Settings** — 在线修改配置，保存后点击 **Restart server** 应用

## 生产部署建议

1. **反向代理 + HTTPS**：使用 Nginx/Caddy 终止 TLS，避免明文传输密码与终端数据。
2. **限制访问**：防火墙仅放行可信 IP；不要将服务直接暴露到公网。
3. **强密码**：使用 `pyttyd config reset-password` 定期轮换。
4. **进程管理**：配合 systemd 在开机时自动启动、异常退出后重启。

### systemd 示例

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

### Nginx 反向代理示例

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

## 开发

```bash
git clone https://github.com/zhanglaiya/pyttyd.git
cd pyttyd
pip install -e .

pyttyd init --force
pyttyd
```

健康检查：`GET /health`

## 平台

仅支持 Linux / macOS（依赖 POSIX PTY）。Windows 原生不支持。

## 技术栈

- 后端：FastAPI、uvicorn
- 前端：xterm.js、原生 JS/CSS
- 终端：POSIX PTY + bash

## 相关项目

- [ttyd](https://github.com/tsl0922/ttyd) — C 实现，功能成熟
- [gotty](https://github.com/yudai/gotty) — Go 实现

## License

Apache 2.0
