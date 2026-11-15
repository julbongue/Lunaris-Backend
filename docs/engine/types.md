# Tipos, Unidades e Convenções — Motor Científico LUNARIS

Este documento detalha os tipos de dados, unidades físicas e convenções de
coordenadas usados no contrato definitivo do motor científico.

---

## 1. Unidades Físicas

Todas as entradas e saídas do motor devem usar as seguintes unidades:

| Físico | Unidade de uso | Unidades aceites | Observações |
|---|---|---|---|
| Ângulo | **graus (deg)** | radianos (apenas internamente, se necessário) | Nunca devolver ângulos em radianos para o contrato |
| Altitude / elevação | **metros (m)** para altura; **quilómetros (km)** para alcance | m, km | A escala de altitude no DEM é m; o alcance de JPL Horizons é km |
| Tempo | **UTC** | s, min, h, dias | O passo de amostragem é em minutos; os instantes são UTC |
| Distância (terreno) | **metros (m)** | — | Os rasters DEM usam m (ou pixel), a escala é definida no header |
| Irradiância | **W/m²** | — | Usado nas condições de iluminação |

### Graus vs Radianos

* Todos os ângulos do contrato (`EngineInput`, `EngineResult`) são em graus.
* Internamente, o motor pode converter para radianos para cálculos
  trigonométricos, mas sempre converte de volta para graus.
* As validações Pydantic rejeitam graus fora do intervalo definido.

---

## 2. Coordenadas Geográficas Lunares

### 2.1 Latitude

* Intervalo: [-90, +90] graus.
* Positive para **norte**.
* Duas convenções são possíveis:
  * **planetocentric**: latitude medida a partir do equilátero da Lua (plano
    equatorial), positivo para norte.  É o padrão do JPL Horizons e o
    usado na maioria dos almanacos planetários.
  * **planetographic**: latitude medida a partir do elipsóide de referência.
    Idem ao planetocentric, mas a definição usa o elipsóide.  O valor em
    graus é interpretado ao longo do elipsóide.

### 2.2 Longitude

* Intervalo: [-180, +180] graus (ou [0, 360) normalizado).
* **East-positive**: leste = positivo, oeste = negativo.
* O JPL Horizons usa longitude east-positive no referencial do corpo.
* A API normaliza a longitude para [0, 360) antes de passar ao motor
  (quando o motor espera east-positive).

### 2.3 Altitude

* Altura do observador acima da superfície de referência (equilátero ou
  elipsóide).
* Unidade: metros.
* Se o dataset de site não fornecer elevação, o valor **0 m** é usado e
  uma advertência é devolvida.

### 2.4 Eixos e orientação (notação)

Para manter a clareza, usa-se a seguinte notação:

* **N** = direcção geográfica norte.
* **E** = direcção geográfica leste.
* **Z** = vertical (zenite do observador).
* **χ** (xi) = elevação angular do corpo acima do horizonte (z).
* **η** (eta) = azimute medido a partir do norte, sentido horário (N→E =
  90°, S = 180°, W = 270°).

---

## 3. Referenciais

### 3.1 Selenográfico (superfície-fixo)

* O referencial de rotação da Lua.
* O eixo polar está ligado à rotação lunar.
* Os azimutes topocêntricos são expressos neste referencial (azimute a
  partir do norte local, sentido horário).

### 3.2 Inercial (ICRF / J2000)

* Referencial não-rotativo.
* Usado como base para as posições estelares e dos corpos.
* A transformação para o selenográfico envolve a rotação lunear (inclinação
  do eixo, precessão, libração).

### 3.3 Eclíptica de data

* Referencial do plano eclíptica na data do cálculo.
* Usado para posicionar o Sol e a Terra.

### 3.4 Convenção de transformação

Para o MVP:

* Entrada: coordenadas em `planetocentric`, referencial `selenographic`.
* Cálculo: o JPL Horizons devolve as posições topocêntricas no referencial
  necessário (normalmente equatorial ou eclíptica de data).
* Saída: o motor deve transformar para o referencial selenográfico e
  devolver os azimutes/elevações no referencial `selenographic`.

Para motores que usam outros datasets (ex.: LOLA terreno), a transformação
entre o referencial lunar e o inercial deve ser manifestada no código e
documentada.

---

## 4. Validação de Unidades

As validações nos schemas Pydantic (`app/schemas/engine.py`) aplicam-se às
unidades do contrato:

| Campo | Validação |
|---|---|
| `latitude_deg` | [-90, 90] |
| `longitude_deg` | [-180, 180] |
| `altitude_m` | >= 0 |
| `sun_elevation_deg`, `earth_elevation_deg` | [-90, 90] |
| `azimuth_deg` | [0, 360) |
| `elevation_deg` | [-90, 90] |
| `phase_angle_deg` | [0, 180] |
| `incidence_angle_deg`, `emission_angle_deg` | [0, 90] |
| `solar_longitude_deg` | [0, 360) |
| `horizon_elevation_deg` | [-90, 90] |
| `step_minutes` | [1, 1440] |

Qualquer valor fora destes intervalos gera um erro de validação (422 na
API).

---

## 5. Interpretação de Dados de Terreno (DEM)

### 5.1 Rasters (formato binário)

A maioria dos datasets DEM lunar são rasters georreferenciados:

* Cada pixel tem uma altura (elevação em relação a um referencial).
* O raster tem um geotransform que mapeia pixel → longitude/latitude (ou
  coordenadas projetadas).
* O valor do pixel representa a altura do terreno nessa posição.

### 5.2 PDS3 (.img/.lbl ou .xml)

Os datasets da NASA (LOLA, LOLA + Kaguya, GLD100) são normalmente distribuídos
em formato PDS3:

* `.img` — dados binários (geralmente little-endian, shorts sem sinal ou
  floats).
* `.lbl` (ou `.xml`) — rótulos com metadados: escala, offset, projeção,
  extensão, unidade do valor, etc.
* A leitura do rótulo é obrigatória para interpretar os dados.

### 5.3 Escalas e offsets

Os valores brutos do raster são geralmente **amostragem inteira** de
elevação.  O rótulo tem:

* `SCALE_FACTOR`: multiplicador para obter o valor físico.
* `OFFSET`: correção aditiva.
* Unidade: metros (ou outra unidade).

Fórmula:

```
elevation_m = raw_value * SCALE_FACTOR + OFFSET
```

(Referencia-se à superfície de referência, e.g. raio lunar de 1737.4 km.)

---

## 6. Código de Cores e Outros Atributos

Atenção ao "co-de-cores" (no de raster):

* O valor do pixel pode ser de altura ou outro atributo (inclinação,
  albedo).
* O dataset deve indicar o significado do pixel no rótulo.

Para o MVP, apenas a elevação vertical (`elevation`) é necessária.
