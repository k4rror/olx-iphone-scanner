from __future__ import annotations

import argparse
import csv
import io
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from olx_scanner.core.config import load_config, save_config
from olx_scanner.core.regions import (
    VOIVODESHIPS,
    get_region_display_name,
    normalize_region,
)
from olx_scanner.i18n import (
    DEFAULT_LANG,
    LANGUAGES,
    TRANSLATIONS,
    get_language,
    set_language,
    tl,
)
from olx_scanner.scraper.client import TLSScraper
from olx_scanner.storage.database import Database
from olx_scanner.web.scanner_service import scanner_service

app = FastAPI(
    title="OLX iPhone Database Dashboard",
    description="Dedicated Local Data Management, Live Scanner Controller & Analytics Suite",
    version="1.0.0",
)

DB_PATH = Path("olx_iphones.db")
WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Pamięć podręczna metadanych OLX (zapobiega spamowaniu olx.pl)
PROBE_CACHE: dict[str | None, tuple[float, int, int]] = {}
PROBE_CACHE_TTL_SECONDS = 300.0


def get_db() -> Database:
    return Database(db_path=DB_PATH)


def resolve_request_language(request: Request) -> str:
    """Określa język na podstawie parametru URL, ciasteczka, pliku konfiguracyjnego lub nagłówka."""
    param_lang = request.query_params.get("lang")
    if param_lang and param_lang in LANGUAGES:
        return param_lang

    cookie_lang = request.cookies.get("scanner_lang")
    if cookie_lang and cookie_lang in LANGUAGES:
        return cookie_lang

    cfg = load_config() or {}
    cfg_lang = cfg.get("language")
    if cfg_lang and cfg_lang in LANGUAGES:
        return cfg_lang

    accept = request.headers.get("accept-language", "").lower()
    for code in LANGUAGES:
        if code in accept:
            return code

    return DEFAULT_LANG


def build_template_context(request: Request, active_page: str) -> dict[str, Any]:
    lang = resolve_request_language(request)
    lang_dict = TRANSLATIONS.get(lang, TRANSLATIONS.get(DEFAULT_LANG, {}))
    return {
        "request": request,
        "active_page": active_page,
        "current_lang": lang,
        "languages": LANGUAGES,
        "translations_json": json.dumps(lang_dict, ensure_ascii=False),
        "t": lambda key, **kwargs: tl(lang, key, **kwargs),
    }


class NotesUpdateRequest(BaseModel):
    notes: str


class ScannerStartRequest(BaseModel):
    region: str | None = None
    ai_language: str | None = None
    pages: int = 3
    watch: bool = False
    interval: int = 120
    threads: int = 8


class ScannerConfigRequest(BaseModel):
    region: str | None = None
    ai_language: str | None = None
    pages: int = 3
    watch: bool = False
    interval: int = 120
    threads: int = 8
    api_key: str | None = None
    model: str = "deepseek-v4-flash-vision-exp"
    custom_proxy: str | None = None
    language: str | None = None


@app.get("/api/scanner/config")
async def get_scanner_config() -> dict[str, Any]:
    cfg = load_config() or {}
    key = cfg.get("api_key", "")
    masked_key = f"{key[:5]}...{key[-4:]}" if len(key) > 8 else (tl(get_language(), "api_key_configured") if key else "")
    return {
        "region": cfg.get("region"),
        "ai_language": cfg.get("ai_language", cfg.get("language", "pl")),
        "pages": cfg.get("pages", 3),
        "watch": cfg.get("watch", False),
        "interval": cfg.get("interval", 120),
        "threads": cfg.get("threads", 8),
        "api_key_masked": masked_key,
        "model": cfg.get("model", "deepseek-v4-flash-vision-exp"),
        "custom_proxy": cfg.get("custom_proxy", ""),
        "language": cfg.get("language", get_language()),
    }


class LanguageChangeRequest(BaseModel):
    language: str


# =============================================================================
# WIDOKI HTML DASHBOARDU
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def root_redirect() -> Response:
    return RedirectResponse(url="/scanner", status_code=status.HTTP_302_FOUND)


