from data_pipeline.etl.load_lunar_data import (
    build_database_url,
    build_dataframe,
    split_table_name,
)


def test_build_database_url_handles_raw_and_encoded_password():
    raw = build_database_url("postgresql://postgres:Mochileiros@2026@db.example.co:5432/postgres")
    encoded = build_database_url(
        "postgresql://postgres:Mochileiros%402026@db.example.co:5432/postgres"
    )

    assert raw.drivername == "postgresql+psycopg2"
    assert raw.password == "Mochileiros@2026"
    assert raw.host == "db.example.co"
    assert raw.port == 5432
    assert raw.database == "postgres"
    assert raw.render_as_string(hide_password=False) == encoded.render_as_string(
        hide_password=False
    )
    assert "Mochileiros%402026" in raw.render_as_string(hide_password=False)


def test_build_database_url_keeps_reserved_password_characters():
    url = build_database_url("postgres://user:p/a:ss?w@rd#x@db.example.co/postgres?sslmode=require")

    assert url.username == "user"
    assert url.password == "p/a:ss?w@rd#x"
    assert url.host == "db.example.co"
    assert dict(url.query) == {"sslmode": "require"}


def test_split_table_name_supports_schema():
    assert split_table_name("lunar_sites") == (None, "lunar_sites")
    assert split_table_name("public.lunar_sites") == ("public", "lunar_sites")


def test_seed_dataframe_contains_required_sites():
    dataframe = build_dataframe()

    assert len(dataframe) == 3
    assert set(dataframe["name"]) == {
        "Cratera Shackleton",
        "Malapert Mountain",
        "Cratera Faustini",
    }
    assert list(dataframe.columns) == [
        "name",
        "latitude",
        "longitude",
        "elevation_m",
        "science_score",
        "description",
        "source",
    ]
