# Recomendação Técnica — Dataset DEM Lunar

Esta recomendação técnica identifica e compara as fontes de dados de
elevação lunar disponíveis, para permitir o cálculo das obstrução do
horizonte.  A recomendação é baseada em resolução, precisão, cobertura,
formato, acesso programático e facilidade de integração.

---

## 1. Fontes Evaluadas

### 1.1 LOLA — Lunar Orbiter Laser Altimeter

* **Instalação**: LRO (Lunar Reconnaissance Orbiter), instrumento NASA.
* **Fluxo de dados**: LOLA Science Team → LOLA Data Node → PDS Geosciences
  Node (WUSTL) → distribuição pública.
* **Resolução**: múltiplas resoluções disponíveis: 4, 16, 64, 128, 256,
  512 pixels/deg; e polar stereographic (240 p/deg até 5 m/px).
* **Precisão vertical**: ~1 m (horizontal) após correção de crossover.
* **Cobertura**: global (inclui polos).
* **Formato**: PDS3 (arquivos `.img` + `.lbl` ou `.xml`).
* **Acesso**: [Geosciences Node LOLA](http://pds-geosciences.wustl.edu/missions/lro/lola.htm)
  e [LOLA Data Node](http://imbrium.mit.edu/); o PDE (Lunar Orbital Data
  Explorer, [ODE](http://ode.rsl.wustl.edu/moon/)) permite pesquisar e
  descarregar produtos.
* **Licenciamento**: Domínio público (NASA).
* **Facilidade de integração com Python**: Alta.  O rótulo PDS3 é
  ler com `pvl`/`pds3`; o raster pode ser aberto com GDAL (`rasterio`).
* **Vantagens**: Precisão vertical alta, cobertura global e incluindo
  polos; base de dados de referência para o Lunar Geodetic
  Coordinate System (LGCS).
* **Limitações**: Dataset grande (global 64 ppd ~ várias GB); acessos
  via HTTP pesados; necessidade de parse de rótulo PDS3.

### 1.2 SLDEM2015 — Merged LOLA + Kaguya TC DEM

* **Instalação**: LOLA (NASA LRO) co-registado com os dados de TIR (Terrain
  Camera) do Kaguya (JAXA).
* **Fluxo de dados**: LOLA + Kaguya TC → merged → USGS Astrogeology.
* **Resolução**: 256 ppd (~118 m/px) e 512 ppd (~59 m/px).
* **Precisão vertical**: ~3 a 4 m (acurácia, típica).
* **Cobertura**: ±60° de latitude (cobertura polar limitada, **não** cobre
  a região polar com -89.9°).
* **Formato**: PDS3 (`.img/.lbl` ou `.xml`), GDAL/ISIS3-compatible.
* **Acesso**: [SLDEM2015 Tiles (MIT)](https://imbrium.mit.edu/BROWSE/SLDEM2015/TILES/)
  e [USGS Astrogeology](https://astrogeology.usgs.gov/).
* **Licenciamento**: Domínio público (NASA/USGS/USAF).
* **Facilidade de integração**: Boa.  Arquivos PDS3, lidos com GDAL.
* **Vantagens**: Acurácia vertical alta, sem interpolação, boa cobertura
  ±60°.
* **Limitações**: Não cobre polos; dimensões grandes; acesso via HTTP
  pesado.

### 1.3 GLD100 — Global Lunar DTM 100 m (LROC WAC Stereo)

* **Instalação**: LROC (Lunar Reconnaissance Orbiter Camera) — dados de
  estereoa imagem WAC.
* **Resolução**: ~100 m/px (79°S a 79°N).
* **Precisão vertical**: média relativa ~18 m (1 sigma) (acurácia ruim
  comparada com LOLA).
* **Cobertura**: 79°S a 79°N (inclui polar com -89.9°).
* **Formato**: PDS3 (`.img/.lbl`) ou TIFF (mapa planetary).
* **Acesso**: [USGS Astrogeology GLD100](https://astrogeology.usgs.gov/search/map/moon_lroc_wac_dtm_gld100_118m).
* **Licenciamento**: Domínio público (USGS).
* **Facilidade de integração**: Boa (raster TIFF/PDS3).
* **Vantagens**: Cobertura global até 79°S, fácil de ler, é o "raster
  de visualização" usado no LROC QuickMap.
* **Limitações**: Menor precisão vertical (~18 m), baseada em estereoa
  (não em laser altimetry); geodynamically menos precisa que LOLA.

---

## 2. Comparação das Fontes

| Critério | LOLA GDR | SLDEM2015 | GLD100 |
|---|---|---|---|
| Resolução | 64 ppd (~118 m) a 512 ppd (~3.4 m) | 512 ppd (~59 m) | ~100 m |
| Precisão vertical | ~1 m | ~3-4 m | ~18 m |
| Cobertura | Global (inclui polos) | ±60° lat | 79°S-79°N |
| Formato | PDS3 (.img/.lbl) | PDS3 (.img/.lbl) | PDS3 / TIFF |
| Peças de acesso | PDS Geosciences Node / LOLA Data Node | MIT SLDEM node | USGS Astrogeology |
| Licença | Domínio público | Domínio público | Domínio público |
| Leitura Python | Boa (pvl + rasterio) | Boa (rasterio) | Boa (rasterio) |
| Tamanho (global 64 ppd) | ~10 GB | ~22 GB (full) | ~10 GB |
| Notas | Fonte de referência | Boa precisão, cobertura limitada | Boa resolução e cobertura |

---

## 3. Recomendação

### Recomendação Principal: **LOLA GDR (64 ppd, ~118 m/px)**

Para o MVP e para a integração do motor científico, recomenda-se:

* **Fonte primária**: LOLA GDR, resolução 64 ppd (118 m/px), cobertura
  global.
* **Porquê**:
  * Precisão vertical ~1 m — equipara ao desejo de cálculo de obstrução
    de horizonte.
  * Cobertura global — incluindo a região polar que interessa (ex. Shackleton).
  * É a base do Lunar Geodetic Coordinate System, garantindo consistência
    com os datasets formais.
  * MDS (Mission Data System) compatível com GDAL/`rasterio`.

* **Fonte complementar**: LOLA polar stereographic (5 m/px) para regiões
  polares específicas em que a resolução global não seja suficiente.

* **Alternativa de ajuste**: SLDEM2015 (512 ppd) para regiões fora dos
  polos quando a resolução é mais importante que a cobertura polar.

* Por que não GLD100 como única fonte:
  * A precisão vertical (~18 m) é baixa para cálculos de obstrução de
    horizonte a nível de landing site.
  * Baseada em estereoa, não em laser altimetry, com maior incerteza.

---

## 4. Como Descarregar

### 4.1 LOLA GDR — Geosciences Node

1. Visitar
   [http://pds-geosciences.wustl.edu/missions/lro/lola.htm](http://pds-geosciences.wustl.edu/missions/lro/lola.htm).
2. Aceder à secção "Data" / "Geosciences Online Archives".
3. Para resolução 64 ppd, descarregar o produto:
   * `lro-l-lola-3-rdr-v1/lrolol_0xxx/data/lola_edr/`
   * Título usual: "LOLA Global DTM 64 ppd" (PDS3).
4. Descarregar os ficheiros `.img`, `.lbl` (ou `.xml`) e, se aplicável,
   o `.hdr`.

### 4.2 LOLA — LOLA Data Node (mais recente)

* Acesso mais recente e frequentemente atualizado.
  [http://imbrium.mit.edu/](http://imbrium.mit.edu/).

### 4.3 SLDEM2015

* [https://imbrium.mit.edu/BROWSE/SLDEM2015/TILES/](https://imbrium.mit.edu/BROWSE/SLDEM2015/TILES/)
  — tiles por região (256 ppd e 512 ppd).
* [USGS Astrogeology](https://astrogeology.usgs.gov/) — petição de petição.

### 4.4 Polos

* LOLA polar stereographic products (manuscritos em research) são feitos
  em formato polar; estão disponíveis no PDS Geosciences Node ou através
  do LOLA Data Node.

---

## 5. Como Interpretar os Rasters

### 5.1 Estrutura PDS3

Cada produto `.img` está acompanhado de um `.lbl` (ou `.xml`) que
contém:

* `OBJECT_ID`, `PRODUCT_ID`, `RECORD_AREA` (página/linha/campo).
* `MAP_PROJECTION`: ex. "EQUIDISTANT CYLINDRICAL".
* `SAMPLE_NUM`, `LINE_NUM`, `PIXEL_SIZE`, `LINE_SIZE`, `FILE_SIZE`.
* `GROUND_TRACK` (início/ fim).
* `SCALE_FACTOR` e `OFFSET` (para converter valor bruto → elevação).
* `UNIT_OF_MEASURE`: "M", "KM", etc.
* `POINTING_ANGLES` (se for sensor).

Exemplo de leitura (pseudo):

```
# Ler o .lbl
label = read_pds3_label("lola_global_64.ppd.lbl")

# Extrair escala e offset
scale = label['SCALE_FACTOR']
offset = label['OFFSET']

# Abre o .img com rasterio
with rasterio.open("lola_global_64.ppd.img") as src:
    # Transformar latitude/longitude em pixel
    row, col = src.index(lon_deg, lat_deg)
    raw = src.read(1, window=((row, row+1), (col, col+1)))[0, 0]
    elevation_m = raw * scale + offset
```

### 5.2 Geotransform e projeção

* A projeção do rótulo define como converter longitude/latitude em
  coordenadas do raster.
* Para projeções "Equidistant Cylindrical", a conversão é linear:
  `col = (lon - lon0) / pixel_size`
  `row = (lat - lat0) / pixel_size` (com sinal correto).
* Para polars, há coordenadas próprias; usar a transformação do rótulo.

### 5.3 Elevação e raio lunar

Os produtos LOLA geralmente são obtidos como altitude em relação à
superfície de referência (raio lunar = 1737400 m).  Então:

```
elevation_m = raw_value * scale + offset
```

A elevação acima do elipsóide é `elevation_m`.  Se necessário, adicionar
à altura do observador.

---

## 6. Como Consultar a Elevação de uma Coordenada

Método:

1. Converter lat/lon (planetocentric + east-positive, [0, 360) ou
   [-180, 180] de acordo com o rótulo) para as coordenadas do raster.
2. Ler o valor do pixel (interpolação linear para precisão).
3. Converter para elevação com `scale`/`offset`.
4. Se exact match não estiver disponível, usar interpolação (bilinear
   ou bicúbica).

### Exemplo de consulta (pseudocódigo)

```
def get_elevation(src, lon_deg, lat_deg):
    row, col = src.index(lon_deg, lat_deg)
    # interpolação bilinear
    ...
    raw = sampled_value(src, row, col)
    elevation = raw * src.scales[0] + src.offsets[0]
    return elevation
```

---

## 7. Como Extrair um Perfil Topográfico ao Longo de um Azimute

Método:

1. Dado o terrain `(lat, lon)` e `azimuth_deg` e `distance_max` (ex. 10 km),
   gerar um conjunto de pontos ao longo da linha de visão:

```
for distance in [0, 100, 200, ..., 10000] (metros):
    lat_point, lon_point = destination_point(lat, lon, azimuth, distance)
    elevation = get_elevation(lat_point, lon_point)
```

2. Converter cada `lat/lon` para o referencial do raster.
3. Ler a elevação do rótulo.
4. Computar o ângulo de depressão do terreno em relação ao observador:

```
for each segment:
    dH = elevation_terrain - elevation_observer (m)
    dH = (elevation_terrain - elevation_observer)  # m
    angle = degrees(atan2(dH, distance))  # degrees
```

5. O `horizon_elevation_deg` é o mínimo de `angle` ao longo do perfil
   (depressão máxima).

---

## 8. Como Utilizar o Perfil para Determinar a Obstrução do Horizonte

O caminho para obstrução:

1. **Obter perfil de elevação** ao longo de um azimute (ver seção 7).
2. **Cálculo do ângulo visível**: para cada ponto ao longo do perfil,
   comparar a linha de visão com a linha tangente/horizonte geométrico.
3. **Obstrução**: se um terreno mais alto estiver entre o observador e o
   corpo (Sol/Terra), ele bloqueia a visão.  O ângulo de depressão do
   terreno é medida e comparada com o ângulo de elevação do corpo.
4. **Visibilidade topográfica**: se `elevation_body < horizon_elevation_deg`
   (ou `elevation_body + terrain_height_correction < 0`), então não se
   enxerda.
5. **Visibilidade geométrica**: sem terreno (plano), apenas o ângulo de
   elevação do corpo é necessário.

### Nota importante

* O MVP deve distinguir claramente:
  * **Visibilidade geométrica**: corpo acima do horizonte geométrico.
  * **Visibilidade topográfica**: linhas de visão não são bloqueadas por
    terreno.
* O motor new deve devolver ambos (se o terreno estiver disponível).

---

## 9. Implementação em Python (recomendada)

Bibliotecas que se devem usar (sem instalar agora sem autorização):

* `rasterio` ou `GDAL` (via `osgeo`) — leitura de rasters.
* `pvl` ou `pds3` — parse de rótulos PDS3.
* `numpy` — processamento de dados (já usado no MVP).
* `astropy` — transformações de coordenadas (se for usar ICRF/J2000).
* `shapely` — geometria (polígonos, linhas).

Nota: estas dependências são recomendadas para uso futuro; a integração
acontece somente com autorização de instalação.

---

## 10. Movimento Técnico Resumido

1. Baixar o produto LOLA GDR 64 ppd (PDS3).
2. Ler o `.lbl` (usando `pvl`).
3. Abrir o `.img` com `rasterio` (GDAL).
4. Implementar `get_elevation(lat, lon)` e `get_profile(lat, lon, azimuth, dist)`.
5. Integrar com o motor: se `terrain_availability != "none"`, calcular
   `horizon_elevation_deg`.
6. Testar com coordenadas reais (Shackleton, Apollo 11, etc.) e comparar
   com o modelo de visibilidade geométrica.
