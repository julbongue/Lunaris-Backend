from __future__ import annotations

from datetime import UTC, datetime

from app.core.exceptions import NotFoundError
from app.core.identifiers import normalize_identifier
from app.schemas.sites import (
    ComparedSite,
    DatabaseSite,
    ElevationComparison,
    ElevationExtreme,
    ScienceScoreComparison,
    ScienceScoreExtreme,
    SiteComparisonRequest,
    SiteComparisonResponse,
    SiteComparisonRow,
    SiteRecommendation,
)
from app.services.lunar_sites import LunarSiteRepository

BASE_CAVEATS = [
    "The comparison uses only the records stored in the PostgreSQL lunar_sites table.",
    "Elevation differences are simple arithmetic differences between stored values; "
    "no terrain, slope or horizon modelling is applied.",
    "Science scores are used as published by the data source and are not recalculated.",
]


def _site_index(sites: list[DatabaseSite]) -> dict[str, DatabaseSite]:
    index: dict[str, DatabaseSite] = {}
    for site in sites:
        for candidate in (site.id, site.name):
            key = normalize_identifier(candidate)
            if key:
                index.setdefault(key, site)
    return index


def _rank_key(site: DatabaseSite) -> tuple[bool, float, bool, float, bool]:
    return (
        site.science_score is not None,
        site.science_score if site.science_score is not None else float("-inf"),
        site.elevation_m is not None,
        site.elevation_m if site.elevation_m is not None else float("-inf"),
        site.is_south_polar,
    )


def _recommendation_key(site: DatabaseSite) -> tuple[float, bool, float, bool]:
    return (
        site.science_score if site.science_score is not None else float("-inf"),
        site.elevation_m is not None,
        site.elevation_m if site.elevation_m is not None else float("-inf"),
        site.is_south_polar,
    )


def _recommend(sites: list[DatabaseSite]) -> SiteRecommendation:
    scored = [site for site in sites if site.science_score is not None]
    if scored:
        ranked = sorted(scored, key=_recommendation_key, reverse=True)
        best = ranked[0]
        runner_up = ranked[1] if len(ranked) > 1 else None
        gap = best.science_score - runner_up.science_score if runner_up else None

        reason = (
            f"{best.name} has the highest science score "
            f"({best.science_score:.2f}) among the compared sites."
        )
        if runner_up is not None and gap is not None:
            reason += (
                f" It leads {runner_up.name} ({runner_up.science_score:.2f}) by {gap:.2f} points."
            )
        if best.is_south_polar:
            reason += (
                " The site is also in the south polar region, which is strategically "
                "relevant for volatile and permanently shadowed region studies."
            )
        if best.elevation_m is not None:
            reason += f" Its stored elevation is {best.elevation_m:.0f} m."

        criteria = ["Highest science score in the requested set."]
        if best.is_south_polar:
            criteria.append("Located in the lunar south polar region.")
        if best.elevation_m is not None:
            criteria.append("Elevation compared as a secondary metric.")

        confidence = "high" if runner_up is None or (gap is not None and gap >= 0.5) else "medium"
        return SiteRecommendation(
            site_id=best.id,
            site_name=best.name,
            reason=reason,
            criteria=criteria,
            confidence=confidence,
            science_score=best.science_score,
            elevation_m=best.elevation_m,
            runner_up_site_name=runner_up.name if runner_up else None,
            science_score_gap=gap,
        )

    elevated = [site for site in sites if site.elevation_m is not None]
    if elevated:
        best = max(elevated, key=lambda site: (site.elevation_m, site.is_south_polar))
        return SiteRecommendation(
            site_id=best.id,
            site_name=best.name,
            reason=(
                f"No science score is available for the compared sites. "
                f"{best.name} is recommended based on its stored elevation "
                f"({best.elevation_m:.0f} m), the highest in the requested set."
            ),
            criteria=["Highest available elevation; science score is unavailable."],
            confidence="low",
            science_score=None,
            elevation_m=best.elevation_m,
        )

    best = sites[0]
    return SiteRecommendation(
        site_id=best.id,
        site_name=best.name,
        reason=(
            f"No science score or elevation data is available. {best.name} is returned as "
            "the first matching site, but no scientific ranking can be justified."
        ),
        criteria=["No science score or elevation data available."],
        confidence="low",
    )


