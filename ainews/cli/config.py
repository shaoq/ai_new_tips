"""CLI config 子命令."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.prompt import Confirm, Prompt

from ainews.config.loader import clear_config_cache, get_config, save_config, set_config_value

config_app = typer.Typer(help="配置管理", no_args_is_help=True)


@config_app.command("init")
def config_init() -> None:
    """交互式初始化配置."""
    config = get_config()

    if config.config_path.exists():
        overwrite = Confirm.ask("配置文件已存在，是否覆盖？", default=False)
        if not overwrite:
            rprint("[yellow]已取消[/yellow]")
            return

    rprint("[bold]AI News Tips 配置向导[/bold]\n")

    # LLM 配置
    rprint("[bold cyan]--- LLM 配置 ---[/bold cyan]")
    config.llm.base_url = Prompt.ask("LLM Base URL", default=config.llm.base_url)
    config.llm.api_key = Prompt.ask("LLM API Key", default=config.llm.api_key)
    config.llm.model = Prompt.ask("LLM Model", default=config.llm.model)
    max_tokens_str = Prompt.ask("Max Tokens", default=str(config.llm.max_tokens))
    config.llm.max_tokens = int(max_tokens_str)

    # Obsidian 配置
    rprint("\n[bold cyan]--- Obsidian 配置 ---[/bold cyan]")
    config.obsidian.vault_path = Prompt.ask("Vault Path", default=config.obsidian.vault_path)
    config.obsidian.api_key = Prompt.ask("Obsidian API Key", default=config.obsidian.api_key)
    port_str = Prompt.ask("Obsidian Port", default=str(config.obsidian.port))
    config.obsidian.port = int(port_str)

    # 钉钉配置
    rprint("\n[bold cyan]--- 钉钉配置 ---[/bold cyan]")
    config.dingtalk.webhook_url = Prompt.ask("DingTalk Webhook URL", default=config.dingtalk.webhook_url)
    config.dingtalk.secret = Prompt.ask("DingTalk Secret", default=config.dingtalk.secret)

    save_config(config)
    clear_config_cache()
    rprint(f"\n[green]配置已保存到 {config.config_path}[/green]")


@config_app.command("show")
def config_show() -> None:
    """显示当前配置（敏感字段脱敏）."""
    config = get_config()
    masked = config.mask_secrets()
    rprint(masked.model_dump())


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="配置键（点分路径，如 llm.model）"),
    value: str = typer.Argument(help="配置值"),
) -> None:
    """修改配置项（点分路径）."""
    config = get_config()
    try:
        config = set_config_value(config, key, value)
        save_config(config)
        clear_config_cache()
        rprint(f"[green]已更新 {key} = {value}[/green]")
    except (KeyError, ValueError) as e:
        rprint(f"[red]错误: {e}[/red]")
        raise typer.Exit(1) from e
