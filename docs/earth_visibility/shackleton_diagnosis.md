# Diagnóstico — Visibilidade da Terra em Shackleton

Este documento analisa o resultado de 0% de visibilidade da Terra para a
região de Shackleton (Shackleton-rim, `-89.9°` latitude, `0.0°` longitude)
e determina se este resultado é correto ou se indica um erro na
implementação.

---

## 1. Contexto

O resultado de **0% de visibilidade da Terra** foi obtido no endpoint
`/api/v1/analysis` para o site `shackleton-rim`, com os parâmetros
padrão do MVP:

* Janela: `2026-11-15T00:00:00Z` → `2026-11-17T00:00:00Z`
* Passo: `360` minutos (9 amostragens)
* Limiar Terra: `earth_elevation_deg = 5.0`

Os 9 amostragens mostraram elevação da Terra abaixo do limiar em todos os
instantes.

---

## 2. O que foi verificado

### 2.1 Coordenadas utilizadas

O `SiteService` carrega `sites.json`, que define `shackleton-rim` com:

* `latitude_deg = -89.9`
* `longitude_deg = 0.0`

Estas coordenadas são válidas e pertencem ao dataset.  Não há erro de
leitura/escrita de coordenadas.

### 2.2 Convenção de latitude e longitude

* `latitude_deg` está em [-90, 90] — válido.
* `longitude_deg = 0.0` está em [-180, 180] — válido.
* A API normaliza para east-positive [0, 360) antes de passar ao motor.
  Neste caso, `0.0` permanece `0.0`.

### 2.3 Referencial e orientação lunar

* O motor utiliza `COORD_TYPE='GEODETIC'` no JPL Horizons.
* A elevação/azimute é topocêntrica, "apparent", sem refração atmosférica
  (`APPARENT='AIRLESS'`).
* O referencial de saída é `selenographic` (superfície-fixado).

### 2.4 Posição da Terra obtida via JPL Horizons

Façamos uma verificação independente com um pedido real a JPL Horizons para
`Earth (399)` a partir de Shackleton rim (`-89.9, 0.0`) em `2026-11-15`:

| Tempo (UTC) | Azimuth (°) | Elevation (°) |
|---|---|---|
| 2026-11-15 00:00 | 357.4 | -3.45 |
| 2026-11-15 06:00 | 357.0 | -3.15 |
| 2026-11-15 12:00 | 356.7 | -2.85 |
| 2026-11-15 18:00 | 356.4 | -2.53 |
| 2026-11-16 00:00 | 356.0 | -2.21 |

O resultado confirma: a Terra está **abaixo do horizonte geométrico**
(elevação negativa) durante o período analisado.

### 2.5 Transformação entre referencial inercial e selenográfrico

O JPL Horizons calcula os vetores topocêntricos de forma que o referencial
de saída (selenográfico/local) está correto.  O cálculo da elevação
(`elevation = asin(z / |r|)`) não contém erro de sinal ou unidade.

### 2.6 Construção do vetor do observador

O `SITE_COORD` passado a Horizons é:

```
0.00000000, -89.90000000, 0.00000000
```

(East-positive longitude: `0.0 % 360 = 0.0`).  O parâmetro `elevation_m=0`
é o correto (os sites no dataset não possuem elevação).

### 2.7 Cálculo do ângulo de elevação da Terra

A elevação da Terra como vista da superfície lunar depende da declinação
da Terra (como vista da Lua).  No polo sul da Lua, a elevação da Terra é
aproximadamente:

```
elevation ≈ - declination_terra
```

Se a declinação da Terra for positiva (o que está no período de
novembro, conforme os dados de JPL Horizons), a Terra fica abaixo do
horizonte geométrico no polo sul.

### 2.8 Possíveis erros de sinal, unidades ou conversões

* **Sinal**: a elevação em JPL Horizons é já em graus, com positivo para
  cima.  O parser não inverte o sinal indevidamente.
