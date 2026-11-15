# Exceções — Motor Científico LUNARIS

Este documento define as exceções que o motor científico deve levantar e
que a camada de API trata.

---

## 1. Exceções já existentes na aplicação

O `app/core/exceptions.py` define uma hierarquia de exceções que são
convertidas em respostas HTTP:

| Exceção | Código HTTP | Código `error.code` | Uso |
|---|---|---|---|
| `LunarisError` | 500 | `internal_error` | Base. |
| `NotFoundError` | 404 | `not_found` | Recurso não encontrado. |
| `BadRequestError` | 400 | `bad_request` | Entrada inválida. |
| `UpstreamServiceError` | 502 | `upstream_error` | Erro no serviço externo (ex.: JPL Horizons). |
| `UpstreamTimeoutError` | 504 | `upstream_timeout` | Timeout no serviço externo. |
| `EngineUnavailableError` | 501 | `engine_unavailable` | Motor pedido não disponível. |

---

## 2. Exceções específicas para o motor

O motor deve levantar exceções da hierarquia acima (ou subclasses).  As
seguintes exceções são recomendadas para o motor científico:

### 2.1 `BadEngineInputError`

Entrada inválida a nível científico (ex.: janela de tempo inválida,
coordendas fora do domínio, terrain indisponível para demanda).

```python
from app.core.exceptions import BadRequestError

class BadEngineInputError(BadRequestError):
    code = "bad_engine_input"
```

### 2.2 `TerrainUnavailableError`

O motor que requer terreno não tem terreno disponível ou os dados do
terreno estão corrompidos/indisponíveis.

```python
from app.core.exceptions import BadRequestError

class TerrainUnavailableError(BadRequestError):
    code = "terrain_unavailable"
    def __init__(self, message, *, details: dict | None = None):
        super().__init__(message, details=details or {})
```

### 2.3 `CoordinateConventionsError`

O motor não suporta as convenções de coordenadas fornecidas (ex.: não
suporta `planetographic` e `inertial` simultaneamente).

```python
from app.core.exceptions import BadRequestError

class CoordinateConventionsError(BadRequestError):
    code = "coordinate_conventions_unsupported"
```

### 2.4 `EngineUnavailableError`

Motor não registado ou desactivado.

```python
from app.core.exceptions import LunarisError

class EngineUnavailableError(LunarisError):
    status_code = 501
    code = "engine_unavailable"
```

### 2.5 `UpstreamServiceError` / `UpstreamTimeoutError`

Para erros de serviços externas (JPL Horizons, acesso ao DEM).  Já definidos.

---

## 3. Nem sempre levantar exceções

O motor deve **não levantar exceções** para:

* `terrain_availability = "none"` — não deve falhar, deve devolver
  `horizon = None`.
* `terrain_availability = "archive"` e o dataset não for encontrado —
  deveria levantar `TerrainUnavailableError`.
* `horizon_reference = "geometric"` — horizonte geométrico sem terreno.

---

## 4. Tratamento na camada de API

O `LunarisError` handler (em `app/main.py`) converte qualquer exceção
na estrutura de erro `{"error": {"code", "message", "details"}}`.

O motor deve levantar exceções com `details` ricos para ajudar no
debug:

```python
raise BadEngineInputError(
    "step_minutes must be between 1 and 1440",
    details={"field": "step_minutes", "value": step_minutes},
)
```

---

## 5. Exceções de validação no Pydantic

Os schemas Pydantic (`app/schemas/engine.py`) levantam `ValidationError`
para valores inválidos.  A API os converte em respostas 422.

Exemplos de validação:

* `latitude_deg` fora de [-90, 90].
* `longitude_deg` fora de [-180, 180].
* `altitude_m` < 0.
* `stop_time <= start_time`.
* `step_minutes` fora de [1, 1440].
* `coordinate_system` ou `reference_frame` inválido.

---

## 6. Boas práticas

* **Nunca** levantar `Exception` genérica; use sempre uma exceção da
  hierarquia existente.
* Incluir mensagens claras e detalhes técnicos.
* Não expor dados sensíveis ou internos do motor nas mensagens.
* Ao levantar `UpstreamServiceError`, incluir `service` e `target` nos
  detalhes para rastreabilidade.


## Implemented error details (Etapa 1)

Scientific adapter may raise `BadRequestError` with `details.code` values including:
- `coordinate_conventions_unsupported` (e.g. `planetographic`)
- `coordinate_transformation_unavailable` (e.g. `inertial`/`ecliptic` without validated transform)
- `terrain_unavailable` (terrain/horizon not supported)

`HorizonsVectorEphemerisProvider` raises `EngineUnavailableError` while real vector ephemerides are not validated/activated. Upstream failures should map to `UpstreamServiceError`/`UpstreamTimeoutError` when applicable.
