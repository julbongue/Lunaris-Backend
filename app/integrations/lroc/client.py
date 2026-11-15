from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class WmsBoundingBox:
    min_longitude_deg: float
    min_latitude_deg: float
    max_longitude_deg: float
    max_latitude_deg: float


class LrocWmsClient:
    """URL builder for the public LROC Lunaserv WMS.

    The service is a real OGC WMS endpoint operated for LROC QuickMap data.
    It exposes map tiles/images, but its numeric DEM layers are not queryable
    through GetFeatureInfo (verified against the 1.1.1 capabilities document).
    This client therefore only builds map URLs and never claims elevation
    values from WMS.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def capabilities_url(self, version: str = "1.1.1") -> str:
        return str(
            httpx.URL(
                self.base_url,
                params={
                    "service": "WMS",
                    "request": "GetCapabilities",
                    "version": version,
                },
            )
        )

    def getmap_url(
        self,
        *,
        layer_id: str,
        bbox: WmsBoundingBox,
        width: int = 1024,
        height: int = 1024,
        image_format: str = "image/png",
    ) -> str:
        params = {
            "SERVICE": "WMS",
            "VERSION": "1.1.1",
            "REQUEST": "GetMap",
            "LAYERS": layer_id,
            "STYLES": "",
            "SRS": "EPSG:4326",
            "BBOX": (
                f"{bbox.min_longitude_deg:.6f},{bbox.min_latitude_deg:.6f},"
                f"{bbox.max_longitude_deg:.6f},{bbox.max_latitude_deg:.6f}"
            ),
            "WIDTH": str(width),
            "HEIGHT": str(height),
            "FORMAT": image_format,
            "TRANSPARENT": "FALSE",
        }
        return str(httpx.URL(self.base_url, params=params))
