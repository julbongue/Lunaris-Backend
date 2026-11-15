"""Seed the PostgreSQL/Supabase ``lunar_sites`` table with curated lunar sites.

The connection URL is converted into a SQLAlchemy :class:`~sqlalchemy.engine.URL`
with the explicit ``postgresql+psycopg2`` driver. Building the URL from its
components lets SQLAlchemy percent-encode reserved characters in the password
(``@``, ``/``, ``:``, ``?``, ``#``, ``%``, ...), so an unencoded ``@`` in a
password is no longer mistaken for the host separator.

Usage
-----
Install the ETL dependencies and run the module from the repository root::

    python -m pip install -r data_pipeline/requirements.txt
    python -m data_pipeline.etl.load_lunar_data

The script loads ``DATABASE_URL`` from the environment or from ``.env``. It can
also build the URL from ``POSTGRES_HOST``, ``POSTGRES_PORT``, ``POSTGRES_USER``,
``POSTGRES_PASSWORD`` and ``POSTGRES_DB`` when ``DATABASE_URL`` is absent.

Examples::

    # Replace the table with the seed rows (default)
    python -m data_pipeline.etl.load_lunar_data

    # Append to an existing table, or inspect the data without connecting
    python -m data_pipeline.etl.load_lunar_data --if-exists append
    python -m data_pipeline.etl.load_lunar_data --dry-run

    # Pass the URL explicitly (it takes precedence over DATABASE_URL)
    python -m data_pipeline.etl.load_lunar_data --database-url "postgresql://..."
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_TABLE = "lunar_sites"
DRIVER_NAME = "postgresql+psycopg2"

_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Dados lunares essenciais para o hackathon.
LUNAR_SITES: list[dict[str, Any]] = [
    {
        "name": "Cratera Shackleton",
        "latitude": -89.9,
        "longitude": 0.0,
        "elevation_m": -4200.0,
        "science_score": 9.8,
        "description": "Cratera rica em hidrogênio/gelo de água nas bordas.",
        "source": "NASA LRO / USGS",
    },
    {
        "name": "Malapert Mountain",
        "latitude": -86.0,
        "longitude": 22.7,
        "elevation_m": 5000.0,
        "science_score": 9.2,
        "description": "Excelente visibilidade para comunicação com a Terra.",
        "source": "NASA Moon Trek",
    },
    {
        "name": "Cratera Faustini",
        "latitude": -87.2,
        "longitude": 77.0,
        "elevation_m": -3900.0,
        "science_score": 8.9,
        "description": "Área de sombra permanente com potencial de voláteis.",
        "source": "NASA PDS",
    },
]


def build_database_url(raw_url: str) -> URL:
    """Convert a PostgreSQL URL string into a SQLAlchemy ``URL`` object.

    SQLAlchemy's default parser treats an unencoded ``@`` in the password as the
    host separator, which breaks passwords such as ``Mochileiros@2026``. Split
    the credentials at the *last* ``@`` instead and pass the raw (percent-decoded)
    components to :meth:`URL.create`. SQLAlchemy then re-encodes the password
    correctly when rendering the URL for psycopg2.
    """

    raw_url = raw_url.strip()
    if not raw_url:
        raise ValueError("A URL de ligação PostgreSQL está vazia.")

    scheme, separator, remainder = raw_url.partition("://")
    if not separator:
        raise ValueError(
            "A URL de ligação deve começar por postgresql://, "
            "postgres:// ou postgresql+psycopg2://."
        )

    if scheme in {"postgres", "postgresql"} or scheme.startswith("postgresql+"):
        driver_name = DRIVER_NAME
    else:
        raise ValueError(f"Esquema de base de dados não suportado: {scheme!r}.")

    # Split credentials from the rest at the last "@" so a raw "@" in the
    # password survives. Splitting the query string afterwards also keeps raw
    # "?", "/", ":" and "#" characters inside the password intact.
    userinfo, at_sign, host_and_query = remainder.rpartition("@")
    if at_sign:
        username, colon, password = userinfo.partition(":")
        username = unquote(username) or None
        password = unquote(password) if colon else None
    else:
        username = None
        password = None
        host_and_query = remainder

    host_and_path, _, query = host_and_query.partition("?")
    host_port, _, database = host_and_path.partition("/")

    parsed_host = urlsplit(f"//{host_port}")
    host = parsed_host.hostname
    try:
        port = parsed_host.port
    except ValueError as exc:
        raise ValueError(f"Porta inválida na URL de ligação: {host_port!r}.") from exc
    if not host:
        raise ValueError("A URL de ligação não inclui o host PostgreSQL.")

    query_params = dict(parse_qsl(query, keep_blank_values=True))

    return URL.create(
        drivername=driver_name,
        username=username,
        password=password,
        host=host,
        port=port,
        database=unquote(database) or None,
        query=query_params,
    )


def resolve_database_url(explicit_url: str | None = None) -> URL:
    """Resolve the database URL from the CLI, environment, or ``POSTGRES_*`` vars."""

    raw_url = explicit_url or os.getenv("DATABASE_URL")
    if raw_url:
        return build_database_url(raw_url)

    host = os.getenv("POSTGRES_HOST")
    password = os.getenv("POSTGRES_PASSWORD")
    if host and password:
        port = os.getenv("POSTGRES_PORT", "5432")
        if not port.isdigit():
            raise ValueError(f"POSTGRES_PORT inválido: {port!r}.")
        return URL.create(
            drivername=DRIVER_NAME,
            username=os.getenv("POSTGRES_USER", "postgres"),
            password=password,
            host=host,
            port=int(port),
            database=os.getenv("POSTGRES_DB", "postgres"),
        )

    raise ValueError(
        "DATABASE_URL não está definida. Defina-a no ambiente/.env ou forneça "
        "POSTGRES_HOST e POSTGRES_PASSWORD (opcionalmente POSTGRES_PORT, "
        "POSTGRES_USER e POSTGRES_DB)."
    )


def split_table_name(value: str) -> tuple[str | None, str]:
    """Split an optional ``schema.table`` name and reject unsafe identifiers."""

    schema, dot, table = value.strip().rpartition(".")
    if dot:
        if not _TABLE_NAME_PATTERN.match(schema) or not _TABLE_NAME_PATTERN.match(table):
            raise ValueError(f"Nome de tabela inválido: {value!r}.")
        return schema, table
    if not _TABLE_NAME_PATTERN.match(value):
        raise ValueError(f"Nome de tabela inválido: {value!r}.")
    return None, value


def build_dataframe() -> pd.DataFrame:
    """Build the seed DataFrame with a stable column order."""

    return pd.DataFrame(
        LUNAR_SITES,
        columns=[
            "name",
            "latitude",
            "longitude",
            "elevation_m",
            "science_score",
            "description",
            "source",
        ],
    )


def load_dataframe(
    dataframe: pd.DataFrame,
    engine: Engine,
    *,
    table_name: str,
    schema: str | None = None,
    if_exists: str = "replace",
) -> None:
    """Write the seed rows with ``pandas.DataFrame.to_sql``."""

    with engine.begin() as connection:
        dataframe.to_sql(
            table_name,
            connection,
            schema=schema,
            if_exists=if_exists,
            index=False,
        )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Popula a tabela lunar_sites no PostgreSQL/Supabase.",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="URL PostgreSQL; sobrepõe DATABASE_URL.",
    )
    parser.add_argument(
        "--table",
        default=None,
        help="Tabela de destino (default: LUNAR_SITES_TABLE ou lunar_sites).",
    )
    parser.add_argument(
        "--if-exists",
        choices=("replace", "append"),
        default="replace",
        help="replace recria a tabela com os dados iniciais; append acrescenta linhas.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        help="Ficheiro .env a carregar (default: .env na raiz do repositório).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra os dados e a ligação sem escrever na base de dados.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.env_file.is_file():
        load_dotenv(args.env_file, override=False)

    table_value = args.table or os.getenv("LUNAR_SITES_TABLE", DEFAULT_TABLE)
    try:
        url = resolve_database_url(args.database_url)
        schema, table_name = split_table_name(table_value)
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    dataframe = build_dataframe()
    qualified_table = f"{schema}.{table_name}" if schema else table_name
    safe_url = url.render_as_string(hide_password=True)

    if args.dry_run:
        print(dataframe.to_string(index=False))
        print(f"\nDestino: {qualified_table} ({args.if_exists})")
        print(f"Ligação: {safe_url}")
        return 0

    engine: Engine | None = None
    try:
        engine = create_engine(url)
        load_dataframe(
            dataframe,
            engine,
            table_name=table_name,
            schema=schema,
            if_exists=args.if_exists,
        )
    except (SQLAlchemyError, ValueError) as exc:
        print(
            f"erro: não foi possível carregar {len(dataframe)} locais em {qualified_table}: {exc}",
            file=sys.stderr,
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print(f"🚀 {len(dataframe)} locais lunares carregados em {qualified_table}.")
    print(f"Base de dados: {safe_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