class SiteComparisonService:
    """Builds a basic comparison matrix from the PostgreSQL lunar sites table."""

    def __init__(self, repository: LunarSiteRepository) -> None:
        self._repository = repository

    def compare(self, request: SiteComparisonRequest) -> SiteComparisonResponse:
        available = self._repository.list_sites()
        index = _site_index(available)
        table = getattr(self._repository, "table_name", "lunar_sites")

        matched: list[tuple[str, DatabaseSite]] = []
        missing: list[str] = []
        seen_site_ids: set[str] = set()
        duplicates: list[str] = []

        for identifier in request.sites:
            site = index.get(normalize_identifier(identifier))
            if site is None:
                missing.append(identifier)
                continue
            if site.id in seen_site_ids:
                duplicates.append(identifier)
                continue
            seen_site_ids.add(site.id)
            matched.append((identifier, site))

        if not matched:
            raise NotFoundError(
                "None of the requested lunar sites were found in PostgreSQL.",
                details={"table": table, "missing": missing},
            )

        compared = [
            ComparedSite(**site.model_dump(), requested_identifier=identifier)
            for identifier, site in matched
        ]

        elevated = [site for _, site in matched if site.elevation_m is not None]
        elevation_comparison = ElevationComparison(has_data=bool(elevated))
        if elevated:
            lowest = min(elevated, key=lambda site: site.elevation_m)
            highest = max(elevated, key=lambda site: site.elevation_m)
            elevation_comparison = ElevationComparison(
                has_data=True,
                lowest=ElevationExtreme(
                    site_id=lowest.id,
                    site_name=lowest.name,
                    elevation_m=lowest.elevation_m,
                ),
                highest=ElevationExtreme(
                    site_id=highest.id,
                    site_name=highest.name,
                    elevation_m=highest.elevation_m,
                ),
                difference_m=highest.elevation_m - lowest.elevation_m,
            )

        scored = [site for _, site in matched if site.science_score is not None]
        science_comparison = ScienceScoreComparison(has_data=bool(scored))
        if scored:
            lowest = min(scored, key=lambda site: site.science_score)
            highest = max(scored, key=lambda site: site.science_score)
            science_comparison = ScienceScoreComparison(
                has_data=True,
                highest=ScienceScoreExtreme(
                    site_id=highest.id,
                    site_name=highest.name,
                    science_score=highest.science_score,
                ),
                lowest=ScienceScoreExtreme(
                    site_id=lowest.id,
                    site_name=lowest.name,
                    science_score=lowest.science_score,
                ),
                difference=highest.science_score - lowest.science_score,
                average=sum(site.science_score for site in scored) / len(scored),
            )

        ranked = sorted((site for _, site in matched), key=_rank_key, reverse=True)
        ranks = {id(site): position for position, site in enumerate(ranked, start=1)}
        lowest_elevation = (
            elevation_comparison.lowest.elevation_m if elevation_comparison.lowest else None
        )
        best_score = (
            science_comparison.highest.science_score if science_comparison.highest else None
        )

        matrix = [
            SiteComparisonRow(
                rank=ranks[id(site)],
                site_id=site.id,
                site_name=site.name,
                requested_identifier=identifier,
                latitude_deg=site.latitude_deg,
                longitude_deg=site.longitude_deg,
                longitude_east_deg=site.longitude_east_deg,
                is_south_polar=site.is_south_polar,
                elevation_m=site.elevation_m,
                elevation_difference_from_lowest_m=(
                    site.elevation_m - lowest_elevation
                    if site.elevation_m is not None and lowest_elevation is not None
                    else None
                ),
                science_score=site.science_score,
                science_score_difference_from_best=(
                    site.science_score - best_score
                    if site.science_score is not None and best_score is not None
                    else None
                ),
            )
            for identifier, site in matched
        ]

        recommendation = _recommend([site for _, site in matched])
        best_site = next(site for site in compared if site.id == recommendation.site_id)

        caveats = list(BASE_CAVEATS)
        if missing:
            caveats.append(
                "Some requested identifiers were not found and were excluded from the comparison: "
                + ", ".join(missing)
                + "."
            )
        if duplicates:
            caveats.append(
                "Duplicate identifiers resolving to the same site were compared once: "
                + ", ".join(duplicates)
                + "."
            )
        if not elevation_comparison.has_data:
            caveats.append("No elevation data is available for the matched sites.")
        if not science_comparison.has_data:
            caveats.append("No science score is available for the matched sites.")

        return SiteComparisonResponse(
            created_at=datetime.now(UTC),
            table=table,
            requested_identifiers=list(request.sites),
            sites=compared,
            missing=missing,
            matrix=matrix,
            elevation_comparison=elevation_comparison,
            science_score_comparison=science_comparison,
            elevation_difference_m=elevation_comparison.difference_m,
            science_score_difference=science_comparison.difference,
            best_site=best_site,
            recommendation=recommendation,
            recommendation_text=recommendation.reason,
            caveats=caveats,
        )
