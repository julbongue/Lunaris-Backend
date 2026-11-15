# Metodologia de Integração do DEM — Horizon Obstruction

This document describes the methodology to integrate a lunar DEM dataset
into the LUNARIS scientific engine, focused on horizon obstruction.

---

## 1. Work Structure

DEM integration should be done through a service/adaptation layer on top
of the engine, without modifying the API. The workflow is:

```
EngineInput (definitive) ──▶ Scientific Engine ──▶ DEM Service ──▶ DEM Dataset
      ▲                                     │
      │                                     ▼
   EngineResult                         Elevation (m)
      │                                     │
      ▼                                     ▼
   HorizonObstruction (topographic) ◄── Geoprocessing
```

---

## 2. DEM Service Layer

### 2.1 API

```python
class DemService:
    def __init__(self, path: Path): ...

    def get_elevation(self, latitude_deg: float, longitude_deg: float) -> float | None:
        """Return elevation in meters above reference surface."""

    def get_profile(
        self,
        latitude_deg: float,
        longitude_deg: float,
        azimuth_deg: float,
        distance_max_m: float,
        segment_step_m: float = 100.0,
    ) -> list[dict[str, float]]:
        """Return a list of points along the azimuth: distance, lat, lon, elevation."""
```

### 2.2 Reading Method

1. Read the PDS3 label.
2. Open the raster with `rasterio`.
3. Convert `(lat, lon)` to pixel coordinates using the geotransform.
4. Read the raw value.
5. Convert with `scale` and `offset`.
6. Return elevation in meters.

### 2.3 Loading Strategy

For performance:

* Open the raster once (singleton).
* Use `rasterio` with chunked `read` to avoid excessive allocation.
* Cache elevation queries (e.g. `functools.lru_cache`).

---

## 3. Horizon Obstruction Calculation

### 3.1 Geometric Visibility

Without terrain:

```
visible = elevation_body_deg >= threshold
```

### 3.2 Topographic Visibility

With terrain:

1. Obtain the elevation profile along the body azimuth.
2. For each point along the profile, compute the line-of-sight angle:

```
angle_point = atan2(elevation_point - elevation_observer, distance)
```

3. `horizon_elevation_deg` is the minimum of `angle_point` along the
   profile (the highest terrain that blocks).

```
# Simplification: if the highest terrain along the azimuth is a_1, a_2, ...
# and the body has elevation_ang and threshold:
topographic_visible = min(angle_points) >= (elevation_body_deg - threshold)
```

### 3.3 Consistency

* When `terrain_availability = "none"`, visibility is geometric.
* When `terrain_availability = "local"` / `"archive"`, topographic
  visibility is returned with `horizon_elevation_deg` explained.

---

## 4. Topographic Profile

### 4.1 Example Metrics

For the MVP and tests, use:

* `distance_max = 10_000 m` (10 km).
* `segment_step = 100 m` → 100 points.

### 4.2 Coordinates Along the Profile

```
def destination_point(lat_deg, lon_deg, azimuth_deg, distance_m):
    # Spherical earth with radius R_moon = 1737400 m
    R = 1737400.0
    lat_rad = radians(lat_deg)
    lon_rad = radians(lon_deg)
    bearing_rad = radians(azimuth_deg)
    d = distance_m / R
    lat2 = asin(sin(lat_rad) * cos(d) + cos(lat_rad) * sin(d) * cos(bearing_rad))
    lon2 = lon_rad + atan2(sin(bearing_rad) * sin(d) * cos(lat_rad),
                           cos(d) - sin(lat_rad) * sin(lat2))
    return degrees(lat2), degrees(lon2)
```

### 4.3 Depression Angle

```
def depression_angle(elevation_terrain_m, elevation_observer_m, distance_m):
    dH = elevation_terrain_m - elevation_observer_m
    # angle in degrees (negative = depression)
    return degrees(atan2(dH, distance_m))
```

### 4.4 Horizon Obstruction

```
horizon_elevation_deg = min(depression_angle over profile)
```

A negative value indicates depression below the geometric horizon.

---

## 5. Integration with the Engine

### 5.1 Engine State

The engine receives:

* `EngineInput` definitively.
* `terrain_availability` indicating if terrain is available.

If available:

* The engine requests the elevation profile for the relevant azimuths.
* `HorizonObstruction` is populated with `horizon_elevation_deg`.

### 5.2 Search Parameters

* For the MVP, use a 360° angular profile (full circle) or only the
  azimuth to the nearest body (Earth/Sun).
* For each azimuth:
  * Obtain the profile.
  * Compute the obstruction.

### 5.3 Interpolation

* The engine should use bilinear interpolation to obtain elevation in
  pixels; a simple pixel read may be too inaccurate.
* Do not use zero padding; use the label to define the exterior.

---

## 6. Validation of DEM Integration

### 6.1 Unit Tests

Simple test:

1. Create a small synthetic DEM with known elevation (e.g. a plane at
   elevation 0, or a mesa at elevation 100 m).
2. Read with `DemService`.
3. Verify `get_elevation` returns the correct value.
4. Verify the profile returns the correct elevation along the azimuth.

### 6.2 Integration Tests

* Use Shackleton and verify the elevation is consistent with the terrain.
* Compare geometric visibility (without terrain) with topographic
  visibility (with terrain).
* Verify `horizon_elevation_deg` is returned.

### 6.3 End-to-End Test

* Make an `AnalysisRequest` with `terrain_availability = "archive"` and
  verify the response includes `horizon` with `has_data = true`.

---

## 7. Limitations and Caveats

* The profile is a straight line of sight; it does not consider the
  curvature of the Moon.  For short distances (km), it is a good
  approximation.
* Terrain elevation is a single surface; there is no shadowing model.
* Obstruction accuracy depends on raster resolution (e.g. 118 m vs 5 m).

---

## 8. Summary of Steps

1. Install `rasterio`/`GDAL` and `pvl` (when authorized).
2. Download LOLA GDR 64 ppd product (PDS3).
3. Implement `DemService` (read, interpolate, profile).
4. Add `horizon_elevation_deg` logic in the engine.
5. Update `AnalysisService` to use `terrain_availability`.
6. Update `AnalysisResult` (or convert `EngineResult`) to include `horizon`.
7. Write unit and integration tests.
