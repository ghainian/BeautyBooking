from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException, Request
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


def _redirect_to_home_section(request: Request, anchor: str) -> RedirectResponse:
    language = (request.query_params.get("culture")
                or request.query_params.get("ui-culture") or "da").lower()
    if language not in LANG_MAP:
        language = "da"
    return RedirectResponse(url=f"/home?culture={language}&ui-culture={language}{anchor}", status_code=307)


@app.get("/contact")
def contact_redirect(request: Request) -> RedirectResponse:
    return _redirect_to_home_section(request, "#contact")


@app.get("/gallery")
def gallery_redirect(request: Request) -> RedirectResponse:
    return _redirect_to_home_section(request, "#gallery")


@app.get("/services")
def services_redirect(request: Request) -> RedirectResponse:
    return _redirect_to_home_section(request, "#services")


@app.get("/price")
def price_redirect(request: Request) -> RedirectResponse:
    return _redirect_to_home_section(request, "#services")


@app.api_route("/contactform/contact-form-handler.php", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def removed_legacy_contact_form_handler() -> None:
    raise HTTPException(status_code=404, detail="Endpoint removed")


@app.api_route("/contact-form-handler.php", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def removed_root_contact_form_handler() -> None:
    raise HTTPException(status_code=404, detail="Endpoint removed")


@app.api_route("/contactform/thanks/contact-form-thank-you.html", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def removed_legacy_contact_form_thanks() -> None:
    raise HTTPException(status_code=404, detail="Endpoint removed")


DIST_DIR = (Path(__file__).resolve().parent.parent / "frontend-dist").resolve()

if DIST_DIR.exists():
    @app.get("/")
    def spa_root() -> FileResponse:
        return FileResponse(str(DIST_DIR / "index.html"))

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        requested = (DIST_DIR / full_path).resolve()

        # Serve real built/static files directly, otherwise fall back to SPA index.
        if requested.is_file() and requested.is_relative_to(DIST_DIR):
            return FileResponse(str(requested))

        index_path = DIST_DIR / "index.html"
        return FileResponse(str(index_path))
