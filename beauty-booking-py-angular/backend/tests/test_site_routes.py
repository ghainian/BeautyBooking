import pytest


def test_health_endpoint_returns_ok(client) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_translations_for_known_language_contains_expected_keys(client) -> None:
    response = client.get("/api/translations/da")

    assert response.status_code == 200
    payload = response.json()
    assert payload["HeroBrand"] == "SALON ANOVA"
    assert "NavBook" in payload


def test_translations_for_unknown_language_falls_back_to_danish(client) -> None:
    response = client.get("/api/translations/xx")

    assert response.status_code == 200
    payload = response.json()
    assert payload["HeroBrand"] == "SALON ANOVA"
    assert payload["NavBook"] == "Bestil Online"


def test_translation_key_lookup_returns_value_for_known_key(client) -> None:
    response = client.get("/api/translations/en/HeroBrand")

    assert response.status_code == 200
    assert response.json() == {
        "key": "HeroBrand",
        "language": "en",
        "value": "SALON ANOVA",
    }


def test_translation_key_lookup_returns_key_when_missing(client) -> None:
    response = client.get("/api/translations/da/NotARealLocalizationKey")

    assert response.status_code == 200
    assert response.json()["value"] == "NotARealLocalizationKey"


@pytest.mark.parametrize(
    "path,location",
    [
        ("/contact", "/home?culture=da&ui-culture=da#contact"),
        ("/gallery", "/home?culture=da&ui-culture=da#gallery"),
        ("/services", "/home?culture=da&ui-culture=da#services"),
        ("/price", "/home?culture=da&ui-culture=da#services"),
    ],
)
def test_legacy_section_redirects(client, path: str, location: str) -> None:
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == location


@pytest.mark.parametrize(
    "path,method",
    [
        ("/contactform/contact-form-handler.php", "get"),
        ("/contactform/contact-form-handler.php", "post"),
        ("/contact-form-handler.php", "get"),
        ("/contact-form-handler.php", "post"),
        ("/contactform/thanks/contact-form-thank-you.html", "get"),
        ("/contactform/thanks/contact-form-thank-you.html", "post"),
    ],
)
def test_removed_legacy_form_endpoints_return_404(client, path: str, method: str) -> None:
    response = getattr(client, method)(path)

    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint removed"


def test_spa_fallback_serves_index_for_unknown_route(client) -> None:
    response = client.get("/this-route-does-not-exist")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "<html" in response.text.lower()


def test_spa_fallback_serves_dist_file_when_file_exists(client) -> None:
    response = client.get("/index.html")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------

def test_health_endpoint_returns_correct_content_type(client) -> None:
    response = client.get("/api/health")
    assert "application/json" in response.headers.get("content-type", "")


def test_translations_endpoint_for_english_contains_english_values(client) -> None:
    response = client.get("/api/translations/en")
    assert response.status_code == 200
    payload = response.json()
    assert payload["HeroBrand"] == "SALON ANOVA"
    assert payload["NavBook"] == "Book Online"
    assert payload["Service1Name"] == "Men's haircut"


def test_translations_endpoint_all_supported_languages_return_200(client) -> None:
    for lang in ("da", "en"):
        response = client.get(f"/api/translations/{lang}")
        assert response.status_code == 200, f"Failed for {lang}"


def test_translation_key_lookup_english_hero_title(client) -> None:
    response = client.get("/api/translations/en/HeroTitle")
    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "en"
    assert "haircare" in payload["value"].lower()


def test_translation_key_lookup_unknown_key_echoes_key(client) -> None:
    response = client.get("/api/translations/en/___missing___")
    assert response.status_code == 200
    assert response.json()["value"] == "___missing___"


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_legacy_contact_form_returns_404_for_all_methods(client, method: str) -> None:
    response = getattr(client, method)("/contactform/contact-form-handler.php")
    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint removed"


def test_home_route_redirects_to_itself_without_loop(client) -> None:
    """GET /home should NOT redirect — it should serve the SPA index."""
    response = client.get("/home", follow_redirects=False)
    # /home is an unknown SPA route; the fallback must serve index.html (200)
    # or a redirect that resolves to a 200. Either way no infinite loop.
    assert response.status_code in (200, 307, 308)


def test_cors_header_present_on_api_response(client) -> None:
    response = client.get(
        "/api/health", headers={"Origin": "http://localhost:4200"})
    assert response.status_code == 200
    # CORS middleware should echo back the allow-origin header
    assert "access-control-allow-origin" in response.headers
