from __future__ import annotations

import logging
import math
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import DatabaseUnavailableError
from app.schemas.sites import DatabaseSite

logger = logging.getLogger("lunaris.database")

# Table names are interpolated into the statement, so only allow safe identifiers.
_TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")

_SELECT_SITES = """
SELECT name, latitude, longitude, elevation_m, science_score, description, source
FROM {table}
ORDER BY science_score DESC NULLS LAST, name ASC
"""


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    result = float(value)
    if not math.isfinite(result):
        return None
    return result


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_longitude(value: float) -> float:
    """Normalize any east-positive longitude to the [-180, 180] convention."""

    return ((value + 180.0) % 360.0) - 180.0


def _sqlalchemy_url(database_url: str) -> str:
    """Normalize a PostgreSQL URL into a SQLAlchemy + psycopg2 URL.

    SQLAlchemy 2.x may otherwise default to the psycopg (v3) driver, which is
    not the dependency installed for this project. Passwords containing
    reserved characters (for example an unencoded ``@``) are percent-encoded
    so that the host is parsed correctly.
    """

    scheme, separator, remainder = database_url.partition("://")
    if not separator:
        return database_url
    if scheme in {"postgres", "postgresql"}:
        scheme = "postgresql+psycopg2"
    elif not scheme.startswith("postgresql+"):
        return database_url

    before_query, question, query = remainder.partition("?")
    authority, slash, path = before_query.partition("/")
    userinfo, at, host = authority.rpartition("@")
    if not at:
        return f"{scheme}://{before_query}{question}{query}"

    user, colon, password = userinfo.partition(":")
    if colon and "%" not in password:
        password = quote(password, safe="")
    credentials = f"{user}:{password}" if colon else user
    return f"{scheme}://{credentials}@{host}{slash}{path}{question}{query}"


class LunarSiteRepository:
    """Reads lunar sites from the PostgreSQL ``lunar_sites`` table."""

    def __init__(
        self,
        database_url: str | None,
        *,
        table_name: str = "lunar_sites",
        pool_pre_ping: bool = True,
        engine: Engine | None = None,
    ) -> None:
        if not _TABLE_NAME_PATTERN.match(table_name):
            raise ValueError(f"Invalid lunar sites table name: {table_name!r}")
        self._database_url = database_url
        self._table_name = table_name
        self._pool_pre_ping = pool_pre_ping
        self._engine = engine

    @property
    def table_name(self) -> str:
        return self._table_name

    def list_sites(self) -> list[DatabaseSite]:
        rows = self._fetch_rows()
        return [self._to_site(row) for row in rows]

    def _fetch_rows(self) -> list[Mapping[str, Any]]:
        statement = text(_SELECT_SITES.format(table=self._table_name))
        try:
            with self._get_engine().connect() as connection:
                return list(connection.execute(statement).mappings().all())
        except SQLAlchemyError as exc:
            logger.warning(
                "Failed to query %s from PostgreSQL: %s",
                self._table_name,
                exc.__class__.__name__,
            )
            raise DatabaseUnavailableError(
                "Could not read lunar sites from PostgreSQL.",
                details={"table": self._table_name},
            ) from exc

    def _get_engine(self) -> Engine:
        if self._engine is not None:
            return self._engine
        if not self._database_url:
            raise DatabaseUnavailableError(
                "DATABASE_URL is not configured; the PostgreSQL lunar sites endpoint "
                "is unavailable.",
                details={"table": self._table_name},
            )
        try:
            self._engine = create_engine(
                _sqlalchemy_url(self._database_url),
                pool_pre_ping=self._pool_pre_ping,
            )
        except (SQLAlchemyError, ValueError) as exc:
            raise DatabaseUnavailableError(
                "The PostgreSQL connection URL is invalid.",
                details={"table": self._table_name},
            ) from exc
        return self._engine

    def _to_site(self, row: Mapping[str, Any]) -> DatabaseSite:
        try:
            return DatabaseSite(
                name=str(row["name"]),
                latitude_deg=float(row["latitude"]),
                longitude_deg=_normalize_longitude(float(row["longitude"])),
                elevation_m=_optional_float(row.get("elevation_m")),
                science_score=_optional_float(row.get("science_score")),
                description=_optional_str(row.get("description")),
                source=_optional_str(row.get("source")),
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise DatabaseUnavailableError(
                "The lunar sites table returned a row with an unexpected shape.",
                details={"table": self._table_name, "row_name": row.get("name")},
            ) from exc
