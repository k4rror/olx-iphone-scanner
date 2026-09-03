from __future__ import annotations

from typing import Any
from rich.box import ROUNDED
from rich.console import ConsoleDimensions, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from olx_scanner.i18n.translations import get_language, t
from olx_scanner.ui.state import DashboardState


def render_dashboard(state: DashboardState, console_size: ConsoleDimensions) -> Layout:
    with state.lock:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="metrics", size=4),
            Layout(name="main_table", ratio=1),
            Layout(name="bottom", size=8),
        )

        smart_tag = t("tag_smart_active") if not state.early_stopping_active else t("tag_smart_boundary")
        lang_badge = f"🌐 {get_language().upper()}"
        header_text = Text.assemble(
            (f" {t('app_title')} ", "bold white on #1e3799"),
            (" │ ", "dim white on #1e3799"),
            (f"{t('tag_model')}: {state.model_name}", "bold yellow on #1e3799"),
            (" │ ", "dim white on #1e3799"),
            (f"{t('tag_proxy')}: {state.proxy_count}", "bold cyan on #1e3799"),
            (" │ ", "dim white on #1e3799"),
            (f"{t('tag_cycle')}: #{state.cycle_index}", "bold green on #1e3799"),
            (" │ ", "dim white on #1e3799"),
            (lang_badge, "bold white on #1e3799"),
            (" │ ", "dim white on #1e3799"),
            (smart_tag, "bold magenta on #1e3799"),
        )
        layout["header"].update(Panel(header_text, box=ROUNDED, style="white on #1e3799", border_style="bright_blue"))

        kpi_table = Table.grid(expand=True)
        for _ in range(5):
            kpi_table.add_column(justify="center", ratio=1)

        card_total = Panel(
            f"[bold white]{state.total_offers_db}[/bold white]\n[dim]{t('kpi_total')}[/dim]",
            box=ROUNDED,
            border_style="blue",
        )
        card_analyzed = Panel(
            f"[bold cyan]{state.analyzed_offers_db}[/bold cyan]\n[dim]{t('kpi_analyzed')}[/dim]",
            box=ROUNDED,
            border_style="cyan",
        )
        card_healthy = Panel(
            f"[bold green]{state.healthy_offers_db}[/bold green]\n[dim]{t('kpi_healthy')}[/dim]",
            box=ROUNDED,
            border_style="green",
        )
        card_damaged = Panel(
            f"[bold red]{state.damaged_offers_db}[/bold red]\n[dim]{t('kpi_damaged')}[/dim]",
            box=ROUNDED,
            border_style="red",
        )
        card_skipped = Panel(
            f"[bold magenta]{state.smart_skipped_duplicates}[/bold magenta]\n[dim]{t('kpi_skipped')}[/dim]",
            box=ROUNDED,
            border_style="magenta",
        )
        kpi_table.add_row(card_total, card_analyzed, card_healthy, card_damaged, card_skipped)
        layout["metrics"].update(kpi_table)

        table = Table(
            expand=True,
            box=ROUNDED,
            border_style="bright_blue",
            header_style="bold bright_cyan",
            show_lines=False,
        )
        table.add_column(t("col_model"), ratio=22, style="bold white")
        table.add_column(t("col_price"), justify="right", ratio=12, style="bold yellow")
        table.add_column(t("col_battery"), justify="center", ratio=10)
        table.add_column(t("col_condition"), ratio=26)
        table.add_column(t("col_verdict"), ratio=30)

        term_h = console_size.height if console_size else 30
        visible_rows_limit = max(4, term_h - 20)
        rows_to_show = state.table_rows[:visible_rows_limit]

        if not rows_to_show:
            table.add_row(
                f"[dim]{t('waiting_label')}[/dim]",
                "[dim]-[/dim]",
                "[dim]-[/dim]",
                "[dim]-[/dim]",
                "[dim]-[/dim]",
            )
        else:
            for r in rows_to_show:
                storage_s = f" {r['storage_gb']}GB" if r.get("storage_gb") else ""
                model_s = f"{r.get('model_name') or r.get('title', '')[:22]}{storage_s}"
                price_val = r.get("price")
                price_s = f"{price_val:.0f} zł" if price_val is not None else "[dim]Brak[/dim]"

                bat_val = r.get("battery_health_pct")
                if bat_val:
                    bat_color = "bright_green" if bat_val >= 85 else ("bright_yellow" if bat_val >= 78 else "bright_red")
                    bat_s = f"[{bat_color}]{bat_val}%[/{bat_color}]"
                else:
                    bat_s = "[dim]?[/dim]"

                is_dam = r.get("is_damaged")
                dam_badge = f"[bold red]{t('badge_damaged')}[/bold red] " if is_dam else f"[bold green]{t('badge_ok')}[/bold green] "
                cond_txt = r.get("condition_state") or r.get("condition") or ""
                stan_s = f"{dam_badge}[dim]{cond_txt[:20]}[/dim]"

                ai_summary = r.get("ai_summary") or r.get("ai_verdict") or "-"
                if len(ai_summary) > 48:
                    ai_summary = ai_summary[:45] + "..."

                table.add_row(model_s, price_s, bat_s, stan_s, ai_summary)

        layout["main_table"].update(
            Panel(table, title=f"[bold white]{t('table_title')}[/bold white]", box=ROUNDED, border_style="cyan")
        )

        layout["bottom"].split_row(
            Layout(name="status_col", ratio=45),
            Layout(name="events_col", ratio=55),
        )

        bar_len = 22
        fill_len = int(state.current_progress * bar_len)
        prog_bar = f"[{'━' * fill_len}{'─' * (bar_len - fill_len)}]"
        pct_lbl = f"{int(state.current_progress * 100)}%"

        cd_info = ""
        if state.next_scan_seconds > 0:
            cd_info = f"\n[dim yellow]{t('next_cycle_in', sec=state.next_scan_seconds)}[/dim yellow]"

        status_elements = [
            Text.from_markup(f"[bold cyan]{t('status_label')}:[/bold cyan] {state.current_status}"),
            Text.from_markup(f"[bold white]{state.progress_label}[/bold white]"),
            Text.from_markup(f"[bright_cyan]{prog_bar}[/bright_cyan] [bold white]{pct_lbl}[/bold white]{cd_info}"),
        ]
        layout["bottom"]["status_col"].update(
            Panel(Group(*status_elements), title=f"[bold white]{t('status_box_title')}[/bold white]", box=ROUNDED, border_style="magenta")
        )

        ev_renderables = []
        if not state.recent_events:
            ev_renderables.append(Text(t("waiting_label"), style="dim"))
        else:
            for ev in state.recent_events:
                lvl_c = {
                    "SUCCESS": "green",
                    "WARN": "yellow",
                    "ERROR": "red",
                    "AI": "magenta",
                    "PROXY": "blue",
                    "SMART": "bright_cyan",
                }.get(ev.level, "white")

                idx_s = f"[{ev.idx}] " if ev.idx else ""
                line = Text.assemble(
                    (f"{ev.timestamp} ", "dim white"),
                    (f"[{ev.level:<5}] ", f"bold {lvl_c}"),
                    (idx_s, "dim cyan"),
                    (ev.message, "white"),
                )
                ev_renderables.append(line)

        layout["bottom"]["events_col"].update(
            Panel(Group(*ev_renderables), title=f"[bold white]{t('events_box_title')}[/bold white]", box=ROUNDED, border_style="bright_black")
        )

        return layout