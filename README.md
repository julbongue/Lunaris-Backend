# LUNARIS Backend

Backend da plataforma **LUNARIS**, desenvolvido para o desafio **NASA Space Apps 2026 — Lunar Landing Site Navigator**.

O objectivo do MVP é permitir comparar locais e datas de aterragem na Lua, sobretudo na região do polo sul, usando dados reais de efemérides e camadas cartográficas públicas.

> **Princípio do projecto:** não são inventados dados científicos. Quando uma integração ou um modelo ainda não existe, a API devolve uma limitação explícita em vez de um valor simulado.

## Estado para execução local + Cloudflare Tunnel

- **Framework:** FastAPI (`app.main:app`)
- **Servidor ASGI:** Uvicorn
- **Prefixo real da API:** `/api/v1` (configurável por `API_V1_PREFIX`)
- **Porta padrão:** `8000` (`PORT`)
- **Host padrão:** `0.0.0.0` (`HOST`)
- **Base de dados PostgreSQL:** **não utilizada** por este backend (não há dependência/configuração/integração no código actual)
- **Redis:** **não utilizado** por este backend (cache e store são em memória, com TTL configurável)
- **Motor científico:** seleccionável por `SCIENTIFIC_ENGINE` (`geometric` por defeito; `scientific-lunaris` disponível conforme configuração/provider). O arranque da API não depende de PostgreSQL/Redis; para `scientific-lunaris` com provider `spice` são necessários `spiceypy` e kernels NAIF validados (não incluídos).

## Arquitectura

```text
app/
├── api/                     # rotas FastAPI e dependências
├── core/                    # configuração, cache, excepções
├── data/                    # dados locais curados (sites, layers, sources)
├── integrations/            # clientes externos (Horizons, LROC, Moon Trek)
├── schemas/                 # contratos Pydantic
├── services/                # domínio, orquestração, motores
└── main.py                  # aplicação FastAPI, CORS, logging, startup/shutdown
scripts/                     # arranque, health check, túnel, paragem
cloudflared/                 # exemplo de configuração Named Tunnel (sem segredos)
docs/                        # documentação técnica e operacional
```

A separação é intencional:

- **API** valida pedidos e devolve esquemas estáveis.
- **Services** orquestram o domínio e as regras do MVP.
- **Integrations** isolam o acesso a fontes externas.
- **Engine** é a fronteira reservada para o motor científico completo.

## Requisitos

- Ubuntu/Linux com Python 3.12+
- `pip` e `venv`
- `curl` (recomendado para scripts de verificação)
- `cloudflared` apenas se for expor a API via Cloudflare Tunnel
- Rede de saída para integrações externas quando usadas (ex.: JPL Horizons, LROC, Moon Trek)

## Instalação

```bash
cd /home/jbongue/Documentos/Lunaris-Backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

> Se já existir uma pasta `.env/` (por exemplo, uma virtualenv criada com esse nome), renomeie-a para `.venv/` ou use variáveis de ambiente. A aplicação só carrega `.env` quando este for um ficheiro regular.

## Configuração de ambiente

Edite `.env` conforme o ambiente. Variáveis principais:

| Variável | Descrição | Exemplo/padrão |
| --- | --- | --- |
| `HOST` | Host de escuta do Uvicorn | `0.0.0.0` |
| `PORT` | Porta de escuta do Uvicorn | `8000` |
| `DEBUG` | Modo debug (não recomendado publicamente) | `false` |
| `API_V1_PREFIX` | Prefixo da API | `/api/v1` |
| `LOG_LEVEL` | Nível de log (`DEBUG`, `INFO`, `WARNING`, ...) | `INFO` |
| `CORS_ORIGINS` | Origens permitidas (CSV ou JSON array) | `https://app.vercel.app,http://localhost:3000` |
| `SCIENTIFIC_ENGINE` | Motor científico (`geometric`, `scientific-lunaris`, ...) | `geometric` |
| `SCIENTIFIC_EPHEMERIS_PROVIDER` | Provider do motor científico | `mock` |
| `MAX_REQUEST_BODY_BYTES` | Limite de tamanho do body (defesa básica) | `1000000` |
| `RATE_LIMIT_*` | Rate limiting em memória (defesa básica) | ver `.env.example` |
| `TRUST_PROXY_HEADERS` | Confiar em `X-Forwarded-For` (apenas atrás de proxy/túnel confiável) | `false` |

