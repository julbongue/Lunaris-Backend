# LUNARIS — Contrato Definitivo do Motor Científico

Documento que define o contrato de interface para a implementação do motor
científico do LUNARIS. O contrato é a base para que outra pessoa possa
desenvolver o motor sem precisar de alterar os endpoints da API.

---

## 1. Propósito e escopo

Este documento define:

* as entradas e saídas do motor científico;
* as unidades físicas e as convenções de coordenadas;
* as estruturas Pydantic (`app/schemas/engine.py`);
* a interface Python (`ScientificEngine` protocol);
* as exceções específicas;
* as validações aplicáveis;
* exemplos de entrada e saída.

O contrato é dividido em duas partes:

1. **Contrato definitivo** — usado por qualquer motor novo (`ScientificEngine`
   protocol + `EngineInput`/`EngineResult` Pydantic).  Este é o contrato que
   o time de desenvolvimento do motor implementa.
2. **Interface legada** — os tipos `EngineInput` / `EngineOutput`
   (dataclasses) que o motor geométrico atual implementa.  A interface
   legada é mantida para retrocompatibilidade com o MVP.

---

## 2. Princípios de Design

* **Sem ambiguidade de unidades e funções.**  Todos os ângulos são
  expressos em graus, exceto quando explicitamente indicado.  Radianos
  nunca virão como entrada de um motor.
* **Sem ambiguidade de coordenadas.**  A latitude é sempre no intervalo
  [-90, +90] graus.  A longitude é sempre **east-positive** (leste =
  positivo), no intervalo [-180, +180] ou normalizada para [0, 360).
* **Retenção da retrocompatibilidade.**  O motor geométrico existente
  continua a usar a interface legada.  O novo motor deve implementar o
  contrato definitivo.
* **Claridade de origem e precisão.**  A cada resultado o motor deve
  declarar a origem dos dados e, sempre que possível, a precisão.

---

## 3. Tipos de Dados e Unidades

### 3.1 Ângulos

| Quantidade | Unidade | Intervalo | Notas |
|---|---|---|---|
| latitude | graus (deg) | [-90, +90] | positivo para norte |
| longitude | graus (deg) | [-180, +180] ou [0, 360) | east-positive |
| azimuth | graus (deg) | [0, 360) | horário a partir do norte |
| elevation (altitude angular) | graus (deg) | [-90, +90] | acima do horizonte positivo |
| phase angle | graus (deg) | [0, 180] | ângulo Sol-Observador-Ponto de superfície |
| incidence | graus (deg) | [0, 90] | ângulo entre a normal da superfície e o Sol |
| emission | graus (deg) | [0, 90] | ângulo entre a normal da superfície e o observador |
| solar longitude | graus (deg) | [0, 360) | azimute do Sol visto pelo observador |
| horizon obstruction | graus (deg) | [-90, +90] | depressão máxima do terreno em relação ao horizonte geométrico |

### 3.2 Distâncias

| Quantidade | Unidade |
|---|---|
| altitude do observador | metros (m) |
| alcance topocêntrico | quilómetros (km) |

### 3.3 Tempo

* Todos os instantes são UTC.
* O intervalo de observação é `[start_time, stop_time)` (start inclusive,
  stop exclusive).
* O passo de amostragem é `step_minutes`, em minutos, [1, 1440].

### 3.4 Sistemas de coordenadas

| Sistema | Descrição |
|---|---|
| **planetocentric** | latitude medida a partir do plano do equador, positivo para norte.  O padrão do JPL Horizons. |
| **planetographic** | latitude medida a partir do plano do equador, definida para um elipsóide rotador; usada por alguns datum lunar. |
| **selenographic** | nomenclatura convencional lunar, mesmos eixos que planetocentric; manter para compatibilidade com literatura lunar. |
| **inertial** | referencial não-rotativo (ICRF / J2000). |
| **selenographic** | referencial lunar, fixo à superfície (o referencial de rotação). |
| **ecliptic** | referencial do eclíptica de data. |

Notas sobre latitude planetocêntrica vs planetográfica:

* A **latitude planetocêntrica** é o ângulo entre o plano do equador e a
  reta que liga o centro lunal ao observador.  É o que o JPL Horizons
  utiliza nas tabelas OBSERVER com `COORD_TYPE='GEODETIC'`.
* A **latitude planetográfica** é definida sobre o elipsóide de referência
  (para a Lua, o datum WGS-84 / lunar GCS).  Nenhum dos dois é "correcto"
  em si; correspondem a diferentes modelos de superfície.  O contrato
  exige que a convenção seja declarada explicitamente no payload.

### 3.5 Referenciais

* O referencial **selenográfico** é fixo à superfície da Lua (o referencial
  de rotação).  É o referencial no qual os azimutes de JPL Horizons são
  normalmente expressos (opressão "topocentric", azimute medido a partir do
  norte local).
* O referencial **inertial** é o ICRF/J2000.  Transformações entre este e o
  selenográfico envolvem a rotação lunear (inclinação do eixo, precessão
  e libração).