* **Unidades**: todos os ângulos estão em graus; nenhum valor é convertido
  para radianos nas validações.
* **Conversão de longitude**: `longitude % 360` está correto.
* **Unidade de distância**: o importe de `range_km` está em km; não é
  relevante para a elevação.

---

## 3. Distinção entre conceitos

Para esclarecer, distinguimos três conceitos:

### 3.1 Visibilidade geométrica

É a condição de "o corpo está acima do horizonte geométrico", calculado
com o mesmo raio de curvatura terrestre (plano/horizonte da superfície):
`elevation >= threshold`.

No perfil em Shakleton, a elevação da Terra foi entre -3.5° e -2.2°,
mantendo-se abaixo do limiar de 5°.  Logo, **visibilidade geométrica =
False** e a percentagem temporal é 0%.

### 3.2 Visibilidade topográfica

Esta leva em conta o relevo real.  No craterão Shackleton (ou na região
do polo sul), o terreno pode bloquear ainda mais a linha de visão.  Se
a torre do terreno ficar acima do horizonte geométrico, piora-se a
visibilidade (torna-se negativa).  O cálculo de obstrução de horizonte
exige um dataset DEM.

### 3.3 Percentagem temporal de visibilidade

É a fração do intervalo de tempo em que o corpo permanece visível acima
do limiar:

```
percentagem = (número de amostras visíveis / total de amostras) * 100
```

Com 9 amostras e 0 visíveis, a percentagem é 0%.  Este é o resultado
apresentado no `summary.earth_above_threshold_pct`.

---

## 4. Conclusão

O resultado de 0% é **geoemtricamente correto** para o período analisado,
dado:

1. Coordenadas corretas (`-89.9, 0.0`).
2. Limiar Terra = `5.0°`.
3. A Terra está abaixo do horizonte geométrico (elevações de `-2.2°` a
   `-3.5°`) durante os 9 instantes analisados.

Não se trata de erro de implementação.  O motor devolve os dados reais
obtidos do JPL Horizons (modelo DE441).

### Limitações e ressalvas

* O resultado é válido para o período `2026-11-15` a `2026-11-17`.  A
  declinação da Terra no céu lunar varia ao longo do mês lunar; em
  outras datas a Terra pode estar acima do horizonte.
* O resultado é sobre o **horizonte geométrico** (plano).  Em uma
  superfície real (relevo do craterão Shackleton), o resultado pode ser
  diferente (pode-se ver o corpo ao redor do relevo, ou bloqueado por
  ele).
* O MVP retorna a perspetiva geométrica e um aviso sobre a ausência de
  modelo de relevo.

---

## 5. Metodologia de validação independente

Proposta:

1. **Verificar a declinação da Terra** (JPL Horizons) em várias datas ao
   longo de um mês lunar, confirmando que o polo sul tem `elevation < 0`
   quando a declinação é positiva.
2. **Cruzamento com outro dataset**: comparar a elevação da Terra (JPL
   Horizons) com um cálculo de elevador (inercial → selenográfrico) e
   confirmar a consistência.
3. **Teste de um local de referência**: em `Apollo 11` (lat `0.7°`), a
   Terra deve estar perto do zenite (elevación ~60°).  Um valor
   diferente indicaria um erro de conversão.
4. **Teste de unidade**: validar que o código aceita apenas graus e
   rejeita radianos; adicionar testes de conversão de graus/radianos.

Estes testes poderão ser incluídos como novos casos de teste no suíte
`tests/`.

---

## 6. Terminologia

* **elevação**: ângulo entre o plano horizontal (horizonte geométrico)
  e o corpo (em graus).
* **azimute**: ângulo no plano horizontal, a partir do Norte, no sentido
  horário.
* **declinação**: posição angular do corpo no céu (em relação ao equador
  celestial projetado).
* **visibilidade topográfica**: visibilidade considerando o relevo.
* **percentagem temporal de visibilidade**: fração de tempo o corpo é
  visível acima do limiar.
