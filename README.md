# LUNARIS Backend

Backend da plataforma **LUNARIS**, desenvolvido para o desafio **NASA Space Apps 2026 — Lunar Landing Site Navigator**.

O objectivo do MVP é permitir comparar locais e datas de aterragem na Lua, sobretudo na região do polo sul, usando dados reais de efemérides e camadas cartográficas públicas.

> **Princípio do projecto:** não são inventados dados científicos. Quando uma integração ou um modelo ainda não existe, a API devolve uma limitação explícita em vez de um valor simulado.

## Arquitectura

```text
app/
├── api/
│   ├── deps.py                  # injecção de dependências FastAPI
│   └── v1/
│       ├── router.py
│       └── endpoints/
│           ├── health.py
│           ├── sites.py         # locais curados + coordenadas personalizadas
│           ├── analysis.py      # análise de iluminação/visibilidade
│           ├── scenarios.py     # comparação de cenários
│           ├── topography.py    # catálogo de camadas cartográficas
│           └── sources.py       # estado das fontes externas
├── core/
│   ├── cache.py                 # cache TTL em memória
│   ├── config.py                # pydantic-settings
│   └── exceptions.py            # erros de domínio -> respostas HTTP
├── data/
│   ├── sites.json               # locais lunares curados
│   ├── topography_layers.json   # camadas WMS/WMTS verificadas
│   └── sources.json             # fontes e estado de integração
├── integrations/
│   ├── horizons/                # cliente + parser do JPL Horizons
│   ├── lroc/                    # construtor de URLs do WMS LROC/Lunaserv
│   └── moontrek/                # construtor de URLs do WMTS Moon Trek
├── schemas/                     # modelos Pydantic de entrada/saída
├── services/
│   ├── engine/                  # interface do motor científico + baseline
│   ├── sites.py
│   ├── ephemeris.py
│   ├── analysis.py
│   ├── analysis_store.py
│   ├── comparison.py
│   ├── topography.py
│   └── sources.py
└── main.py
```

A separação é intencional:

- **API** valida pedidos e devolve esquemas estáveis.
- **Services** orquestram o domínio e as regras do MVP.
- **Integrations** isolam o acesso a fontes externas.
- **Engine** é a fronteira reservada para o motor científico completo.

## Requisitos

- Python 3.12+
- pip e venv

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

> Se já existir uma pasta `.env/` (por exemplo, uma virtualenv criada com esse nome), renomeie-a para `.venv/` ou use variáveis de ambiente. A aplicação só carrega `.env` quando este for um ficheiro regular.

## Executar

```bash
uvicorn app.main:app --reload
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

## Endpoints principais

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Estado do serviço e motor activo. |
| `GET` | `/api/v1/sites` | Lista de locais curados. Parâmetros: `region`, `south_polar_only`. |
| `GET` | `/api/v1/sites/{site_id}` | Detalhes de um local. |
| `POST` | `/api/v1/sites/resolve` | Normaliza coordenadas lunares personalizadas (não persiste). |
| `POST` | `/api/v1/analysis` | Analisa um local e intervalo temporal. |
| `GET` | `/api/v1/analysis/{analysis_id}` | Recupera uma análise em cache (TTL). |
| `POST` | `/api/v1/scenarios/compare` | Compara 2..6 cenários (`MAX_COMPARISON_SCENARIOS`). |
| `GET` | `/api/v1/topography/layers` | Catálogo de camadas WMS/WMTS verificadas. |
| `POST` | `/api/v1/topography/context` | URLs de mapa e contexto topográfico para um local. |
| `GET` | `/api/v1/sources` | Fontes externas e estado de integração. |

### Exemplo: análise

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis \
  -H 'Content-Type: application/json' \
  -d '{
    "site": {"type": "known", "site_id": "shackleton-rim"},
    "start_time": "2026-11-15T00:00:00Z",
    "stop_time": "2026-11-17T00:00:00Z",
    "step_minutes": 60,
    "thresholds": {"sun_elevation_deg": 0.0, "earth_elevation_deg": 5.0},
    "include_samples": true
  }'
```

### Exemplo: coordenadas personalizadas

```json
{
  "site": {
    "type": "coordinates",
    "name": "Meu local polar",
    "latitude_deg": -88.5,
    "longitude_deg": 15.0,
    "elevation_m": 500.0
  },
  "start_time": "2026-11-15T00:00:00Z",
  "stop_time": "2026-11-16T00:00:00Z",
  "step_minutes": 60
}
```

`longitude_deg` é **east-positive** no intervalo `[-180, 180]`. A resposta inclui também `longitude_east_deg` no intervalo `[0, 360)`, que é a convenção usada pelo JPL Horizons.

## Fontes externas e integração real

