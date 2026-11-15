from __future__ import annotations

import json
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.lroc import LrocWmsClient, WmsBoundingBox
from app.integrations.moontrek import MoonTrekClient
from app.schemas.sites import Site
from app.schemas.topography import (
    BoundingBox,
    TopographyContext,
    TopographyLayer,
    TopographyLayerList,
)

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "topography_layers.json"

TOPOGRAPHY_CAVEATS = [
    "Map services provide visual context only. Numeric elevation sampling requires a "
    "local DEM or a dedicated elevation service and is not implemented in this MVP.",
    "LROC Lunaserv numeric DEM layers are not queryable through GetFeatureInfo; the API "
    "does not infer elevations from map images.",
    "Moon Trek WMTS layers are imagery. Use the WMTS capabilities document for tile "
    "matrix and style details.",
]


class TopographyService:
    def __init__(
        self,
        layers: list[TopographyLayer],
        *,
        lroc: LrocWmsClient,
        moontrek: MoonTrekClient,
        settings: Settings,
    ) -> None:
        self._layers = {layer.id: layer for layer in layers}
        if len(self._layers) != len(layers):
            raise ValueError("Duplicate topography layer id in dataset")
        self._lroc = lroc
        self._moontrek = moontrek
        self._settings = settings

    @classmethod
    def from_file(
        cls,
        path: Path = DATA_PATH,
        *,
        lroc: LrocWmsClient | None = None,
        moontrek: MoonTrekClient | None = None,
        settings: Settings | None = None,
    ) -> TopographyService:
        payload = json.loads(path.read_text(encoding="utf-8"))
        layers = [TopographyLayer.model_validate(entry) for entry in payload["layers"]]
        resolved_settings = settings or Settings()
        return cls(
            layers,
            lroc=lroc or LrocWmsClient(resolved_settings.lroc_wms_url),
            moontrek=moontrek or MoonTrekClient(resolved_settings.moontrek_tiles_url),
            settings=resolved_settings,
        )

    def list_layers(
        self,
        *,
        provider: str | None = None,
        data_type: str | None = None,
    ) -> TopographyLayerList:
        layers = list(self._layers.values())
        if provider:
            layers = [layer for layer in layers if layer.provider == provider]
        if data_type:
            layers = [layer for layer in layers if layer.data_type == data_type]
        return TopographyLayerList(
            layers=layers,
            total=len(layers),
            caveats=list(TOPOGRAPHY_CAVEATS),
        )

    def get_layer(self, layer_id: str) -> TopographyLayer:
        layer = self._layers.get(layer_id)
        if layer is None:
            raise NotFoundError(
                f"Topography layer '{layer_id}' was not found.",
                details={"layer_id": layer_id},
            )
        return layer

    def build_context(
        self,
        site: Site,
        *,
        layer_id: str,
        size_deg: float,
    ) -> TopographyContext:
        layer = self.get_layer(layer_id)
        bbox, bbox_notes = self._bbox_for_site(site, size_deg)
        map_url: str | None = None
        tile_url_template: str | None = None

        if layer.access == "wms":
            map_url = self._lroc.getmap_url(
                layer_id=layer.layer_id,
                bbox=WmsBoundingBox(
                    min_longitude_deg=bbox.min_longitude_deg,
                    min_latitude_deg=bbox.min_latitude_deg,
                    max_longitude_deg=bbox.max_longitude_deg,
                    max_latitude_deg=bbox.max_latitude_deg,
                ),
                width=self._settings.topography_map_size_px,
                height=self._settings.topography_map_size_px,
            )
        else:
            tile_url_template = layer.tile_url_template or self._moontrek.tile_url_template(
                layer_id=layer.layer_id
            )

        elevation_available = site.elevation_m is not None
        elevation_source = None
        if elevation_available:
            elevation_source = "user-provided" if site.is_custom else "site_dataset"

        notes = list(bbox_notes)
        if layer.notes:
            notes.append(layer.notes)
        notes.extend(TOPOGRAPHY_CAVEATS)
        if not elevation_available:
            notes.append(
                "No elevation was provided for this site. The API does not infer one "
                "from map imagery."
            )

        return TopographyContext(
            site=site,
            layer=layer,
            bbox=bbox,
            map_url=map_url,
            tile_url_template=tile_url_template,
            capabilities_url=layer.capabilities_url,
            elevation_m=site.elevation_m,
            elevation_available=elevation_available,
            elevation_source=elevation_source,
            notes=notes,
        )

    @staticmethod
    def _bbox_for_site(site: Site, size_deg: float) -> tuple[BoundingBox, list[str]]:
        half = size_deg / 2.0
        min_latitude = max(-90.0, site.latitude_deg - half)
        max_latitude = min(90.0, site.latitude_deg + half)
        min_longitude = site.longitude_deg - half
        max_longitude = site.longitude_deg + half

        notes: list[str] = []
        if min_longitude < -180.0 or max_longitude > 180.0:
            min_longitude = -180.0
            max_longitude = 180.0
            notes.append(
                "The requested bounding box crosses the antimeridian; the full "
                "longitude range was returned."
            )

        return (
            BoundingBox(
                min_latitude_deg=round(min_latitude, 6),
                min_longitude_deg=round(min_longitude, 6),
                max_latitude_deg=round(max_latitude, 6),
                max_longitude_deg=round(max_longitude, 6),
            ),
            notes,
        )
