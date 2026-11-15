# Contrato de Integração com o Frontend

Este documento define o contrato de integração entre o backend LUNARIS e o
frontend, garantindo que os modelos Pydantic, respostas JSON, tipos
numéricos, campos, datas/horários, unidades e convenções de coordenadas se
encontram.

---

## 1. Objetivo

Garantir que:

* O frontend consiga consumir as respostas da API sem alterações.
* As novas funcionalidades do motor científico (visibilidade Terra/Sol,
  iluminação, obstrução de horizonte) sejam transportadas sem quebrar o
  contrato atual.
* As diferenças de convenção (graus vs radianos, latitude planetocêntrica
  vs planetográfica, longitude east-positive) sejam claramente documentadas.

---

## 2. Contrato de Entrada (Frontend → API)

O frontend envia `AnalysisRequest` (ou `ComparisonRequest`) com:

| Campo | Tipo | Notas |
|---|---|---|
| `site` | object | `KnownSiteReference` ou `CoordinateSiteReference` |
| `start_time` | string (ISO 8601 UTC) | ex. `2026-11-15T00:00:00Z` |
| `stop_time` | string (ISO 8601 UTC) | ex. `2026-11-17T00:00:00Z` |
| `step_minutes` | integer | [1, 1440] |
| `thresholds` | object | `sun_elevation_deg` [deg], `earth_elevation_deg` [deg] |
| `include_samples` | boolean | default `true` |
| `terrain_availability` | string | `"none" | "local" | "archive"` (novo, se fornecido) |

### Unidades

* Todos os ângulos em **graus**.
* Tempo em **UTC ISO 8601**.
* Distância: não utilizado no input atual.
* Elevação do observador: metros (via `site.elevation_m` ou
  `CoordinateSiteReference.elevation_m`).

---

## 3. Contrato de Saída (API → Frontend)

### 3.1 `AnalysisResult`

Os campos principais retornados:

```json
{
  "analysis_id": "string",
  "created_at": "string (ISO 8601 UTC)",
  "site": { ... },
  "time_range": {
    "start_time": "string (ISO 8601 UTC)",
    "stop_time": "string (ISO 8601 UTC)",
    "step_minutes": 360
  },
  "thresholds": {
    "sun_elevation_deg": 0.0,
    "earth_elevation_deg": 5.0
  },
  "summary": {
    "total_samples": 9,
    "sun_above_threshold_pct": 100.0,
    "earth_above_threshold_pct": 0.0,
    "solar_window_count": 1,
    "communication_window_count": 0
  },
  "solar_windows": [ ... ],
  "communication_windows": [ ... ],
  "samples": [ ... ],
  "model": { ... },
  "sources": [ ... ],
  "caveats": [ ... ]
}
```

### 3.2 Campos adicionais a partir do motor científico

Para transportar o novo contrato científico, a `AnalysisResult` (ou o
`EngineResult`) deve incluir:

* `earth.visible` (boolean)
* `earth.elevation_deg` (float, graus)
* `earth.azimuth_deg` (float, graus)
* `sun.visible` (boolean)
* `sun.elevation_deg` (float, graus)
* `sun.azimuth_deg` (float, graus)
* `sun_coordinates.altitude_deg`, `.azimuth_deg`, `.range_km`
* `earth_coordinates.altitude_deg`, `.azimuth_deg`, `.range_km`
* `illumination.phase_angle_deg`, `.incidence_angle_deg`,
  `.emission_angle_deg`, `.solar_longitude_deg`
* `conditions.sunlit`, `.dark`, `.terminator`, `.insolation_w_m2`
* `horizon.ref`, `.horizon_elevation_deg`, `.has_data`, `.source`, `.notes`
* `quality.engine_name`, `.engine_version`, `.coordinate_system`,
  `.reference_frame`, `.elevation_source`, `.temporal_extent`, `.notes`

---

## 4. Mapeamento dos Modelos Pydantic

### 4.1 `Thresholds` (legacy) ↔ `EngineInput.threshods`

| Legacy (Pydantic) | New (EngineInput) |
|---|---|
| `sun_elevation_deg: float` | `sun_elevation_deg: float` (graus) |
| `earth_elevation_deg: float` | `earth_elevation_deg: float` (graus) |

### 4.2 `AnalysisRequest` ↔ `EngineInput`

| `AnalysisRequest` (API) | `EngineInput` (definitive) |
|---|---|
| `site` (conhecido/coordenadas) | `latitude_deg`, `longitude_deg`, `altitude_m` |
| `start_time`, `stop_time`, `step_minutes` | `start_time`, `stop_time`, `step_minutes` |
| `coordinate_system` | `coordinate_system` (default `planetocentric`) |
| `reference_frame` | `reference_frame` (default `selenographic`) |
| `terrain_availability` | `terrain_availability` (default `none`) |

