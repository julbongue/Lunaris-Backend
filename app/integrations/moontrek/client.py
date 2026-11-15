from __future__ import annotations


class MoonTrekClient:
    """URL builder for NASA Moon Trek OGC WMTS layers.

    Moon Trek also exposes a Trek catalog REST service. The MVP uses curated,
    verified WMTS layer metadata from app/data/topography_layers.json instead
    of downloading the large live catalog on every request.
    """

    def __init__(self, tiles_base_url: str) -> None:
        self.tiles_base_url = tiles_base_url.rstrip("/")

    def capabilities_url(self, *, layer_id: str, projection: str = "EQ") -> str:
        return f"{self.tiles_base_url}/{projection}/{layer_id}/1.0.0/WMTSCapabilities.xml"

    def tile_url_template(
        self,
        *,
        layer_id: str,
        projection: str = "EQ",
        style: str = "default",
        tile_matrix_set: str = "default028mm",
        extension: str = "jpg",
    ) -> str:
        return (
            f"{self.tiles_base_url}/{projection}/{layer_id}/1.0.0/"
            f"{style}/{tile_matrix_set}/{{z}}/{{y}}/{{x}}.{extension}"
        )