@app.get("/scanner", response_class=HTMLResponse)
async def serve_scanner_page(request: Request) -> Response:
    ctx = build_template_context(request, active_page="scanner")
    response = templates.TemplateResponse(request=request, name="pages/scanner.html", context=ctx)
    if request.query_params.get("lang"):
        response.set_cookie("scanner_lang", ctx["current_lang"], max_age=31536000, samesite="lax")
    return response


@app.get("/offers", response_class=HTMLResponse)
async def serve_offers_page(request: Request) -> Response:
    ctx = build_template_context(request, active_page="offers")
    response = templates.TemplateResponse(request=request, name="pages/offers.html", context=ctx)
    if request.query_params.get("lang"):
        response.set_cookie("scanner_lang", ctx["current_lang"], max_age=31536000, samesite="lax")
    return response


@app.get("/analytics", response_class=HTMLResponse)
async def serve_analytics_page(request: Request) -> Response:
    ctx = build_template_context(request, active_page="analytics")
    response = templates.TemplateResponse(request=request, name="pages/analytics.html", context=ctx)
    if request.query_params.get("lang"):
        response.set_cookie("scanner_lang", ctx["current_lang"], max_age=31536000, samesite="lax")
    return response


# =============================================================================
# ENDPOINTY JĘZYKOWE (i18n)
# =============================================================================

@app.post("/api/language")
async def set_app_language(payload: LanguageChangeRequest, response: Response) -> dict[str, Any]:
    if payload.language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="Nieobsługiwany kod języka.")
    set_language(payload.language)
    cfg = load_config() or {}
    cfg["language"] = payload.language
    save_config(cfg)
    response.set_cookie("scanner_lang", payload.language, max_age=31536000, samesite="lax")
    return {"status": "success", "language": payload.language}


@app.get("/api/translations")
async def get_translations_api(request: Request, lang: str | None = None) -> dict[str, Any]:
    target_lang = lang if (lang and lang in LANGUAGES) else resolve_request_language(request)
    return {
        "language": target_lang,
        "languages": LANGUAGES,
        "translations": TRANSLATIONS.get(target_lang, TRANSLATIONS.get(DEFAULT_LANG, {})),
    }


# =============================================================================
# ENDPOINTY STEROWANIA I MONITORINGU SKANERA
# =============================================================================

# Funkcja „Monitoring" (tryb watch) jest tymczasowo wyłączona w web dashboardzie.
# Skaner w trybie pojedynczym działa normalnie. Aby przywrócić watch:
# ustaw True (i zsynchronizuj WATCH_MODE_ENABLED w scanner.js).
WATCH_MODE_ENABLED = False


@app.get("/api/scanner/status")
async def get_scanner_status() -> dict[str, Any]:
    return scanner_service.get_snapshot()


@app.post("/api/scanner/start")
async def start_scanner(payload: ScannerStartRequest | None = None) -> dict[str, Any]:
    override = payload.model_dump() if payload else {}
    if not WATCH_MODE_ENABLED:
        if override.get("watch"):
            raise HTTPException(status_code=403, detail=tl(get_language(), "api_watch_disabled"))
        # Wymuszenie trybu pojedynczego także wtedy, gdy zapisana konfiguracja ma watch=true
        override["watch"] = False
    success = scanner_service.start(config_override=override)
    if not success:
        lang = get_language()
        raise HTTPException(status_code=400, detail=tl(lang, "api_already_running"))
    return {"status": "success", "message": tl(get_language(), "api_started")}


@app.post("/api/scanner/stop")
async def stop_scanner() -> dict[str, Any]:
    success = scanner_service.stop()
    if not success:
        lang = get_language()
        raise HTTPException(status_code=400, detail=tl(lang, "api_not_running"))
    return {"status": "success", "message": tl(get_language(), "api_stopping")}


