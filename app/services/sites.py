from __future__ import annotations

import json
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.sites import CoordinateSiteReference, KnownSiteReference, Site, SiteReference

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "sites.json"


class SiteService:
    def __init__(self, sites: list[Site]) -> None:
        self._sites = {site.id: site for site in sites}
        if len(self._sites) != len(sites):
            raise ValueError("Duplicate site id in dataset")

    @classmethod
    def from_file(cls, path: Path = DATA_PATH) -> SiteService:
        payload = json.loads(path.read_text(encoding="utf-8"))
        sites = [Site.model_validate(entry) for entry in payload["sites"]]
        return cls(sites)

    def list_sites(
        self,
        *,
        region: str | None = None,
        south_polar_only: bool = False,
    ) -> list[Site]:
        sites = list(self._sites.values())
        if region:
            normalized = region.strip().lower()
            sites = [site for site in sites if site.region.lower() == normalized]
        if south_polar_only:
            sites = [site for site in sites if site.is_south_polar]
        return sorted(sites, key=lambda site: (not site.is_south_polar, site.name))

    def get(self, site_id: str) -> Site:
        site = self._sites.get(site_id)
        if site is None:
            raise NotFoundError(
                f"Lunar site '{site_id}' was not found.",
                details={"site_id": site_id},
            )
        return site

    def resolve(self, reference: SiteReference) -> Site:
        if isinstance(reference, KnownSiteReference):
            return self.get(reference.site_id)
        if isinstance(reference, CoordinateSiteReference):
            return self._custom_site(reference)
        raise BadRequestError("Unsupported site reference.")

    @staticmethod
    def _custom_site(reference: CoordinateSiteReference) -> Site:
        name = reference.name or (
            f"Custom site ({reference.latitude_deg:.3f}, {reference.longitude_deg:.3f})"
        )
        return Site(
            id="custom",
            name=name,
            latitude_deg=reference.latitude_deg,
            longitude_deg=reference.longitude_deg,
            elevation_m=reference.elevation_m,
            region="custom",
            site_type="user_defined",
            mission=None,
            country=None,
            description="User-provided lunar coordinates. This site is not persisted.",
            source_url=None,
            tags=["custom"],
            coordinate_precision_deg=None,
            is_custom=True,
        )
