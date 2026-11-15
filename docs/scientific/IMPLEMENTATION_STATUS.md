# Scientific Engine Integration — Implementation Status

## Estado final
**PARCIALMENTE CONCLUÍDO** (motor científico integrado e operacional com efemérides **mock** e com provider **Horizons observer** baseado em dados reais da NASA JPL Horizons Az/El; SPICE/DEM topográfico real permanecem dependentes de ambiente, kernels e datasets não validados nesta sessão).

## Arquitetura implementada
- **Contrato definitivo por instante:** `app/schemas/engine.py` (`EngineResult`) é avaliado **por instante UTC** no adaptador científico; cada instante é associado ao seu `timestamp` em `InstantResult` e nos `samples` agregados. Não há descarte silencioso de instantes (falha explícita se cobertura incompleta).
- **Agregação temporal no serviço/camada de análise:** `AnalysisService` preserva o fluxo `AnalysisRequest -> AnalysisResult -> API`. Para o motor científico, obtém resultados por instante via `ScientificAdapter.analyze_request(...)` e agrega `summary`, `solar_windows`, `communication_windows` e `samples` (compatível com contrato legado/frontend). Campos científicos opcionais representativos (último instante) e `quality` agregado são anexados ao `AnalysisResult` (extensão aditiva).
- **Núcleo científico reutilizado:** `app/services/engine/lunaris_scientific/` (cópia integrada do núcleo geométrico: vetores, coordenadas, frames, visibilidade, iluminação geométrica, topografia/temporal como base).
- **Abstrações:**
  - `app/services/engine/ephemeris_provider.py`: `EphemerisProvider` (Protocol), `InstantEphemeris`, `CoordinateTransformer` (Protocol), `NoopCoordinateTransformer`, `MockDeterministicEphemerisProvider` (ativo), `HorizonsVectorEphemerisProvider` (indisponível por validação pendente).
- **Adaptador:** `app/services/engine/scientific_adapter.py` (`ScientificAdapter`, `name=scientific-lunaris`): valida convenções, obtém efemérides por instante, calcula visibilidade Terra/Sol e coordenadas topocêntricas via `lunaris_scientific`, constrói `EngineResult` por instante e `DataQualityMetadata` agregado, traduz validações para `BadRequestError` com códigos.
- **DI/Registry/Config:** `app/services/engine/registry.py`, `app/api/deps.py`, `app/core/config.py` (`scientific_engine`, `scientific_ephemeris_provider=mock|horizons`), `app/services/engine/__init__.py`.
- **Schemas aditivos:** `app/schemas/analysis.py` aceita `coordinate_system`, `reference_frame`, `terrain_availability`, `horizon_reference` em `AnalysisRequest` e campos científicos opcionais + `quality` em `AnalysisResult`.

## Ficheiros criados
- `app/services/engine/lunaris_scientific/*` (núcleo integrado)
- `app/services/engine/ephemeris_provider.py`
- `app/services/engine/scientific_adapter.py`
- `docs/scientific/IMPLEMENTATION_STATUS.md`
- `tests/test_scientific_adapter.py`
- `tests/test_scientific_integration.py`

## Ficheiros alterados (localizados)
- `app/schemas/analysis.py` (campos aditivos opcionais)
- `app/services/analysis.py` (suporte a motor científico + agregação/preservação de fluxo)
- `app/services/engine/registry.py`, `app/services/engine/__init__.py`
- `app/api/deps.py`
- `app/core/config.py`