### 4.3 Unidades e convenções de coordenadas

| Conceito | Convenção |
|---|---|
| Latitude | graus, [-90, 90], positivo para norte |
| Longitude | graus, east-positive, [-180, 180] ou [0, 360) |
| Azimuth | graus, [0, 360), horário a partir do Norte |
| Elevation | graus, [-90, 90] |
| Altitude do observador | metros |
| Tempo | UTC ISO 8601 |
| Distância | metros (DEM), quilómetros (JPL Horizons) |

---

## 5. Campos Obrigatórios e Opcionais

| Campo | Obrigatório | Notas |
|---|---|---|
| `analysis_id` | sim | UUID |
| `created_at` | sim | ISO 8601 UTC |
| `summary` | sim | Métricas de visibilidade |
| `solar_windows` | sim | Lista |
| `communication_windows` | sim | Lista |
| `samples` | opcional | Se `include_samples=true` |
| `model` | sim | Metadados do motor |
| `caveats` | sim | Listas de avisos |
| `earth.visible` | opcional | Novo (motor científico) |
| `sun.visible` | opcional | Novo (motor científico) |
| `illumination` | opcional | Novo (motor científico) |
| `horizon` | opcional | Novo (motor científico) |
| `quality` | opcional | Novo (motor científico) |

---

## 6. Datas e Fusos Horários

* Todas as datas no JSON são **ISO 8601** com **UTC** (sufixo `Z`).
* O timezone é sempre UTC; não devem ser enviados offset numa outra
  timezone.
* O backend normaliza `start_time`/`stop_time` para UTC no Pydantic
  validator.

---

## 7. Unidades e Convenções de Coordenadas

### 7.1 Ângulos

* Graus, a menos que explicitamente indicado.
* Intervalos validados: latitude [-90, 90]; longitude [-180, 180] (ou
  [0, 360) normalizado); azimute [0, 360); elevação [-90, 90].

### 7.2 Latitude planetocêntrica vs planetográfica

* O contrato exige que a convenção seja declarada no `coordinate_system`
  do `EngineInput`.
* Valores em graus são interpretados respectivamente:
  * `planetocentric`: latitude a partir do equador lunar.
  * `planetographic`: latitude sobre o elipsóide de referência.
* O frontend deve fornecer o `coordinate_system` se não usar o padrão
  (`planetocentric`).

### 7.3 Longitude east-positive

* Valores em [-180, 180] são normalizados para [0, 360).
* Ex.: `-42.13` → `317.87`.

---

## 8. Evolução do Contrato

* O contrato atual é estável e não deve ser quebrado.
* Novas funcionalidades do motor científico podem adicionar campos
  opcionais (`earth`, `sun`, `illumination`, `horizon`, `quality`).
* A adição de novos campos não quebra a compatibilidade do frontend,
  desde que o frontend trate campos ausentes.

---

## 9. Exemplos de Resposta

### 9.1 Resposta de análise (resumo)

```json
{
  "analysis_id": "a1b2c3d4-e5f6-7890-...",
  "created_at": "2026-11-15T07:26:51Z",
  "site": {
    "id": "shackleton-rim",
    "name": "Shackleton Crater (reference point)",
    "latitude_deg": -89.9,
    "longitude_deg": 0.0,
    "longitude_east_deg": 0.0,
    "region": "lunar_south_pole"
  },
  "summary": {
    "total_samples": 9,
    "sun_above_threshold_pct": 100.0,
    "earth_above_threshold_pct": 0.0
  },
  "solar_windows": [ ... ],
  "communication_windows": [],
  "quality": {
    "engine_name": "geometric-altaz-threshold",
    "engine_version": "0.1.0",
    "elevation_source": "jpl_horizons",
    "temporal_extent": "2026-11-15T00:00:00Z/2026-11-17T00:00:00Z"
  }
}
```

### 9.2 Resposta com motor científico (esquema)

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
    "engine_name": "lola-terrain-baseline",
    "engine_version": "1.0.0",
    "coordinate_system": "planetocentric",
    "reference_frame": "selenographic",
    "elevation_source": "lola",
    "temporal_extent": "2026-11-15T00:00:00Z/2026-11-16T00:00:00Z"
  }
}
```

---

## 10. Resumo das Regras de Consistência

* `latitude_deg` em [-90, 90], positivo para norte.
* `longitude_deg` em [-180, 180] ou normalizado para [0, 360).
* Ângulos em graus.
* Tempo em UTC.
* `earth.elevation_deg` e `sun.elevation_deg` em graus acima do horizonte.
* `horizon_elevation_deg` em graus de depressão abaixo do horizonte
  geométrico.
* O frontend deve tratar ausência de campos opcionais como
  indefinido/nulo.
