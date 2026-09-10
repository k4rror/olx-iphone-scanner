from __future__ import annotations

import sys
from typing import Any

from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from olx_scanner.core.config import save_config
from olx_scanner.core.pricing import (
    COST_PER_OFFER_STANDARD_USD,
    ITEMS_PER_PAGE,
    calculate_deepseek_cost,
)
from olx_scanner.core.regions import (
    VOIVODESHIPS,
    get_region_display_name,
    normalize_region,
)
from olx_scanner.scraper.client import TLSScraper


def render_voivodeship_table() -> Table:
    table = Table(
        title="[bold cyan]Wybierz Województwo / Voivodeship[/bold cyan]",
        box=ROUNDED,
        border_style="cyan",
        header_style="bold bright_cyan",
        show_lines=False,
    )
    table.add_column("Nr", justify="right", style="bold yellow", width=4)
    table.add_column("Województwo (PL)", style="white")
    table.add_column("Slug OLX", style="dim cyan")
    table.add_column("Nr", justify="right", style="bold yellow", width=4)
    table.add_column("Województwo (PL)", style="white")
    table.add_column("Slug OLX", style="dim cyan")

    keys = list(VOIVODESHIPS.keys())
    half = (len(keys) + 1) // 2

    for i in range(half):
        slug1 = keys[i]
        name1 = VOIVODESHIPS[slug1]
        idx1 = i + 1

        idx2_s, name2, slug2 = "", "", ""
        if i + half < len(keys):
            slug2 = keys[i + half]
            name2 = VOIVODESHIPS[slug2]
            idx2_s = str(i + half + 1)

        table.add_row(str(idx1), name1, slug1, idx2_s, name2, slug2)

    return table


