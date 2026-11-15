# Exemplos de Entrada e Saída — Motor Científico LUNARIS

Este documento apresenta exemplos práticos de entrada e saída para o
contrato definitivo do motor científico.

---

## 1. Exemplo Básico — Célula de Lat/Lon e Janela de Tempo

### Entrada

```json
{
  "latitude_deg": -89.9,
  "longitude_deg": 0.0,
  "altitude_m": 0.0,
  "start_time": "2026-11-15T00:00:00+00:00",
  "stop_time": "2026-11-16T00:00:00+00:00",
  "step_minutes": 360,
  "coordinate_system": "planetocentric",
  "reference_frame": "selenographic",
  "sun_elevation_deg": 0.0,
  "earth_elevation_deg": 5.0,
  "terrain_availability": "none",
  "horizon_reference": "geometric",
  "source": "jpl_horizons"
}
```

### Validação

* `latitude_deg = -89.9` — válido (polos).
* `longitude_deg = 0.0` — válido (próximo do equador / meridianos).
* `altitude_m = 0.0` — válido.
* `start_time` e `stop_time` — UTC, `stop` > `start`.
* `step_minutes = 360` — válido.
* `coordinate_system = "planetocentric"` — válido.
* `reference_frame = "selenographic"` — válido.

### Saída

```json
{
  "earth": {
    "visible": false,
    "elevation_deg": -2.21,
    "azimuth_deg": 356.02,
    "elevation_threshold_deg": 5.0
  },
  "sun": {
    "visible": true,
    "elevation_deg": 2.21,
    "azimuth_deg": 356.02,
    "elevation_threshold_deg": 0.0
  },
  "sun_coordinates": {
    "azimuth_deg": 356.02,
    "elevation_deg": 2.21,
    "range_km": 384400.0
  },
  "earth_coordinates": {
    "azimuth_deg": 356.02,
    "elevation_deg": -2.21,
    "range_km": 384400.0
  },
  "illumination": {
    "phase_angle_deg": 177.0,
    "incidence_angle_deg": 89.9,
    "emission_angle_deg": 0.0,
    "solar_longitude_deg": 176.0
  },
  "conditions": {
    "sunlit": true,
    "dark": false,
    "terminator": false,
    "insolation_w_m2": 0.0
  },
  "horizon": null,
  "quality": {
    "engine_name": "geometric-altaz-threshold",
    "engine_version": "0.1.0",
    "coordinate_system": "planetocentric",
    "reference_frame": "selenographic",
    "elevation_source": "jpl_horizons",
    "temporal_extent": "2026-11-15T00:00:00Z/2026-11-16T00:00:00Z",
    "notes": [
      "No terrain data; horizon is geometric.",
      "Site elevation not provided; 0 km assumed by JPL Horizons."
    ]
  }
}
```