@app.post("/api/scanner/config")
async def save_scanner_config(payload: ScannerConfigRequest) -> dict[str, Any]:
    existing = load_config() or {}
    data = payload.model_dump(exclude_unset=True)

    if not data.get("api_key"):
        data["api_key"] = existing.get("api_key", "")

    if data.get("language"):
        set_language(data["language"])

    existing.update(data)
    save_config(existing)
    return {"status": "success", "message": tl(get_language(), "api_config_saved")}


@app.get("/api/scanner/probe")
async def probe_olx_region(region: str | None = None) -> dict[str, Any]:
    norm_region = normalize_region(region)
    display_name = get_region_display_name(norm_region)
    now = time.time()

    if norm_region in PROBE_CACHE:
        cached_time, total_items, available_pages = PROBE_CACHE[norm_region]
        if now - cached_time < PROBE_CACHE_TTL_SECONDS:
            return {
                "region_slug": norm_region,
                "region_display": display_name,
                "total_items": total_items,
                "available_pages": available_pages,
                "cached": True,
            }

    scraper = TLSScraper(region=norm_region)
    total_items, available_pages = scraper.probe_search_meta(region=norm_region)

    PROBE_CACHE[norm_region] = (now, total_items, available_pages)

    return {
        "region_slug": norm_region,
        "region_display": display_name,
        "total_items": total_items,
        "available_pages": available_pages,
        "cached": False,
    }


# =============================================================================
# ENDPOINTY BAZY DANYCH I ANALITYKI
# =============================================================================

@app.get("/api/stats")
async def get_stats() -> dict[str, Any]:
    db = get_db()
    basic_stats = db.get_stats()
    analytics = db.get_analytics_summary()
    return {
        "status": "success",
        "kpi": basic_stats,
        "analytics": analytics,
    }


@app.get("/api/models")
async def get_models() -> list[str]:
    db = get_db()
    return db.get_distinct_models()


@app.get("/api/regions")
async def get_regions_list() -> dict[str, str]:
    return VOIVODESHIPS


@app.get("/api/offers")
async def list_offers(
    q: str | None = None,
    model: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_battery: int | None = None,
    max_battery: int | None = None,
    storage: int | None = None,
    is_damaged: bool | None = None,
    face_id_working: bool | None = None,
    icloud_clean: bool | None = None,
    is_favorite: bool | None = None,
    only_analyzed: bool = False,
    min_margin: float | None = None,
    only_deals: bool = False,
    sort_by: str = "newest",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=200),
) -> dict[str, Any]:
    db = get_db()
    result = db.query_offers(
        q=q,
        model=model,
        min_price=min_price,
        max_price=max_price,
        min_battery=min_battery,
        max_battery=max_battery,
        storage=storage,
        is_damaged=is_damaged,
        face_id_working=face_id_working,
        icloud_clean=icloud_clean,
        is_favorite=is_favorite,
        only_analyzed=only_analyzed,
        min_margin=min_margin,
        only_deals=only_deals,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )
    return result

@app.get("/api/models/stats")
async def get_model_stats_endpoint(model: str | None = None) -> dict[str, Any]:
    db = get_db()
    stats = db.get_model_stats(model_name=model)
    if model and not stats:
        return {
            "model_name": model,
            "total_count": 0,
            "avg_price": None,
            "min_price": None,
            "max_price": None,
            "avg_battery": None,
            "damaged_count": 0,
            "healthy_count": 0,
        }
    return stats or {}

@app.get("/api/offers/{olx_id}")
async def get_offer_details(olx_id: str) -> dict[str, Any]:
    db = get_db()
    offer = db.get_offer_by_id(olx_id)
    if not offer:
        raise HTTPException(status_code=404, detail=tl(get_language(), "api_offer_not_found"))
    return offer


@app.post("/api/offers/{olx_id}/favorite")
async def toggle_favorite(olx_id: str) -> dict[str, Any]:
    db = get_db()
    if not db.offer_exists(olx_id):
        raise HTTPException(status_code=404, detail=tl(get_language(), "api_offer_missing"))
    is_fav = db.toggle_favorite(olx_id)
    return {"status": "success", "olx_id": olx_id, "is_favorite": is_fav}


