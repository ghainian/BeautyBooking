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