| Fonte | Acesso programático | Estado no MVP |
| --- | --- | --- |
| **JPL Horizons** | REST API pública (`https://ssd.jpl.nasa.gov/api/horizons.api`) | **Integrado**. Tabelas `OBSERVER` com `QUANTITIES='4'` e `CENTER='coord@301'` para obter azimute/elevação topocêntricos do Sol e da Terra a partir de um local lunar. |
| **LROC QuickMap / Lunaserv** | OGC WMS público (`https://wms.im-ldi.com/lroc/wms`) | **Integrado como camadas de mapa**. Não existe API pública de análise pontual; as camadas DEM numéricas respondem `LayerNotQueryable` a `GetFeatureInfo`, pelo que a API não inventa elevações. |
| **NASA Moon Trek** | OGC WMTS + catálogo Trek REST | **Integrado como camadas de mapa**. Catálogo curado de camadas verificadas; os tiles são servidos por WMTS. |
| **CSA Moon Exploration** | Portal web | **Não integrado**. Não foi identificada API pública; é referência educativa. |
| **NAIF SPICE** | Kernels SPICE | **Planeado** para o motor científico completo. |
| **PDS Geosciences** | Arquivos PDS | **Planeado** para ingestão local de DEMs e modelos de horizonte. |

O endpoint `GET /api/v1/sources` devolve esta informação de forma estruturada.

## Modelo científico do MVP

O motor activo chama-se `geometric-altaz-threshold` e é deliberadamente simples:

1. O JPL Horizons devolve amostras de azimute/elevação do Sol e da Terra, vistas de um observador na superfície lunar.
2. Uma amostra é considerada iluminada se a elevação do Sol for `>= sun_elevation_deg`.
3. Uma amostra é considerada com ligação directa se a elevação da Terra for `>= earth_elevation_deg`.
4. As janelas são construídas a partir de amostras contíguas.

Limitações explícitas (também devolvidas em cada análise):

- não há modelo de horizonte topográfico nem ray tracing de sombras;
- não há modelo de potência, bateria, térmica ou link budget;
- as fronteiras das janelas são instantes amostrados, não tempos exactos de rise/set;
- a elevação do local é assumida como `0 km` quando não é fornecida;
- os resultados são preliminares e não servem para decisões críticas de missão.

### Substituir o motor científico

A interface está em `app/services/engine/base.py`:

```python
class ScientificEngine(Protocol):
    name: str
    version: str

    def analyze(self, data: EngineInput) -> EngineOutput: ...
```

Para adicionar o motor completo:

1. criar, por exemplo, `app/services/engine/spice.py`;
2. implementar `ScientificEngine`;
3. registar em `app/services/engine/registry.py`;
4. seleccionar com `SCIENTIFIC_ENGINE=spice`.

A API, os schemas e os endpoints não precisam de mudar.

## Dependências

### Instaladas

| Dependência | Justificação |
| --- | --- |
| `fastapi` | Framework da API e OpenAPI. |
| `uvicorn[standard]` | Servidor ASGI. |
| `pydantic` | Validação e serialização dos contratos da API. |
| `pydantic-settings` | Configuração por ambiente/`.env`. |
| `httpx` | Cliente HTTP assíncrono para o JPL Horizons. |
| `pytest` | Testes automatizados. |
| `ruff` | Lint e formatação. |

### Deliberadamente adiadas

| Dependência | Motivo |
| --- | --- |
| `spiceypy` | Só é necessária quando o motor SPICE for implementado. O JPL Horizons já fornece azimute/elevação suficientes para o MVP. |
| `astropy` | Não é necessária para consultar o Horizons nem para a baseline geométrica. |
| `numpy` / `scipy` | A baseline usa operações simples sobre listas. Interpolação e processamento científico pertencem ao motor futuro. |

Não instalar estas dependências sem uma necessidade concreta do motor científico.

## Dados locais

- `app/data/sites.json`: locais curados com coordenadas publicadas, fonte e precisão aproximada. As coordenadas não são apresentadas como “landing pads” certificados.
- `app/data/topography_layers.json`: camadas verificadas em 2026-11-14, com URLs de WMS/WMTS e notas de limitação.
- `app/data/sources.json`: inventário das fontes e do respectivo estado de integração.

Para adicionar um local, inclua uma entrada em `sites.json` com `id`, coordenadas, região, tipo, descrição e `source_url`.

## Testes e qualidade

```bash
pytest
ruff check .
ruff format --check .
```

Os testes de API usam um cliente Horizons falso e determinístico. Nenhum teste faz chamadas de rede.

## Estrutura de resposta de erro

```json
{
  "error": {
    "code": "upstream_error",
    "message": "JPL Horizons returned HTTP 503 for Sun.",
    "details": {"service": "JPL Horizons", "target": "Sun", "status_code": 503}
  }
}
```
