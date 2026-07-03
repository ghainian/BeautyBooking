from fastapi.testclient import TestClient

from app.localization import LANG_MAP, get_text
from app.main import app


client = TestClient(app)


REQUIRED_KEYS = [
    "NavHome",
    "NavAbout",
    "NavServices",
    "NavGallery",
    "NavHours",
    "NavContact",
    "ServicesTitle",
    "GalleryTitle",
    "HoursTitle",
    "ContactEyebrow",
    "BookingTitle",
]


def test_all_supported_languages_have_required_keys():
    for language, translations in LANG_MAP.items():
        for key in REQUIRED_KEYS:
            assert key in translations, f"Missing key {key} in language {language}"
            assert translations[key].strip(
            ), f"Empty value for key {key} in language {language}"


def test_unknown_language_falls_back_to_danish():
    for key in REQUIRED_KEYS:
        assert get_text("xx", key) == get_text("da", key)


def test_translation_api_returns_each_language_with_required_keys():
    for language in LANG_MAP:
        response = client.get(f"/api/translations/{language}")
        assert response.status_code == 200

        payload = response.json()
        for key in REQUIRED_KEYS:
            assert key in payload
            assert str(payload[key]).strip()


def test_section_redirects_keep_selected_language_for_all_languages():
    routes = {
        "/services": "#services",
        "/gallery": "#gallery",
        "/contact": "#contact",
        "/price": "#services",
    }

    for language in LANG_MAP:
        for route, anchor in routes.items():
            response = client.get(
                route,
                params={"culture": language, "ui-culture": language},
                follow_redirects=False,
            )
            assert response.status_code == 307
            assert response.headers["location"] == f"/home?culture={language}&ui-culture={language}{anchor}"


def test_section_redirect_unknown_language_defaults_to_danish():
    response = client.get(
        "/services",
        params={"culture": "xx", "ui-culture": "xx"},
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert response.headers["location"] == "/home?culture=da&ui-culture=da#services"


def test_root_path_serves_frontend_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "<!doctype html>" in response.text.lower()
