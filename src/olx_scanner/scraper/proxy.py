from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from olx_scanner.core.models import VerifiedProxy

TARGET_BASE_URL = "https://www.olx.pl"


def parse_proxy_line(raw_line: str) -> dict[str, Any] | None:
    line = raw_line.strip()
    if not line or line.startswith(("#", "//")):
        return None

    kind = "http"
    if "://" in line:
        kind_part, _, rest = line.partition("://")
        kind = kind_part.lower()
        line = rest

    auth = ""
    if "@" in line:
        auth_part, _, host_port = line.rpartition("@")
        auth = auth_part + "@"
        line = host_port

    line = line.split("/")[0].split("?")[0].strip()
    host, _, port_s = line.rpartition(":")
    if host and port_s.isdigit():
        port = int(port_s)
        clean_host = host.strip("[]")
        full_url = f"{kind}://{auth}{clean_host}:{port}" if auth else f"{kind}://{clean_host}:{port}"
        return {
            "url": full_url,
            "kind": kind,
            "addr": f"{clean_host}:{port}",
            "host": clean_host,
            "port": port,
            "initial_ms": 9999,
        }
    return None


def load_candidate_proxies(
    custom_file: str | Path | None = None,
    logger: Callable[[str, str, str | None], None] | None = None,
) -> list[dict[str, Any]]:
    log = logger or (lambda msg, lvl="PROXY", idx=None: None)
    candidates_dict: dict[tuple[str, str], dict[str, Any]] = {}

    if custom_file:
        c_path = Path(custom_file)
        if not c_path.is_file():
            log(f"Podany plik proxy '{custom_file}' nie istnieje!", "ERROR")
            return []

        try:
            cnt = 0
            if c_path.suffix.lower() == ".json":
                data = json.loads(c_path.read_text(encoding="utf-8"))
                items = data.get("proxies", data) if isinstance(data, dict) else data
                for item in items:
                    if isinstance(item, dict):
                        h, p = item.get("host"), item.get("port")
                        k = item.get("kind", "http").lower()
                        if h and p:
                            key = (k, f"{h}:{p}")
                            candidates_dict[key] = {
                                "url": f"{k}://{h}:{p}",
                                "kind": k,
                                "addr": f"{h}:{p}",
                                "host": str(h).strip("[]"),
                                "port": int(p),
                                "initial_ms": item.get("latency_ms") or 9999,
                            }
                            cnt += 1
            else:
                for line in c_path.read_text(encoding="utf-8").splitlines():
                    parsed = parse_proxy_line(line)
                    if parsed:
                        key = (parsed["kind"], parsed["addr"])
                        if key not in candidates_dict:
                            candidates_dict[key] = parsed
                            cnt += 1
            log(f"Załadowano {cnt} proxy z pliku użytkownika: {c_path.resolve()}", "SUCCESS")
            return list(candidates_dict.values())
        except Exception as e:
            log(f"Błąd odczytu pliku {custom_file}: {e}", "ERROR")
            return []

    search_dirs = [Path("."), Path("..")]
    ranked_re = re.compile(
        r"^\s*\d+\s+(?P<ms>\d+|-)\s+(?P<kind>http|socks5|socks4)\s+(?P<exit_ip>\S+)\s+(?P<addr>\S+)\s*$",
        re.IGNORECASE,
    )

    for s_dir in search_dirs:
        json_path = s_dir / "proxies_live.json"
        if json_path.is_file():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                for item in data.get("proxies", []):
                    kind = item.get("kind", "http").lower()
                    host, port = item.get("host"), item.get("port")
                    if host and port:
                        addr = f"{host}:{port}"
                        key = (kind, addr)
                        if key not in candidates_dict:
                            candidates_dict[key] = {
                                "url": f"{kind}://{addr}",
                                "kind": kind,
                                "addr": addr,
                                "host": host,
                                "port": int(port),
                                "initial_ms": item.get("latency_ms") or 9999,
                            }
            except Exception:
                pass

        ranked_path = s_dir / "proxies_ranked.txt"
        if ranked_path.is_file():
            try:
                for line in ranked_path.read_text(encoding="utf-8").splitlines():
                    m = ranked_re.match(line.strip())
                    if m:
                        kind = m.group("kind").lower()
                        addr = m.group("addr")
                        host, _, port_s = addr.rpartition(":")
                        if host and port_s.isdigit():
                            key = (kind, addr)
                            if key not in candidates_dict:
                                candidates_dict[key] = {
                                    "url": f"{kind}://{addr}",
                                    "kind": kind,
                                    "addr": addr,
                                    "host": host.strip("[]"),
                                    "port": int(port_s),
                                    "initial_ms": int(m.group("ms")) if m.group("ms").isdigit() else 9999,
                                }
            except Exception:
                pass

    candidates = list(candidates_dict.values())
    kind_priority = {"socks5": 0, "socks4": 1, "http": 2}
    candidates.sort(key=lambda x: (kind_priority.get(x["kind"], 3), x["initial_ms"]))
    return candidates