## Como selecionar o motor científico
- **Legacy (padrão, sem regressões):** `SCIENTIFIC_ENGINE=geometric`
- **Científico (mock determinístico):** `SCIENTIFIC_ENGINE=scientific-lunaris` e `SCIENTIFIC_EPHEMERIS_PROVIDER=mock` (padrão)
- **Horizons observer (real):** `SCIENTIFIC_EPHEMERIS_PROVIDER=horizons` ou `horizons-observer` usa NASA JPL Horizons OBSERVER Az/El (topocêntrico lunar). Distâncias podem usar aproximações médias quando range explícito não é parseado; proveniência registada em `quality`.
- **SPICE:** `SCIENTIFIC_EPHEMERIS_PROVIDER=spice` com `SPICE_KERNEL_PATHS` requer `spiceypy` e kernels NAIF validados (não disponíveis/validados neste ambiente).
- **Vetorial cartesiano validado:** `horizons-vectors` indisponível sem transformação/orientação lunar validada.

## Como executar os testes
```bash
cd /home/jbongue/Documentos/Lunaris-Backend
python3 -m pytest -q
# específicos
python3 -m pytest -q tests/test_scientific_adapter.py tests/test_scientific_integration.py
```

## Funcionalidades efetivamente disponíveis
- Avaliação geométrica por instante (Terra/Sol): visibilidade, elevação, azimute, distância (`range_km`) via vetores body-fixed injetados.
- Agregação temporal (resumo, janelas solares/comunicação, amostras) compatível com API existente.
- `DataQualityMetadata` agregado e proveniência (mock/real conforme provider).
- Validações e erros controlados: `planetographic` rejeitado (Etapa 1), `inertial`/`ecliptic` rejeitados sem transformação validada, terreno/topografia não suportada rejeitada, falhas de cobertura de instantes explícitas.
- Integração DI/registry/config e preservação do motor legado.

## Campos científicos não calculados (Etapa 1, sem invenção)
- `illumination` (`IlluminationAngles`): `None`
- `conditions` (`IlluminationConditions`): `None`
- `horizon` (`HorizonObstruction`): `None` sem DEM/topografia
- Sem modelo de insolação, terminador rigoroso, fase/emissão/solar_longitude completos, sem DEM/LOLA.

## O que funciona com dados reais vs mocks
- **Mocks determinísticos:** totalmente funcional para testes/integração offline (fonte rotulada `mock`, sintética).
- **Horizons observer (real):** disponível e integrado para direções topocêntricas reais (Az/El) via JPL Horizons, com mapeamento para o frame de análise e limitações de distância/frame documentadas.
- **SPICE/LOLA real:** não validados/executáveis neste ambiente (faltam `spiceypy`, kernels NAIF e datasets DEM).

## Como ativar o provider real (quando validado)
1. Implementar recuperação de vetores/estados Horizons (ou SPICE) com quantidade/formato adequado e metadados explícitos (frame, época, unidades, origem centro/topocêntrico).
2. Validar correspondência com `lunaris_scientific` (body-fixed selenográfico) ou implementar `CoordinateTransformer` real e rastreável (librações/orientação temporal) — sem rotações fictícias.
3. Atualizar `HorizonsVectorEphemerisProvider.get_instants` para devolver `InstantEphemeris` validados e registar proveniência real em `elevation_source/source`.
4. Adicionar testes de paridade com fontes de referência (Horizons/SPICE) e ativar `SCIENTIFIC_EPHEMERIS_PROVIDER=horizons`.
5. Rever políticas de `reference_frame` suportados conforme transformações disponíveis.

## Bloqueios restantes (dependências externas/decisões científicas)
- Obtenção validada de vetores efemérides Terra/Sol em frame compatível (Horizons vetorial ou SPICE/kernels).
- Transformações `inertial/ecliptic -> body-fixed` tempo-dependentes com dados de orientação lunar validados.
- Suporte `planetographic` (se requerido).
- Modelo completo de iluminação/condições e integração DEM/topográfica (LOLA) para `horizon`.

## Notas de proveniência e limitações
- `DataQualityMetadata` é preenchido com `engine_name/version`, `coordinate_system`, `reference_frame`, `elevation_source`, `temporal_extent` e notas de limitações.
- Altitude 0 m assumida quando não fornecida; ausência de terreno explicitada; sem invenção de precisão/cobertura/kernels.