* O referencial **ecliptic** é o eclíptica de data.

Para o MVP, o motor deve:

1. receber coordenadas em `planetocentric` (graus, east-positive) e o tempo
   UTC;
2. usar o JPL Horizons (ou outro gerador de epêmero) para obter o vector
   topocêntrico do corpo;
3. expressar o resultado no referencial `selenographic` (e/ou inertial, se
   pedido).

---

## 4. Interface Python

### 4.1 Contrato definitivo

```python
from typing import Protocol
from app.schemas.engine import EngineInput, EngineResult

class ScientificEngine(Protocol):
    """Interface definitiva para motores científicos do LUNARIS.

    Qualquer motor que queira ser utilizado pela API deve implementar
    este protocolo.  O método ``analyze`` recebe um ``EngineInput``
    definitivo e devolve um ``EngineResult``.
    """
    name: str
    version: str

    def analyze(self, data: EngineInput) -> EngineResult: ...
```

### 4.2 Interface legada (retrocompatibilidade)

```python
class ScientificEngine(Protocol):
    name: str
    version: str
    def analyze(self, data: EngineInput) -> EngineOutput: ...
```

* `EngineInput` legada: dataclass com `points`, `thresholds`, `range_start`,
  `range_end`, `step_minutes`.
* `EngineOutput` legada: dataclass com `summary`, `solar_windows`,
  `communication_windows`, `model`.

O motor legado `GeometricEngine` implementa esta interface.  O novo motor
deve implementar o contrato definitivo (4.1).

### 4.3 Registro e injeção

O registo de motores (`app/services/engine/registry.py`) é um dicionário
`name -> engine`.  O motor activo é seleccionado através da configuração
`SCIENTIFIC_ENGINE`.  A implementação do motor novo pode ser:

* registada no registo com um nome (ex.: `lola-terrain` ou `spice`),
* seleccionada via `SCIENTIFIC_ENGINE=lola-terrain`,
* injetada via override de dependência no layer API.

Nenhum endpoint da API tem de ser alterado para aceitar um motor novo.

---

## 5. Exceções

O motor deve levantar exceções que sejam processadas pela camada de API.
As exceções já existentes no app são:

| Exceção | Código HTTP | Uso |
|---|---|---|
| `BadRequestError` | 400 | entrada inválida (ex.: janela de tempo inválida) |
| `NotFoundError` | 404 | recurso mal formado |
| `UpstreamServiceError` | 502 | erro de serviço externo (ex.: JPL Horizons) |
| `UpstreamTimeoutError` | 504 | timeout num serviço externo |
| `EngineUnavailableError` | 501 | motor pedido não disponível |

O motor deve levantar estas exceções (ou subclasses), nunca um erro
genérico.

Exemplo:

```python
from app.core.exceptions import BadRequestError

class BadEngineInputError(BadRequestError):
    code = "bad_engine_input"
```

---

## 6. Validações

As validações são implementadas nos schemas Pydantic (`app/schemas/engine.py`)
e na camada de serviço.

* `latitude_deg`: [-90, 90].
* `longitude_deg`: [-180, 180] (normalizado para [0, 360) pelo chamador).
* `altitude_m`: >= 0.
* `start_time` / `stop_time`: `stop_time` > `start_time`, ambos UTC.
* `step_minutes`: [1, 1440].
* `sun_elevation_deg`, `earth_elevation_deg`: [-90, 90].
* `coordinate_system`: uma das literal values.
* `reference_frame`: uma das literal values.
* `terrain_availability`: uma das literal values.
* `horizon_reference`: uma das literal values.
* Parâmetros adicionais verificados pelo motor (ex.: o motor que utiliza
  terreno deve verificar que `terrain_availability != "none"`).

---

## 7. Exemplo de entrada e saída

### 7.1 Entrada

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

### 7.2 Saída (esquema)

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

---

## 8. Relação com a API existente

O endpoint `/api/v1/analysis` (e `scenarios/compare`) recebe atualmente
um `AnalysisRequest` (Pydantic), resolve o site e chama o motor através da
interface legada.  Para usar o motor novo:

1. O endpoint deve converter o `AnalysisRequest` em um `EngineInput`
   definitivo (o motor pode consumir coordenadas, tempo, thresholds e
   convenções).
2. O resultado do motor definitivo (`EngineResult`) deve ser convertido
   em um `AnalysisResult` para responder (ou o novo motor produz diretamente
   `AnalysisResult`).
3. A conversão deve ser feita numa camada de adaptação (ex.: em
   `app/services/analysis.py`), nunca nos endpoints.

Isto mantém o frontend intacto: o contrato científico é aplicado no backend.

---

## 9. Referências

* JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
* LOLA: https://pds-geosciences.wustl.edu/missions/lro/lola.htm
* SLDEM2015: https://imbrium.mit.edu/BROWSE/SLDEM2015/TILES/
* GLD100: https://astrogeology.usgs.gov/...
* Forma convencional de coordenadas lunares: Archinal et al., "Report of
  the IAU Working Group on Cartographic Coordinates and Rotational Elements",
  2018.