async def _async_check_proxy_olx_tunnel(
    item: dict[str, Any],
    sem: asyncio.Semaphore,
    timeout: float = 2.5,
) -> VerifiedProxy | None:
    host = item["host"]
    port = item["port"]
    kind = item["kind"].lower()
    t0 = time.perf_counter()

    async with sem:
        try:
            coro = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(coro, timeout=timeout)

            if kind == "socks5":
                writer.write(bytes([5, 1, 0]))
                await writer.drain()
                greet = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
                if greet != bytes([5, 0]):
                    writer.close()
                    return None
                host_b = b"www.olx.pl"
                req = bytes([5, 1, 0, 3]) + bytes([len(host_b)]) + host_b + (443).to_bytes(2, "big")
                writer.write(req)
                await writer.drain()
                hdr = await asyncio.wait_for(reader.readexactly(4), timeout=timeout)
                writer.close()
                if hdr[0] != 5 or hdr[1] != 0:
                    return None
            elif kind == "socks4":
                host_b = b"www.olx.pl"
                req = bytes([4, 1]) + (443).to_bytes(2, "big") + bytes([0, 0, 0, 1, 0]) + host_b + bytes([0])
                writer.write(req)
                await writer.drain()
                resp = await asyncio.wait_for(reader.readexactly(8), timeout=timeout)
                writer.close()
                if resp[0] != 0 or resp[1] != 0x5A:
                    return None
            else:
                req = (
                    b"CONNECT www.olx.pl:443 HTTP/1.1\r\n"
                    b"Host: www.olx.pl:443\r\n"
                    b"Proxy-Connection: close\r\n\r\n"
                )
                writer.write(req)
                await writer.drain()
                data = await asyncio.wait_for(reader.read(1024), timeout=timeout)
                writer.close()
                if not data:
                    return None
                status_line = data.split(b"\r\n", 1)[0]
                if not (b"200" in status_line or b"220" in status_line):
                    return None

            latency_ms = int((time.perf_counter() - t0) * 1000)
            return VerifiedProxy(
                url=item["url"],
                kind=kind.upper(),
                addr=item["addr"],
                latency_ms=latency_ms,
            )
        except Exception:
            return None


def detect_local_rotator(logger: Callable[[str, str, str | None], None] | None = None) -> str | None:
    from olx_scanner.scraper.client import create_tls_session

    log = logger or (lambda msg, lvl="PROXY", idx=None: None)
    env_proxy = os.getenv("HTTP_PROXY") or os.getenv("ALL_PROXY")
    ports_to_check = [8080, 8888, 8118, 9080, 18080]

    if env_proxy:
        m = re.search(r":(\d{2,5})", env_proxy)
        if m:
            p = int(m.group(1))
            if p not in ports_to_check:
                ports_to_check.insert(0, p)

    log("Sprawdzanie dostępności lokalnego rotatora ProxyScanner (porty: 8080, 8888, 8118, 9080, 18080)...", "PROXY")

    for port in ports_to_check:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.2)
            res = s.connect_ex(("127.0.0.1", port))
            s.close()
            if res == 0:
                local_url = f"http://127.0.0.1:{port}"
                log(f"Wykryto nasłuch na {local_url}. Weryfikacja połączenia z OLX...", "PROXY")
                t0 = time.perf_counter()
                try:
                    sess = create_tls_session(local_url)
                    resp = sess.get(TARGET_BASE_URL, timeout_seconds=3, allow_redirects=True)
                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    if resp.status_code == 200:
                        log(f"Połączono z lokalnym rotatorem {local_url} ({elapsed_ms}ms, HTTP 200)!", "SUCCESS")
                        return local_url
                except Exception as e:
                    log(f"Lokalny port {port} nie przekazał poprawnie ruchu HTTPS: {e}", "WARN")
        except Exception:
            pass

    log("Brak aktywnego lokalnego rotatora na 127.0.0.1.", "PROXY")
    return None


def display_no_proxy_referral(console: Console) -> None:
    banner = (
        "[bold yellow]⚠ Nie podano własnych proxy ani nie wykryto aktywnego rotatora w tle![/bold yellow]\n\n"
        "[bold white]Nie posiadasz własnych proxy?[/bold white]\n"
        "Skorzystaj z wbudowanego narzędzia [bold cyan]ProxyScanner[/bold cyan], aby automatycznie pobrać,\n"
        "przetestować i rotować setki darmowych, zweryfikowanych serwerów proxy:\n\n"
        "  [bold green]1.[/bold green] Otwórz osobne okno terminala w katalogu: [bold cyan]cd ..[/bold cyan]\n"
        "  [bold green]2.[/bold green] Uruchom silnik rotatora: [bold cyan]python main.py[/bold cyan]\n"
        "  [bold green]3.[/bold green] ProxyScanner wystawi lokalny port [bold green]http://127.0.0.1:8080[/bold green],\n"
        "     który ten skaner wykryje natychmiastowo!\n\n"
        "[dim]Własną listę możesz podać poleceniem:[/dim] [bold cyan]olx-scanner --proxy-file proxy.txt[/bold cyan]\n\n"
        "[bold magenta]➔ Kontynuuję w trybie bezpośrednim (Direct TLS)...[/bold magenta]"
    )
    console.print(Panel(banner, title="💡 Wskazówka: Użyj ProxyScanner", border_style="cyan"))


