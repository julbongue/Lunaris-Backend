# Integração do Motor Científico — Arquitetura e Injeção

Este documento descreve como arquitectar a integração do motor científico
no backend sem alterar os endpoints da API.

---

## 1. Visão Geral

```
Frontend ──▶ API (FastAPI) ──▶ Service (AnalysisService) ──▶ Engine
                                              │
                                              ├──▶ EngineInput (definitive)
                                              │
                                              └──▶ EngineResult (definitive)
```

* Os endpoints (`app/api/v1/endpoints/analysis.py`, `scenarios.py`) continuam
  a aceitar o mesmo contrato de entrada (`AnalysisRequest`).
* O `AnalysisService` (ou uma camada de adaptação) converte o input do
  endpoint para o `EngineInput` definitivo.
* O `ScientificEngine` protocol define a interface que qualquer motor
  deve implementar.
* O resultado do motor (`EngineResult`) é convertido de volta para o
  `AnalysisResult` que a API devolve.

---

## 2. Camadas

### 2.1 API (`app/api/v1/endpoints/`)

* Nenhuma mudança necessária para aceitar um motor novo.
* O endpoint recebe `AnalysisRequest`, resolve o `Site` e passa para o
  `AnalysisService`.
* O endpoint não deve saber que tipo de motor está em uso.

### 2.2 Service (`app/services/analysis.py`)

A camada de serviço é responsável por:

1. Resolver o site e extrair os parâmetros (coordenadas, tempo, thresholds).
2. Criar o `EngineInput` definitivo (ou adaptar o input do endpoint).
3. Invocar o `ScientificEngine` através do protocolo.
4. Converter o `EngineResult` para `AnalysisResult` (ou deixar o motor
   devolver `AnalysisResult` diretamente).
5. Salvar no `AnalysisStore` e devolver.

A camada de adaptação deve ser claro e testável.

### 2.3 Engine (`app/services/engine/`)

* `base.py` — protocolos (`ScientificEngine`), tipos legados
  (`EngineInput`, `EngineOutput`).
* `schemas.py` — o novo contrato Pydantic (definido em `app/schemas/engine.py`).
* `registry.py` — registo de motores disponíveis.
* `geometric.py` — implementação legada (não alterada).
* Ficheiros de motor novo (`lola_engine.py`, `spice_engine.py`, ...).

---

## 3. Injeção de Dependência

O `app/api/deps.py` já injeta o motor através de:

```python
def get_scientific_engine() -> ScientificEngine:
    return get_engine(settings.scientific_engine)
```

E `AnalysisService` recebe o motor como dependência.

Para o motor novo:

1. Implementar o `ScientificEngine` protocol.
2. Registar no `registry.py` com um nome.
3. Opções de configuração:
   * `SCIENTIFIC_ENGINE=lola-terrain` — seleccionar via config.
   * Override de dependência no layer de teste.
   * Substituição no registo.

---

## 4. Registo de Motores

O `registry.py` é actualmente:

```python
_ENGINES: dict[str, ScientificEngine] = {
    "geometric": GeometricEngine(),
}

def get_engine(name: str) -> ScientificEngine:
    engine = _ENGINES.get(name)
    if engine is None:
        available = ", ".join(sorted(_ENGINES))
        raise EngineUnavailableError(...)
    return engine
```

Para o motor novo:

* Adicionar à constante `_ENGINES` (com o nome do motor).
* Manter o `get_engine` como point of access.
* O motor novo deve implementar o protocolo definitivo.

---

## 5. Conversão de Contratos

O `AnalysisResult` atual contém:

* `summary`, `solar_windows`, `communication_windows`, `samples`, `model`,
  `caveats`.

O `EngineResult` definitivo contém:

* `earth`, `sun`, `sun_coordinates`, `earth_coordinates`,
  `illumination`, `conditions`, `horizon`, `quality`.

A conversão deve:

1. Mapear `summary` → `summary` (ou recalcular).
2. Mapear `solar_windows` → `windows` (janelas de sol).
3. Mapear `communication_windows` → `windows` (janelas de comunicação).
4. Usar `EarthVisibility`/`SunVisibility` para os campos de visibilidade.
5. Usar `IlluminationAngles`/`IlluminationConditions` para iluminação.
6. Anexar `HorizonObstruction`/`DataQualityMetadata` quando disponíveis.
7. Manter `model` e `limitations` (do motor legado) para compatibilidade.

A camada de adaptação é opcional.  Se o motor novo puder produzir
diretamente `AnalysisResult`, não é necessária a conversão.  Mas a
arquitetura deve ser clara e testável.

---

## 6. Configuração de Motores

* A configuração do nome do motor é via `SCIENTIFIC_ENGINE`.
* O motor deve ser disponível e activo; se não estiver disponível,
  `EngineUnavailableError` (501) é levantada.
* O `SourceService` e o catálogo `sources.json` podem ser atualizados
  para refletir os motores adicionados.

---

## 7. Boas Práticas

* **Nunca** modificar o `AnalysisRequest` ou o `AnalysisResult` para
  sím o motor.
* **Nunca** implementar o motor dentro dos endpoints.
* **Nunca** usar mocks de dados reais no motor.
* **Nunca** expor campos internos do motor nos endpoints sem um
  campo correspondente no contrato.
* **Nunca** assumir que o motor está disponível; verificar `EngineUnavailableError`.
* **Nunca** manter dois motores ativos simultaneamente no mesmo request.


## Scientific adapter integration (implemented, Etapa 1)

- Engine selectable via `SCIENTIFIC_ENGINE=scientific-lunaris` (default legacy: `geometric`).
- Ephemeris provider for scientific engine via `SCIENTIFIC_EPHEMERIS_PROVIDER=mock|horizons` (`mock` default, deterministic synthetic; `horizons` unavailable until validated vector/frame retrieval is implemented).
- Definitive `EngineResult` evaluated per UTC instant in `app/services/engine/scientific_adapter.py`; temporal aggregation (samples/summary/windows) remains in `AnalysisService` without silent sample drops.
- `AnalysisResult` includes additive optional scientific fields and aggregated `quality`.
- Limitations: `illumination`/`conditions`/`horizon` not computed in this stage (no invented values); `inertial`/`ecliptic` and `planetographic` and terrain modes rejected with controlled errors.
- Real Horizons vector provider activation requires validated Cartesian vectors, units, origin and body-fixed frame/transformations (see `docs/scientific/IMPLEMENTATION_STATUS.md`).
