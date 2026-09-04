from __future__ import annotations

import os
from typing import Any

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt

from olx_scanner.core.config import load_config, save_config
from olx_scanner.i18n.translations import set_language, t


def run_initial_setup_wizard(console: Console | None = None) -> dict[str, Any]:
    console = console or Console()

    console.clear()
    lang_panel = (
        "[bold cyan]Select your language / Wybierz język / Оберіть мову / Sprache wählen / Абярыце мову:[/bold cyan]\n\n"
        "  [bold green]1.[/bold green] English (Default)\n"
        "  [bold green]2.[/bold green] Polski (Polish)\n"
        "  [bold green]3.[/bold green] Українська (Ukrainian)\n"
        "  [bold green]4.[/bold green] Deutsch (German)\n"
        "  [bold green]5.[/bold green] Беларуская (Belarusian)\n"
    )
    console.print(Panel(lang_panel, title="🌍 Language Selection / Wybierz Język", border_style="cyan", box=ROUNDED))

    choice_map = {"1": "en", "2": "pl", "3": "uk", "4": "de", "5": "be"}
    lang_choice = Prompt.ask("Choose [1-5]", choices=list(choice_map.keys()), default="1", console=console)
    selected_lang = choice_map[lang_choice]
    set_language(selected_lang)

    console.clear()
    welcome_panel = f"[bold white]{t('wizard_welcome')}[/bold white]\n\n[bold green]✓[/bold green] {t('lang_selected')}"
    console.print(Panel(welcome_panel, title=t("wizard_title"), border_style="bright_blue", box=ROUNDED))

    existing_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    api_key = existing_key

    if existing_key and len(existing_key) > 8:
        masked = f"{existing_key[:5]}...{existing_key[-4:]}"
        console.print(f"\n[cyan]{t('api_key_detected', masked=masked)}[/cyan]")
        use_existing = Confirm.ask(t("prompt_use_existing_api_key"), default=True, console=console)
        if not use_existing:
            api_key = Prompt.ask(f"\n{t('prompt_api_key')}", password=True, console=console).strip()
    else:
        api_key = Prompt.ask(f"\n{t('prompt_api_key')}", password=True, console=console).strip()

    proxy_menu = (
        f"{t('proxy_mode_direct')}\n"
        f"{t('proxy_mode_rotator')}\n"
        f"{t('proxy_mode_custom')}\n"
    )
    console.print(f"\n[bold yellow]{t('prompt_proxy_mode')}:[/bold yellow]")
    console.print(proxy_menu)
    proxy_choice = Prompt.ask("Choice [1-3]", choices=["1", "2", "3"], default="1", console=console)

    proxy_mode = "direct"
    custom_proxy_val = ""
    proxy_file_val = None

    if proxy_choice == "2":
        proxy_mode = "rotator"
        custom_proxy_val = "http://127.0.0.1:8080"
    elif proxy_choice == "3":
        custom_input = Prompt.ask(f"\n{t('prompt_custom_proxy_value')}", console=console).strip()
        if custom_input.endswith((".txt", ".json")):
            proxy_mode = "file"
            proxy_file_val = custom_input
        else:
            proxy_mode = "custom"
            custom_proxy_val = custom_input

    pages = IntPrompt.ask(f"\n{t('prompt_pages')}", default=3, console=console)
    pages = max(1, min(pages, 25))

    watch_mode = Confirm.ask(f"\n{t('prompt_watch_mode')}", default=False, console=console)
    interval = 120
    if watch_mode:
        interval = IntPrompt.ask(f"{t('prompt_interval')}", default=120, console=console)

    threads = IntPrompt.ask(f"\n{t('prompt_threads')}", default=8, console=console)

    config_data = {
        "language": selected_lang,
        "api_key": api_key,
        "model": "deepseek-v4-flash-vision-exp",
        "proxy_mode": proxy_mode,
        "custom_proxy": custom_proxy_val,
        "proxy_file": proxy_file_val,
        "pages": pages,
        "threads": threads,
        "watch": watch_mode,
        "interval": interval,
    }

    save_config(config_data)

    if api_key:
        os.environ["DEEPSEEK_API_KEY"] = api_key

    console.print(
        Panel(
            f"{t('setup_saved_msg')}\n\n[bold white]{t('press_enter_to_start')}[/bold white]",
            title=t("setup_complete_title"),
            border_style="green",
            box=ROUNDED,
        )
    )
    try:
        input()
    except Exception:
        pass

    return config_data


def get_or_init_config(force_setup: bool = False, console: Console | None = None) -> dict[str, Any]:
    console = console or Console()
    existing = load_config()

    if force_setup or existing is None:
        return run_initial_setup_wizard(console=console)

    set_language(existing.get("language", "en"))
    return existing