### CORS (Vercel + local)

Exemplo:

```env
CORS_ORIGINS=https://meu-frontend.vercel.app,http://localhost:3000,http://localhost:5173
```

Regras implementadas:

- Aceita lista separada por vírgulas **ou** JSON array.
- Não permite wildcard `*`.
- `allow_credentials=false`.
- Métodos explícitos permitidos: `GET, POST, PUT, PATCH, DELETE, OPTIONS`.
- Headers permitidos via CORS: `*` (adequado para preflight típico de `Content-Type`, `Authorization`, etc.).

## Arranque local

### Opção A — Uvicorn directo

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info
```

### Opção B — Script de arranque

```bash
./scripts/start_backend.sh
```

O script:

- carrega `.env` (se existir);
- verifica dependências Python essenciais (`fastapi`, `uvicorn`, `pydantic-settings`, `httpx`);
- inicia em background;
- aguarda e verifica `GET /api/v1/health`;
- falha com erro claro se o processo não iniciar ou o health check não responder.

Logs/PID padrão: `.lunaris-backend.log`, `.lunaris-backend.pid`.

## Verificação da API

### Script

```bash
./scripts/check_health.sh
# ou contra URL pública/túnel:
BASE_URL=https://<seu-host> ./scripts/check_health.sh
```

### Comandos manuais

```bash
curl -fsS http://127.0.0.1:8000/
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/capabilities
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>

## Configuração de PostgreSQL, Redis e motor científico

### PostgreSQL e Redis

- **Estado actual:** não requeridos/não integrados neste backend.
- **Não expor:** se forem adicionados no futuro ao ambiente local, mantenha-os em `localhost`/rede privada e **nunca** os encaminhe pelo Cloudflare Tunnel.
- **Dados locais usados:** ficheiros JSON em `app/data/` (sites, topography layers, sources).

### Motor científico

- **Padrão:** `SCIENTIFIC_ENGINE=geometric` (baseline do MVP, sem dependências científicas adicionais).
- **Alternativo:** `SCIENTIFIC_ENGINE=scientific-lunaris` com `SCIENTIFIC_EPHEMERIS_PROVIDER=mock|horizons-observer|spice|horizons-vectors` conforme disponibilidade/configuração.
- **SPICE:** requer `spiceypy` e kernels NAIF válidos (`SPICE_KERNEL_PATHS`); não são incluídos nem validados automaticamente por este repositório.
- A API preserva contratos e limitações explícitas quando capacidades não estão disponíveis.

## Exposição via Cloudflare Tunnel

Documentação detalhada: [`docs/cloudflare-tunnel.md`](docs/cloudflare-tunnel.md)  
Exemplo de Named Tunnel: [`cloudflared/config.example.yml`](cloudflared/config.example.yml)

### Desenvolvimento rápido (Quick Tunnel)

```bash
./scripts/start_backend.sh
cloudflared tunnel --url http://localhost:8000
# ou: ./scripts/start_tunnel.sh quick
```

- URL pública temporária (`*.trycloudflare.com`) muda a cada execução.
- Útil para testes; **não** é configuração persistente de produção.

### Configuração persistente (Named Tunnel)

> **Acção manual necessária (não automatizável por este repositório):** autenticação na sua conta Cloudflare, criação do túnel, associação DNS/domínio e gestão de credenciais.

Comandos exactos (substitua placeholders):

```bash
cloudflared tunnel login
cloudflared tunnel create lunaris-backend
cloudflared tunnel route dns lunaris-backend api.example.com
cp cloudflared/config.example.yml cloudflared/config.yml
# editar cloudflared/config.yml com <TUNNEL_UUID>, credentials-file e hostname
./scripts/start_backend.sh
./scripts/start_tunnel.sh named
# ou: cloudflared tunnel --config cloudflared/config.yml run
```

Teste público:

```bash
curl https://api.example.com/api/v1/health
```

