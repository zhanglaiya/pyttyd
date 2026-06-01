"""Command-line interface for pyttyd."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

from pyttyd import __version__
from pyttyd.config import (
    config_path,
    get_config,
    init_config,
    load_config,
    save_config,
    set_config_path,
    set_password,
    show_config,
)

app = typer.Typer(
    add_completion=False,
    help="Pyttyd — share your terminal over the web.",
    no_args_is_help=False,
)
config_app = typer.Typer(help="View or edit configuration.")
app.add_typer(config_app, name="config")


def _ensure_initialized() -> None:
    cfg = get_config()
    if not cfg.initialized:
        typer.secho(
            "Pyttyd is not initialized. Run `pyttyd init` first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        help="Path to config file.",
        envvar="PYTTYD_CONFIG",
    ),
) -> None:
    """Run the web terminal server (default when no subcommand is given)."""
    if config:
        set_config_path(config)
        load_config(config)

    if ctx.invoked_subcommand is None:
        from pyttyd.server import run_server

        _ensure_initialized()
        run_server()


@app.command("start")
def start_cmd(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path.", envvar="PYTTYD_CONFIG"),
) -> None:
    """Start pyttyd in the background."""
    if config:
        set_config_path(config)
        load_config(config)
    _ensure_initialized()

    from pyttyd.daemon import log_file, pid_file, start_background

    pid = start_background()
    cfg = get_config()
    typer.secho(f"Pyttyd started in background (pid {pid})", fg=typer.colors.GREEN)
    typer.echo(f"  Listen : http://{cfg.host}:{cfg.port}")
    typer.echo(f"  PID    : {pid_file()}")
    typer.echo(f"  Log    : {log_file()}")


@app.command("stop")
def stop_cmd(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path.", envvar="PYTTYD_CONFIG"),
) -> None:
    """Stop the background pyttyd process."""
    if config:
        set_config_path(config)
    from pyttyd.daemon import stop_background

    if stop_background():
        typer.secho("Pyttyd stopped.", fg=typer.colors.GREEN)
    else:
        typer.secho("Pyttyd is not running.", fg=typer.colors.YELLOW)


@app.command("status")
def status_cmd(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path.", envvar="PYTTYD_CONFIG"),
) -> None:
    """Show whether pyttyd is running in the background."""
    if config:
        set_config_path(config)
        load_config(config)
    from pyttyd.daemon import log_file, pid_file, status_background

    state, pid = status_background()
    if state == "running":
        cfg = get_config()
        typer.secho(f"running (pid {pid})", fg=typer.colors.GREEN)
        typer.echo(f"  Listen : http://{cfg.host}:{cfg.port}")
    else:
        typer.echo("stopped")
    typer.echo(f"  PID file : {pid_file()}")
    typer.echo(f"  Log file : {log_file()}")


@app.command("init")
def init_cmd(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Admin username."),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Admin password."),
    host: Optional[str] = typer.Option(None, "--host", help="Listen address."),
    port: Optional[int] = typer.Option(None, "--port", help="Listen port."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config."),
) -> None:
    """Initialize pyttyd and generate credentials."""
    if config:
        set_config_path(config)

    try:
        cfg, user, plain_password = init_config(
            username=username,
            password=password,
            host=host,
            port=port,
            force=force,
        )
    except FileExistsError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho("Pyttyd initialized successfully!", fg=typer.colors.GREEN, bold=True)
    typer.echo()
    typer.echo(f"  Config file : {config_path()}")
    typer.echo(f"  Listen      : http://{cfg.host}:{cfg.port}")
    typer.echo(f"  Username    : {user}")
    typer.echo(f"  Password    : {plain_password}")
    typer.echo()
    typer.secho("View credentials anytime with: pyttyd config show", fg=typer.colors.YELLOW)
    typer.echo("Start the server with: pyttyd")
    typer.echo("Run in background:     pyttyd start")


@app.command("version")
def version_cmd() -> None:
    """Show version."""
    typer.echo(f"pyttyd {__version__}")


@config_app.command("show")
def config_show(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON."),
) -> None:
    """Show current configuration."""
    if config:
        set_config_path(config)
    cfg = load_config()
    data = show_config(cfg)
    if json_output:
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
        return
    for key, value in data.items():
        typer.echo(f"{key:16} {value}")


@config_app.command("path")
def config_path_cmd() -> None:
    """Print the config file path."""
    typer.echo(config_path())


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Config key."),
    value: str = typer.Argument(..., help="Config value."),
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Set a configuration value."""
    if config:
        set_config_path(config)
    cfg = load_config()
    if key == "password":
        set_password(cfg, value)
    else:
        cfg.apply_updates({key: value})
    save_config(cfg)
    typer.secho(f"Updated {key}", fg=typer.colors.GREEN)


@config_app.command("edit")
def config_edit(
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Open config file in $EDITOR."""
    if config:
        set_config_path(config)
    path = config_path()
    if not path.exists():
        typer.secho("Config not found. Run `pyttyd init` first.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "vi"
    subprocess.call([editor, str(path)])


@config_app.command("reset-password")
def config_reset_password(
    password: Optional[str] = typer.Option(None, "--password", "-p", help="New password."),
    config: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Reset the login password."""
    import secrets

    if config:
        set_config_path(config)
    cfg = load_config()
    plain = password or secrets.token_urlsafe(12)
    set_password(cfg, plain)
    save_config(cfg)
    typer.secho("Password updated.", fg=typer.colors.GREEN)
    typer.echo(f"  Username : {cfg.username}")
    typer.echo(f"  Password : {plain}")
    typer.echo("  Run `pyttyd config show` to view credentials later.")


def entrypoint() -> None:
    try:
        app()
    except KeyboardInterrupt:
        sys.exit(130)
