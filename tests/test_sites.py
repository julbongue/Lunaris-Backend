import pytest
from fastapi.testclient import TestClient

from app.api import deps
from app.core.exceptions import DatabaseUnavailableError
from app.main import app
from app.schemas.sites import DatabaseSite
from app.services.lunar_sites import LunarSiteRepository, _sqlalchemy_url


def test_list_sites(client: TestClient):
    response = client.get("/api/v1/sites")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 8
    ids = {site["id"] for site in payload["sites"]}
    assert "shackleton-rim" in ids
    assert "apollo-11" in ids


def test_list_south_polar_sites(client: TestClient):
    response = client.get("/api/v1/sites", params={"south_polar_only": True})

    assert response.status_code == 200
    sites = response.json()["sites"]
    assert sites
    assert all(site["is_south_polar"] for site in sites)
    assert {site["id"] for site in sites} >= {"shackleton-rim", "cabeus-crater"}


def test_get_site_derives_longitude_convention(client: TestClient):
    response = client.get("/api/v1/sites/cabeus-crater")

    assert response.status_code == 200
    payload = response.json()
    assert payload["longitude_deg"] == -42.13
    assert payload["longitude_east_deg"] == 317.87
    assert payload["is_south_polar"] is True


def test_get_unknown_site_returns_404(client: TestClient):
    response = client.get("/api/v1/sites/not-a-real-site")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_resolve_custom_coordinates(client: TestClient):
    response = client.post(
        "/api/v1/sites/resolve",
        json={
            "name": "My polar site",
            "latitude_deg": -88.5,
            "longitude_deg": -10.25,
            "elevation_m": 1200.0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["persisted"] is False
    assert payload["site"]["is_custom"] is True
    assert payload["site"]["longitude_east_deg"] == 349.75
    assert payload["site"]["elevation_m"] == 1200.0


def test_resolve_invalid_latitude_returns_422(client: TestClient):
    response = client.post(
        "/api/v1/sites/resolve",
        json={"latitude_deg": -100.0, "longitude_deg": 0.0},
    )

    assert response.status_code == 422


class FakeLunarSiteRepository:
    table_name = "lunar_sites"

    def list_sites(self) -> list[DatabaseSite]:
        return [
            DatabaseSite(
                name="Cratera Shackleton",
                latitude_deg=-89.9,
                longitude_deg=-0.5,
                elevation_m=-4200.0,
                science_score=9.8,
                description="Cratera rica em hidrogénio/gelo de água nas bordas.",
                source="NASA LRO / USGS",
            ),
            DatabaseSite(
                name="Malapert Mountain",
                latitude_deg=-86.0,
                longitude_deg=22.7,
                elevation_m=5000.0,
                science_score=9.2,
                description="Excelente visibilidade para comunicação com a Terra.",
                source="NASA Moon Trek",
            ),
        ]


def test_list_database_sites(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: FakeLunarSiteRepository()

    response = client.get("/api/v1/sites/database")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["table"] == "lunar_sites"
    assert payload["source"] == "postgresql"
    assert payload["sites"][0]["name"] == "Cratera Shackleton"
    assert payload["sites"][0]["science_score"] == 9.8
    assert payload["sites"][0]["is_south_polar"] is True
    assert payload["sites"][0]["longitude_east_deg"] == 359.5


def test_database_endpoint_without_database_url_returns_503(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: LunarSiteRepository(None)

    response = client.get("/api/v1/sites/database")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_compare_database_sites_by_name_is_case_insensitive(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: FakeLunarSiteRepository()

    response = client.post(
        "/api/v1/sites/compare",
        json={"sites": ["cratera shackleton", "Malapert Mountain"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["table"] == "lunar_sites"
    assert payload["source"] == "postgresql"
    assert [site["name"] for site in payload["sites"]] == [
        "Cratera Shackleton",
        "Malapert Mountain",
    ]
    assert payload["elevation_difference_m"] == pytest.approx(9200.0)
    assert payload["science_score_difference"] == pytest.approx(0.6)
    assert payload["elevation_comparison"]["lowest"]["site_name"] == "Cratera Shackleton"
    assert payload["elevation_comparison"]["highest"]["site_name"] == "Malapert Mountain"
    assert payload["science_score_comparison"]["highest"]["science_score"] == pytest.approx(9.8)
    assert payload["best_site"]["name"] == "Cratera Shackleton"
    assert payload["recommendation"]["site_name"] == "Cratera Shackleton"
    assert payload["recommendation"]["confidence"] == "high"
    assert "Cratera Shackleton" in payload["recommendation_text"]
    assert payload["matrix"][0]["elevation_difference_from_lowest_m"] == pytest.approx(0.0)
    assert payload["matrix"][0]["science_score_difference_from_best"] == pytest.approx(0.0)
    assert payload["matrix"][1]["elevation_difference_from_lowest_m"] == pytest.approx(9200.0)
    assert payload["matrix"][1]["science_score_difference_from_best"] == pytest.approx(-0.6)


def test_compare_database_sites_accepts_ids_slugs_and_raw_lists(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: FakeLunarSiteRepository()

    response = client.post(
        "/api/v1/sites/compare",
        json={"site_ids": ["cratera-shackleton", "malapert-mountain"]},
    )
    assert response.status_code == 200
    assert [site["id"] for site in response.json()["sites"]] == [
        "cratera-shackleton",
        "malapert-mountain",
    ]

    raw_list_response = client.post(
        "/api/v1/sites/compare",
        json=["malapert-mountain", "Cratera Shackleton"],
    )
    assert raw_list_response.status_code == 200
    assert raw_list_response.json()["requested_identifiers"] == [
        "malapert-mountain",
        "Cratera Shackleton",
    ]


def test_compare_database_sites_reports_missing_identifiers(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: FakeLunarSiteRepository()

    response = client.post(
        "/api/v1/sites/compare",
        json={"sites": ["Cratera Shackleton", "Not a real site"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["missing"] == ["Not a real site"]
    assert payload["sites"][0]["name"] == "Cratera Shackleton"
    assert any("Not a real site" in caveat for caveat in payload["caveats"])


def test_compare_database_sites_unknown_returns_404(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: FakeLunarSiteRepository()

    response = client.post(
        "/api/v1/sites/compare",
        json={"sites": ["Not a real site"]},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_compare_database_sites_without_database_url_returns_503(client: TestClient):
    app.dependency_overrides[deps.get_lunar_sites_repository] = lambda: LunarSiteRepository(None)

    response = client.post(
        "/api/v1/sites/compare",
        json={"sites": ["Cratera Shackleton", "Malapert Mountain"]},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_repository_normalizes_east_longitudes():
    repository = LunarSiteRepository("postgresql://unused", engine=None)
    site = repository._to_site(
        {
            "name": "Polo Sul",
            "latitude": -89.0,
            "longitude": 317.87,
            "elevation_m": None,
            "science_score": None,
            "description": None,
            "source": None,
        }
    )

    assert site.longitude_deg == pytest.approx(-42.13)
    assert site.longitude_east_deg == pytest.approx(317.87)


def test_repository_rejects_unsafe_table_name():
    with pytest.raises(ValueError):
        LunarSiteRepository("postgresql://unused", table_name="lunar_sites; DROP TABLE x")


def test_repository_missing_url_raises_domain_error():
    repository = LunarSiteRepository(None)
    with pytest.raises(DatabaseUnavailableError) as exc_info:
        repository.list_sites()
    assert exc_info.value.code == "database_unavailable"


def test_sqlalchemy_url_forces_psycopg2_driver():
    assert (
        _sqlalchemy_url("postgresql://user:secret@host:5432/db")
        == "postgresql+psycopg2://user:secret@host:5432/db"
    )
    assert (
        _sqlalchemy_url("postgres://user:secret@host:5432/db")
        == "postgresql+psycopg2://user:secret@host:5432/db"
    )
    assert (
        _sqlalchemy_url("postgresql+psycopg2://user:secret@host:5432/db")
        == "postgresql+psycopg2://user:secret@host:5432/db"
    )


def test_sqlalchemy_url_encodes_at_sign_in_password():
    assert (
        _sqlalchemy_url("postgresql://postgres:Mochileiros@2026@db.example.co:5432/postgres")
        == "postgresql+psycopg2://postgres:Mochileiros%402026@db.example.co:5432/postgres"
    )
    assert (
        _sqlalchemy_url("postgresql://postgres:Mochileiros%402026@db.example.co:5432/postgres")
        == "postgresql+psycopg2://postgres:Mochileiros%402026@db.example.co:5432/postgres"
    )