## Endpoints principais

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/` | Entrada da API |
| `GET` | `/api/v1/health` | Estado do serviço e motor activo (verifica carregamento de dados locais) |
| `GET` | `/api/v1/capabilities` | Capacidades/configuração reportada |
| `GET` | `/api/v1/sites` | Lista de locais curados |
| `GET` | `/api/v1/sites/{site_id}` | Detalhes de um local |
| `POST` | `/api/v1/sites/resolve` | Normaliza coordenadas lunares personalizadas |
| `POST` | `/api/v1/analysis` | Analisa um local e intervalo temporal |
| `GET` | `/api/v1/analysis/{analysis_id}` | Recupera uma análise em cache (TTL) |
| `POST` | `/api/v1/scenarios/compare` | Compara cenários |
| `GET` | `/api/v1/topography/layers` | Catálogo de camadas WMS/WMTS |
| `POST` | `/api/v1/topography/context` | Contexto/URLs de mapa para um local |
| `GET` | `/api/v1/sources` | Fontes externas e estado de integração |

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

## Segurança para exposição pública

Medidas implementadas/configuráveis:

- CORS restrito a origens explicitamente configuradas (sem wildcard, sem credenciais).
- Validação de inputs via Pydantic/FastAPI nos contratos existentes.
- Limite de tamanho de body por `Content-Length` (`MAX_REQUEST_BODY_BYTES`, defesa básica).
- Rate limiting em memória por IP (`RATE_LIMIT_*`, defesa básica; reforçar no proxy/Cloudflare se necessário).
- Em `DEBUG=false`, erros não tratados devolvem mensagem genérica sem stack trace.
- Não exposição de variáveis de ambiente/segredos por endpoints.
- Timeouts configuráveis para integrações externas (ex.: JPL Horizons).
- Endpoints e contratos existentes preservados; não desactivar autenticação existente (nenhuma autenticação específica foi removida/introduzida fora do existente).

> **Nota:** o backend expõe apenas HTTP na porta configurada; PostgreSQL/Redis não fazem parte deste serviço e não devem ser expostos.

## Testes e qualidade

```bash
source .venv/bin/activate
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Os testes de API usam clientes/fakes determinísticos quando aplicável; não introduza mocks na execução de produção.

## Resolução de problemas

- **`ModuleNotFoundError`/dependências em falta:** instale `requirements-dev.txt` no venv activo.
- **Porta em uso:** altere `PORT` ou termine o processo que usa a porta.
- **Health falha no arranque:** verifique logs (`.lunaris-backend.log`), integridade de `app/data/*.json` e configuração de `SCIENTIFIC_ENGINE`/providers.
- **Erro CORS no browser:** confirme origem exacta em `CORS_ORIGINS` e reinicie o backend.
- **`cloudflared` não encontrado:** instale o binário oficial; o script `start_tunnel.sh` falha com instrução.
- **Quick Tunnel não dá URL estável:** comportamento esperado; use Named Tunnel.
- **429 / 413:** ajuste limites apenas se seguro (`RATE_LIMIT_*`, `MAX_REQUEST_BODY_BYTES`) e considere protecções adicionais no Cloudflare.
- **Falhas ao consultar Horizons:** dependência externa/latência/rede; valide `HORIZONS_*` e conectividade.

## Encerramento controlado

```bash
./scripts/stop_backend.sh          # pára túnel (se iniciado por script) e backend
./scripts/stop_backend.sh backend  # apenas backend
./scripts/stop_backend.sh tunnel   # apenas túnel
```

## Documentação adicional

- [`docs/cloudflare-tunnel.md`](docs/cloudflare-tunnel.md) — exposição via Cloudflare Tunnel
- [`docs/frontend/contract.md`](docs/frontend/contract.md) — contrato frontend
- [`docs/engine/*`](docs/engine) — motor e contratos
- [`docs/scientific/IMPLEMENTATION_STATUS.md`](docs/scientific/IMPLEMENTATION_STATUS.md) — estado científico
- `GET /docs` e `GET /openapi.json` — documentação interactiva da API em execução

## Estrutura de resposta de erro

```json
{
  "error": {
    "code": "bad_request",
    "message": "Mensagem de erro",
    "details": {}
  }
}
```