@app.patch("/api/offers/{olx_id}/notes")
async def update_notes(olx_id: str, payload: NotesUpdateRequest) -> dict[str, Any]:
    db = get_db()
    if not db.offer_exists(olx_id):
        raise HTTPException(status_code=404, detail=tl(get_language(), "api_offer_missing"))
    db.update_notes(olx_id, payload.notes)
    return {"status": "success", "olx_id": olx_id, "user_notes": payload.notes}


@app.delete("/api/offers/{olx_id}")
async def delete_offer(olx_id: str) -> Response:
    db = get_db()
    if not db.offer_exists(olx_id):
        raise HTTPException(status_code=404, detail=tl(get_language(), "api_offer_missing"))
    success = db.delete_offer(olx_id)
    if not success:
        raise HTTPException(status_code=500, detail=tl(get_language(), "api_delete_failed"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/export")
async def export_csv(
    q: str | None = None,
    model: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_battery: int | None = None,
    is_damaged: bool | None = None,
    is_favorite: bool | None = None,
    min_margin: float | None = None,
    only_deals: bool = False,
    sort_by: str = "newest",
) -> StreamingResponse:
    db = get_db()
    data = db.query_offers(
        q=q,
        model=model,
        min_price=min_price,
        max_price=max_price,
        min_battery=min_battery,
        is_damaged=is_damaged,
        is_favorite=is_favorite,
        min_margin=min_margin,
        only_deals=only_deals,
        sort_by=sort_by,
        page=1,
        page_size=5000,
    )
    items = data["items"]

    buffer = io.StringIO()
    buffer.write("\ufeff")

    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "OLX ID", "Model", "Pamięć (GB)", "Cena (PLN)", "Średnia Rynkowa (PLN)",
        "Szacowana Marża (PLN)", "Marża (%)", "Bateria (%)",
        "Stan", "Uszkodzony", "Face ID", "iCloud Czysty", "Ulubione",
        "Werdykt AI", "Notatki Użytkownika", "Lokalizacja", "Data dodania", "Link OLX"
    ])

    for r in items:
        writer.writerow([
            r.get("olx_id"),
            r.get("model_name") or r.get("title"),
            r.get("storage_gb") or "",
            r.get("price") if r.get("price") is not None else "",
            r.get("avg_model_price") if r.get("avg_model_price") is not None else "",
            r.get("margin_pln") if r.get("margin_pln") is not None else "",
            f"{r.get('margin_pct')}%" if r.get("margin_pct") is not None else "",
            r.get("battery_health_pct") or "",
            r.get("condition_state") or "",
            "TAK" if r.get("is_damaged") else "NIE",
            "TAK" if r.get("face_id_working") == 1 else ("NIE" if r.get("face_id_working") == 0 else ""),
            "TAK" if r.get("icloud_clean") == 1 else ("NIE" if r.get("icloud_clean") == 0 else ""),
            "TAK" if r.get("is_favorite") else "NIE",
            r.get("ai_summary") or "",
            r.get("user_notes") or "",
            r.get("location") or "",
            r.get("posted_at") or "",
            r.get("url") or "",
        ])

    buffer.seek(0)
    filename = f"olx_iphones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# =============================================================================
# PUNKT STARTOWY DLA CLI (olx-dashboard)
# =============================================================================

def run_server() -> None:
    parser = argparse.ArgumentParser(description="OLX iPhone Database Dashboard & Live Scanner")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    parser.add_argument("--db", default="olx_iphones.db", help="Path to SQLite database file")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    global DB_PATH
    DB_PATH = Path(args.db)
    scanner_service.db_path = str(DB_PATH)

    cfg = load_config() or {}
    if cfg.get("language"):
        set_language(cfg["language"])

    print(f"\n🚀 OLX iPhone Hub running on http://{args.host}:{args.port}")

    if not args.no_browser:
        import webbrowser
        try:
            webbrowser.open(f"http://{args.host}:{args.port}")
        except Exception:
            pass

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


main = run_server

__all__ = ["app", "run_server", "main"]

if __name__ == "__main__":
    run_server()