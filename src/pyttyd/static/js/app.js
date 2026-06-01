(function () {
  "use strict";

  const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const state = {
    activePaneId: null,
    paneCounter: 0,
    panes: new Map(),
    fontSize: 14,
    lightTheme: false,
    maxTerminals: 4,
  };

  function createFitAddon() {
    if (typeof FitAddon === "function") {
      return new FitAddon();
    }
    if (FitAddon && typeof FitAddon.FitAddon === "function") {
      return new FitAddon.FitAddon();
    }
    throw new Error("FitAddon failed to load");
  }

  function sendToTerminal(pane, data, extra) {
    if (!pane.ws || pane.ws.readyState !== WebSocket.OPEN) return;
    pane.ws.send(JSON.stringify(Object.assign({ input: data }, extra || {})));
  }

  class TerminalPane {
    constructor(id, container) {
      this.id = id;
      this.container = container;
      this.ws = null;
      this.connected = false;
      this.term = new Terminal({
        cursorBlink: true,
        cursorStyle: "bar",
        convertEol: false,
        fontSize: state.fontSize,
        fontFamily: '"JetBrains Mono", "SF Mono", "Menlo", "PingFang SC", "Microsoft YaHei", monospace',
        theme: terminalTheme(),
      });
      this.fitAddon = createFitAddon();
      this.term.loadAddon(this.fitAddon);
      this.render();
      this.connect();
    }

    render() {
      this.container.innerHTML = `
        <div class="pane-header">
          <span class="pane-title">bash #${this.id}</span>
          <span class="pane-status" title="Connection status"></span>
        </div>
        <div class="pane-body"></div>
      `;
      this.headerEl = this.container.querySelector(".pane-header");
      this.statusEl = this.container.querySelector(".pane-status");
      this.bodyEl = this.container.querySelector(".pane-body");
      this.term.open(this.bodyEl);
      this.fit();

      this.headerEl.addEventListener("mousedown", () => setActivePane(this.id));
      this.container.addEventListener("mousedown", () => setActivePane(this.id));
      this.term.onFocus = () => setActivePane(this.id);
      this.term.attachCustomKeyEventHandler((event) => {
        if (event.type !== "keydown") return true;
        const key = event.key.toLowerCase();
        if (event.ctrlKey && key === "c") {
          if (this.term.hasSelection()) {
            return true;
          }
          event.preventDefault();
          sendToTerminal(this, "\x03", { signal: "SIGINT" });
          return false;
        }
        if (event.ctrlKey && key === "z") {
          event.preventDefault();
          if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ signal: "SIGTSTP" }));
          }
          return false;
        }
        return true;
      });
      this.term.onData((data) => {
        if (data.includes("\x03")) {
          sendToTerminal(this, "\x03", { signal: "SIGINT" });
          return;
        }
        sendToTerminal(this, data);
      });
      this.term.onResize((size) => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          this.ws.send(JSON.stringify({ resize: [size.cols, size.rows] }));
        }
      });
    }

    wsUrl() {
      const params = new URLSearchParams({
        rows: String(this.term.rows),
        cols: String(this.term.cols),
      });
      return `${wsProtocol}//${window.location.host}/ws/tty?${params.toString()}`;
    }

    connect() {
      this.setStatus("connecting");
      this.ws = new WebSocket(this.wsUrl());
      this.ws.binaryType = "arraybuffer";
      this.ws.onopen = () => {
        this.connected = true;
        this.setStatus("connected");
        updateGlobalStatus();
        this.fit();
        this.ws.send(JSON.stringify({ resize: [this.term.cols, this.term.rows] }));
      };
      this.ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          this.term.write(new Uint8Array(event.data));
        } else {
          this.term.write(event.data);
        }
      };
      this.ws.onclose = (event) => {
        this.connected = false;
        this.setStatus("disconnected");
        updateGlobalStatus();
        if (event.reason) {
          this.term.writeln(`\r\n\x1b[31m[disconnected] ${event.reason}\x1b[0m`);
        }
      };
      this.ws.onerror = () => {
        this.connected = false;
        this.setStatus("disconnected");
        updateGlobalStatus();
      };
    }

    reconnect() {
      if (this.ws) {
        this.ws.close();
      }
      this.connect();
    }

    close() {
      if (this.ws) {
        this.ws.close();
      }
      this.term.dispose();
    }

    fit() {
      if (!this.bodyEl) return;
      this.fitAddon.fit();
    }

    setStatus(status) {
      this.statusEl.className = `pane-status ${status === "connected" ? "connected" : status === "disconnected" ? "disconnected" : ""}`;
    }

    focus() {
      this.term.focus();
    }

    clear() {
      this.term.clear();
    }
  }

  function terminalTheme() {
    if (state.lightTheme) {
      return {
        background: "#ffffff",
        foreground: "#1f2328",
        cursor: "#1f2328",
        selectionBackground: "#b6d4fe",
      };
    }
    return {
      background: "#0d1117",
      foreground: "#e6edf3",
      cursor: "#e6edf3",
      selectionBackground: "#264f78",
    };
  }

  function setActivePane(id) {
    state.activePaneId = id;
    document.querySelectorAll(".pane-leaf").forEach((el) => {
      el.classList.toggle("active", el.dataset.paneId === String(id));
    });
    const pane = state.panes.get(id);
    if (pane) pane.focus();
  }

  function updateGlobalStatus() {
    const badge = document.getElementById("conn-status");
    const anyConnected = [...state.panes.values()].some((pane) => pane.connected);
    badge.textContent = anyConnected ? "connected" : "disconnected";
    badge.className = `badge ${anyConnected ? "connected" : "disconnected"}`;
    updatePaneLimit();
  }

  function updatePaneLimit() {
    const el = document.getElementById("pane-limit");
    if (!el) return;

    const count = state.panes.size;
    const max = state.maxTerminals;
    const atLimit = count >= max;

    el.textContent = atLimit
      ? `Terminals ${count}/${max} · limit reached`
      : `Terminals ${count}/${max}`;
    el.classList.toggle("at-limit", atLimit);
    el.title = atLimit
      ? `Maximum ${max} concurrent terminals. Increase in Settings (Max terminals) and restart, or run: pyttyd config set max_terminals N`
      : `Concurrent terminal sessions: ${count} of ${max} maximum`;

    ["btn-new", "btn-split-h", "btn-split-v"].forEach((id) => {
      const btn = document.getElementById(id);
      if (btn) btn.disabled = atLimit;
    });
  }

  function createPaneNode(id) {
    const node = document.createElement("div");
    node.className = "pane-leaf";
    if (id != null) {
      node.dataset.paneId = String(id);
    }
    return node;
  }

  function canOpenPane() {
    return state.panes.size < state.maxTerminals;
  }

  function mountPane(container) {
    state.paneCounter += 1;
    const id = state.paneCounter;
    container.dataset.paneId = String(id);
    const pane = new TerminalPane(id, container);
    state.panes.set(id, pane);
    setActivePane(id);
    pane.fit();
    updatePaneLimit();
    return pane;
  }

  function addPane(targetContainer) {
    if (!canOpenPane()) return null;
    const node = createPaneNode();
    targetContainer.appendChild(node);
    return mountPane(node);
  }

  function splitActive(direction) {
    const active = resolveActivePane();
    if (!active) return;
    if (!canOpenPane()) return;

    const keepActiveId = active.id;
    const leaf = active.container;
    const parent = leaf.parentElement;
    if (!parent) return;

    const split = document.createElement("div");
    split.className = `pane-split ${direction}`;

    const sibling = createPaneNode();
    parent.replaceChild(split, leaf);
    split.appendChild(leaf);
    split.appendChild(sibling);
    mountPane(sibling);
    setActivePane(keepActiveId);
    window.requestAnimationFrame(() => {
      resizeAll();
      window.requestAnimationFrame(resizeAll);
    });
    setTimeout(resizeAll, 100);
  }

  function closeActivePane() {
    if (state.panes.size <= 1) return;
    const active = resolveActivePane();
    if (!active) return;

    const leaf = active.container;
    const parent = leaf.parentElement;
    if (!parent) return;

    active.close();
    state.panes.delete(active.id);

    if (parent.classList.contains("pane-split")) {
      const sibling = [...parent.children].find((child) => child !== leaf);
      leaf.remove();
      if (sibling) {
        const grandParent = parent.parentElement;
        if (grandParent) {
          grandParent.replaceChild(sibling, parent);
        }
      } else {
        parent.remove();
      }
    } else {
      leaf.remove();
    }

    collapseLayout(document.getElementById("workspace"));

    const remaining = [...state.panes.keys()];
    if (remaining.length) {
      setActivePane(remaining[remaining.length - 1]);
    }
    resizeAll();
    updatePaneLimit();
  }

  function collapseLayout(root) {
    if (!root) return;

    root.querySelectorAll(".pane-split").forEach((split) => {
      const leaves = [...split.querySelectorAll(":scope > .pane-leaf")];
      if (leaves.length === 1) {
        const grandParent = split.parentElement;
        if (grandParent) {
          grandParent.replaceChild(leaves[0], split);
        }
      }
    });
  }

  function resizeAll() {
    state.panes.forEach((pane) => pane.fit());
  }

  function activePane() {
    return state.panes.get(state.activePaneId);
  }

  function resolveActivePane() {
    for (const [id, pane] of state.panes) {
      const root = pane.term.element;
      if (root && root.contains(document.activeElement)) {
        setActivePane(id);
        return pane;
      }
    }
    return activePane();
  }

  async function bootstrap() {
    bindToolbar();
    bindSettings();

    const me = await fetch("/api/me");
    if (!me.ok) {
      window.location.href = "/login";
      return;
    }
    const user = await me.json();
    document.getElementById("username-label").textContent = user.username;

    const cfgRes = await fetch("/api/config");
    if (cfgRes.ok) {
      const cfg = await cfgRes.json();
      state.maxTerminals = cfg.max_terminals || 4;
      updatePaneLimit();
    }

    const workspace = document.getElementById("workspace");
    workspace.className = "workspace pane-root";

    try {
      addPane(workspace);
      window.addEventListener("resize", resizeAll);
    } catch (error) {
      console.error(error);
      const badge = document.getElementById("conn-status");
      badge.textContent = "error";
      badge.className = "badge disconnected";
    }
  }

  function bindToolbar() {
    document.getElementById("btn-new").addEventListener("click", () => {
      addPane(document.querySelector(".pane-root") || document.getElementById("workspace"));
      resizeAll();
    });
    document.getElementById("btn-split-h").addEventListener("click", () => splitActive("horizontal"));
    document.getElementById("btn-split-v").addEventListener("click", () => splitActive("vertical"));
    document.getElementById("btn-close-pane").addEventListener("click", closeActivePane);
    document.getElementById("btn-clear").addEventListener("click", () => activePane()?.clear());
    document.getElementById("btn-copy").addEventListener("click", async () => {
      const pane = activePane();
      if (!pane) return;
      const selection = pane.term.getSelection();
      if (selection) {
        await navigator.clipboard.writeText(selection);
      }
    });
    document.getElementById("btn-paste").addEventListener("click", async () => {
      const pane = activePane();
      if (!pane || !pane.ws || pane.ws.readyState !== WebSocket.OPEN) return;
      const text = await navigator.clipboard.readText();
      pane.ws.send(JSON.stringify({ input: text }));
    });
    document.getElementById("btn-reconnect").addEventListener("click", () => activePane()?.reconnect());
    document.getElementById("font-size").addEventListener("input", (event) => {
      state.fontSize = Number(event.target.value);
      state.panes.forEach((pane) => {
        pane.term.options.fontSize = state.fontSize;
        pane.fit();
      });
    });
    document.getElementById("btn-theme").addEventListener("click", () => {
      state.lightTheme = !state.lightTheme;
      document.body.classList.toggle("light-theme", state.lightTheme);
      const theme = terminalTheme();
      state.panes.forEach((pane) => {
        pane.term.options.theme = theme;
      });
    });
    document.getElementById("btn-logout").addEventListener("click", async () => {
      await fetch("/api/logout", { method: "POST" });
      window.location.href = "/login";
    });
  }

  async function bindSettings() {
    const dialog = document.getElementById("settings-dialog");
    const form = document.getElementById("settings-form");
    const message = document.getElementById("settings-message");

    document.getElementById("btn-settings").addEventListener("click", async () => {
      const response = await fetch("/api/config");
      if (!response.ok) return;
      const config = await response.json();
      Object.entries(config).forEach(([key, value]) => {
        const input = form.elements.namedItem(key);
        if (input) input.value = value ?? "";
      });
      message.hidden = true;
      dialog.showModal();
    });

    document.getElementById("settings-close").addEventListener("click", () => dialog.close());
    document.getElementById("btn-restart").addEventListener("click", async () => {
      message.textContent = "Restarting server...";
      message.className = "form-message";
      message.hidden = false;
      await fetch("/api/restart", { method: "POST" });
      setTimeout(() => window.location.reload(), 1500);
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());
      if (!payload.password) delete payload.password;
      const response = await fetch("/api/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        message.textContent = "Failed to save settings.";
        message.className = "form-message error";
        message.hidden = false;
        return;
      }
      message.textContent = "Saved. Click Restart to apply host/port/max terminals changes.";
      message.className = "form-message success";
      message.hidden = false;
      if (payload.max_terminals) {
        state.maxTerminals = Number(payload.max_terminals);
        updatePaneLimit();
      }
    });
  }

  bootstrap();
})();