def select_best_olx_proxies(
    custom_file: str | Path | None = None,
    min_working: int = 15,
    max_workers: int = 150,
    timeout: float = 2.5,
    console: Console | None = None,
    logger: Callable[[str, str, str | None], None] | None = None,
) -> list[VerifiedProxy]:
    console = console or Console()
    log = logger or (lambda msg, lvl="PROXY", idx=None: None)

    if not custom_file:
        local_rotator = detect_local_rotator(logger=log)
        if local_rotator:
            console.print(
                Panel(
                    f"[bold green]⚡ Wykryto serwer ProxyScanner ([white]{local_rotator}[/white])![/bold green]\n"
                    f"[cyan]Wszystkie zapytania będą rotowane przez pulę proxy.[/cyan]",
                    title="🚀 Połączenie z rotatorem",
                    border_style="green",
                )
            )
            return [VerifiedProxy(url=local_rotator, kind="ROTATOR", addr=local_rotator.removeprefix("http://"), latency_ms=15)]

    candidates = load_candidate_proxies(custom_file=custom_file, logger=log)
    if not candidates:
        if not custom_file:
            display_no_proxy_referral(console)
        return []

    log(f"Rozpoczynanie testu tuneli HTTPS dla {len(candidates)} proxy ({max_workers} workerów)...", "PROXY")

    verified: list[VerifiedProxy] = []
    done_count = ok_count = fail_count = 0
    start_time = time.perf_counter()

    async def run_async_scan() -> list[VerifiedProxy]:
        nonlocal done_count, ok_count, fail_count
        sem = asyncio.Semaphore(max_workers)
        results: list[VerifiedProxy] = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=25, complete_style="green", finished_style="bold green"),
            TaskProgressColumn(),
            TextColumn("[bold green]✓ {task.fields[ok]}[/bold green]"),
            TextColumn("[bold red]✗ {task.fields[fail]}[/bold red]"),
            TextColumn("[cyan]{task.fields[speed]:.1f} req/s[/cyan]"),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Weryfikacja tuneli HTTPS do OLX", total=len(candidates), ok=0, fail=0, speed=0.0)

            async def scan_item(item: dict[str, Any]) -> None:
                nonlocal done_count, ok_count, fail_count
                res = await _async_check_proxy_olx_tunnel(item, sem, timeout=timeout)
                done_count += 1
                if res:
                    results.append(res)
                    ok_count += 1
                else:
                    fail_count += 1

                elapsed = time.perf_counter() - start_time
                speed = done_count / elapsed if elapsed > 0 else 0.0
                progress.update(
                    task_id,
                    completed=done_count,
                    ok=ok_count,
                    fail=fail_count,
                    speed=speed,
                )

            tasks = [asyncio.create_task(scan_item(c)) for c in candidates]
            await asyncio.gather(*tasks, return_exceptions=True)

        return results

    try:
        verified = asyncio.run(run_async_scan())
    except Exception as e:
        log(f"Błąd asynchronicznego skanu: {e}", "ERROR")

    verified.sort(key=lambda x: x.latency_ms)

    if not verified:
        console.print("[bold yellow]⚠ Żadne proxy nie utworzyło tunelu HTTPS do OLX![/bold yellow]")
        if not custom_file:
            display_no_proxy_referral(console)
        return []

    pool_size = max(min_working, min(len(verified), 50))
    top_verified = verified[:pool_size]

    table = Table(
        title=f"⚡ WYBRANO {len(top_verified)} NAJSZYBSZYCH TUNELI HTTPS NA OLX",
        border_style="green",
        expand=False,
    )
    table.add_column("Rank", justify="center", style="bold cyan")
    table.add_column("Typ", justify="center")
    table.add_column("Ping (HTTPS)", justify="right", style="bold green")
    table.add_column("Adres Proxy", style="white")

    for i, p in enumerate(top_verified[:10], start=1):
        ping_color = "bold green" if p.latency_ms < 400 else ("yellow" if p.latency_ms < 900 else "red")
        table.add_row(str(i), p.kind, f"[{ping_color}]{p.latency_ms} ms[/{ping_color}]", p.addr)

    console.print(table)
    return top_verified