def run_session_configuration_flow(
    console: Console,
    scraper: TLSScraper,
    existing_cfg: dict[str, Any],
) -> dict[str, Any]:
    console.clear()
    console.print(
        Panel(
            "[bold white]Witaj w konfiguratorze sesji OLX iPhone Scanner![/bold white]\n"
            "[dim]Dostosuj parametry skanowania, obszar poszukiwań oraz zatwierdź koszt API.[/dim]",
            title="⚙️ KONFIGURACJA SESJI SKANOWANIA",
            border_style="bright_blue",
            box=ROUNDED,
        )
    )

    # 1. Opcje skanowania
    console.print("\n[bold cyan]1. Opcje działania i wydajności skanera[/bold cyan]")
    default_watch = existing_cfg.get("watch", False)
    console.print("  [bold green]1.[/bold green] Pojedynczy skan (zbada zadaną liczbę stron i zakończy działanie)")
    console.print("  [bold green]2.[/bold green] Ciągły monitoring w tle (Watch mode - cykliczne sprawdzanie)")

    mode_choice = Prompt.ask("Wybierz tryb", choices=["1", "2"], default="2" if default_watch else "1", console=console)
    watch_mode = mode_choice == "2"

    interval_sec = existing_cfg.get("interval", 120)
    if watch_mode:
        interval_sec = IntPrompt.ask("  Interwał sprawdzania w trybie ciągłym (sekundy)", default=interval_sec, console=console)

    default_threads = existing_cfg.get("threads", 8)
    threads_count = IntPrompt.ask("  Liczba równoległych wątków analizy AI DeepSeek", default=default_threads, console=console)

    # 2. Wybór województwa
    console.print("\n[bold cyan]2. Obszar wyszukiwania (Województwo)[/bold cyan]")
    console.print(render_voivodeship_table())
    console.print("  [bold green] 0.[/bold green] [bold white]Cała Polska[/bold white] (brak filtra regionalnego)\n")

    keys = list(VOIVODESHIPS.keys())
    saved_region = existing_cfg.get("region")
    default_input = "0"
    if saved_region in keys:
        default_input = str(keys.index(saved_region) + 1)

    region_prompt_val = Prompt.ask("Wpisz numer [0-16] lub nazwę województwa", default=default_input, console=console).strip()

    selected_slug: str | None = None
    if region_prompt_val.isdigit():
        num = int(region_prompt_val)
        if 1 <= num <= len(keys):
            selected_slug = keys[num - 1]
    else:
        selected_slug = normalize_region(region_prompt_val)

    region_display = get_region_display_name(selected_slug, default_label="Cała Polska")
    console.print(f"[green]✓ Wybrano:[/green] [bold white]{region_display}[/bold white]")

    # 3. Live Probe do OLX
    console.print()
    with console.status(f"[bold yellow]Łączenie z OLX.pl i sprawdzanie ofert dla: {region_display}...[/bold yellow]", spinner="dots"):
        total_items, available_pages = scraper.probe_search_meta(region=selected_slug)

    if total_items == 0:
        console.print(f"[bold red]⚠ Nie udało się wykryć ogłoszeń lub brak ofert dla: {region_display}![/bold red]")
        total_items = 52
        available_pages = 3
    else:
        console.print(
            f"[bold green]✓ Wykryto w OLX:[/bold green] [bold white]{total_items}[/bold white] ogłoszeń "
            f"(około [bold cyan]{available_pages}[/bold cyan] stron po 52 przedmioty)"
        )

    # 4. Liczba stron i dokładna kalkulacja kosztu DeepSeek API
    default_pages = min(existing_cfg.get("pages", 3), available_pages)
    pages_to_scan = IntPrompt.ask(f"\nIle stron chcesz przeskanować w cyklu? (1 - {available_pages})", default=default_pages, console=console)
    pages_to_scan = max(1, min(pages_to_scan, available_pages))

    # Obliczenie na podstawie realnego zużycia tokenów
    estimated_items = min(pages_to_scan * ITEMS_PER_PAGE, total_items)
    cost = calculate_deepseek_cost(estimated_items)

    calc_table = Table.grid(padding=(0, 2))
    calc_table.add_column(style="dim white", justify="left")
    calc_table.add_column(style="bold white", justify="left")

    calc_table.add_row("Wybrane województwo:", f"[bold yellow]{region_display}[/bold yellow]")
    calc_table.add_row("Wszystkie oferty na OLX:", f"{total_items} przedmiotów ({available_pages} stron)")
    calc_table.add_row("Strony wybrane do skanu:", f"[bold cyan]{pages_to_scan}[/bold cyan] stron (~{estimated_items} ogłoszeń)")
    calc_table.add_row("Tryb skanera:", "[bold green]Monitoring ciągły (Watch)[/bold green]" if watch_mode else "Pojedynczy skan")
    calc_table.add_row("Wątki równoległe AI:", str(threads_count))
    calc_table.add_row("─" * 32, "─" * 38)
    calc_table.add_row(
        "Szacowany koszt DeepSeek (Standard):",
        f"[bold bright_green]${cost['standard_usd']:.3f} USD[/bold bright_green] [dim](~{cost['standard_pln']:.2f} PLN)[/dim] "
        f"[dim italic](Wariant A: Peak z Cache)[/dim italic]",
    )
    calc_table.add_row(
        "Zakres kosztów (Off-Peak ↔ Pesymistyczny):",
        f"[dim]${cost['offpeak_usd']:.3f} – ${cost['pessimistic_usd']:.3f} USD "
        f"(~{cost['offpeak_pln']:.2f} – {cost['pessimistic_pln']:.2f} PLN)[/dim]",
    )
    calc_table.add_row(
        "Średni koszt za 1 ogłoszenie:",
        f"[dim white]~${COST_PER_OFFER_STANDARD_USD:.6f} USD (~0.001 zł / ogłoszenie)[/dim white]",
    )

    if available_pages > pages_to_scan:
        all_cost = calculate_deepseek_cost(total_items)
        calc_table.add_row(
            "Koszt pełnego skanu (wszystkie strony):",
            f"[dim]~${all_cost['standard_usd']:.2f} USD (~{all_cost['standard_pln']:.2f} PLN) za całe {available_pages} stron[/dim]",
        )

    calc_table.add_row(
        "Optymalizacja antyspamowa:",
        "[dim green]Filtry heurystyczne (etui/pudełka) oraz anty-duplikat jeszcze bardziej obniżą ten koszt![/dim green]",
    )

    console.print(
        Panel(
            calc_table,
            title="📊 DOKŁADNA KALKULACJA KOSZTÓW API DEEPSEEK (600 tok./oferta)",
            border_style="green",
            box=ROUNDED,
        )
    )

    # 5. Potwierdzenie
    confirmed = Confirm.ask("\nCzy uruchomić skaner z powyższymi parametrami?", default=True, console=console)
    if not confirmed:
        console.print("[yellow]Anulowano uruchomienie skanera. Do widzenia![/yellow]")
        sys.exit(0)

    updated_config = dict(existing_cfg)
    updated_config.update({
        "region": selected_slug,
        "pages": pages_to_scan,
        "watch": watch_mode,
        "interval": interval_sec,
        "threads": threads_count,
    })
    save_config(updated_config)

    return updated_config