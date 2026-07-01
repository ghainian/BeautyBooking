from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from .localization import LANG_MAP, get_text

app = FastAPI(title="BeautyBooking Python Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/translations/{language}")
def get_translations(language: str) -> Dict[str, str]:
    return LANG_MAP.get(language.lower(), LANG_MAP["da"])


@app.get("/api/translations/{language}/{key}")
def get_translation(language: str, key: str) -> Dict[str, str]:
    return {"key": key, "language": language, "value": get_text(language, key)}


@app.get("/contact")
def contact_redirect() -> RedirectResponse:
    return RedirectResponse(url="/home#hours-contact", status_code=307)


@app.get("/gallery")
def gallery_redirect() -> RedirectResponse:
    return RedirectResponse(url="/home#gallery", status_code=307)


@app.get("/services")
def services_redirect() -> RedirectResponse:
    return RedirectResponse(url="/home#services", status_code=307)


@app.get("/price")
def price_redirect() -> RedirectResponse:
    return RedirectResponse(url="/home#services", status_code=307)


DIST_DIR = (Path(__file__).resolve().parent.parent / "frontend-dist").resolve()

if DIST_DIR.exists():
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        requested = (DIST_DIR / full_path).resolve()

        # Serve real built/static files directly, otherwise fall back to SPA index.
        if requested.is_file() and requested.is_relative_to(DIST_DIR):
            return FileResponse(str(requested))

        index_path = DIST_DIR / "index.html"
        return FileResponse(str(index_path))
