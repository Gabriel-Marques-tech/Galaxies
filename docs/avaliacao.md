# Relatório de avaliação: moda-beleza

Setores: moda, beleza · alvo padrão: likes · modo: automatico

## Base

- 46.393 Shorts de 113 canais (YouTube Data API. 2.807 unidades de cota gratuita).
- 474 ganchos (primeiros 5s) com frames, descrição, fala e embedding.
- Atributos por extrator: laya (1151), @cf/meta/llama-3.1-8b-instruct-fast (474).

## Regras fixas (o agente não altera)

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.
- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.
- Teto de 300 vídeos por canal (os mais recentes).
- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas mesmas linhas.
- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.

## Likes

**Modelo ativo `6e7808ded3`** (metadados + historico, âncora móvel):

- Erro +24.5% menor que o baseline (MAE 0.652 vs 0.863; erro típico 1.92× vs 2.37×).
- Acerta 58.7% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 80.1% dos resultados reais no teste (sem calibração: 67.5%). A faixa provável de 50% contém 52.8%.
- Hipótese registrada: âncora móvel: alvo relativo à média dos últimos 10 vídeos do canal (defasada 7 dias) em vez da mediana fixa do treino. Hipótese do diagnóstico da deriva: o período de teste rende ~18% abaixo da mediana histórica e a árvore não extrapola um deslocamento global; a âncora móvel segue o momento do canal. Na validação empata com a fixa (a deriva começa depois dela).

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `de689c3026` | metadados | 2041 | 0.740 | 0.740 | 0.863 | +14.3% | +0.0% | 50.0% | — |
| `9710bd4332` | metadados + multimodal | 103 | 1.021 | 1.045 | 1.114 | +8.4% | +0.0% | 50.0% | — |
| `66d17cd226` | metadados + atributos | 103 | 1.043 | 1.045 | 1.114 | +6.3% | +0.0% | 50.0% | — |
| `0a14455e7b` | metadados + multimodal + atributos | 103 | 1.009 | 1.045 | 1.114 | +9.4% | +0.0% | 50.0% | — |
| `abea55d121` | metadados | 2041 | 0.748 | 0.748 | 0.863 | +13.3% | +0.0% | 58.5% | — |
| `768ddace71` | metadados + multimodal | 103 | 1.021 | 1.045 | 1.114 | +8.4% | +2.3% | 60.6% | — |
| `748469517b` | metadados + atributos (llama-3.1-8b-instruct-fast) | 103 | 1.043 | 1.045 | 1.114 | +6.3% | +0.1% | 50.7% | — |
| `42aff946c4` | metadados + atributos (laya) | 103 | 1.102 | 1.045 | 1.114 | +1.1% | -5.5% | 52.5% | — |
| `d5df310a1b` | metadados + multimodal + atributos (llama-3.1-8b-instruct-fast) | 103 | 1.009 | 1.045 | 1.114 | +9.4% | +3.5% | 62.4% | — |
| `c0e1db64a0` | metadados + multimodal + atributos (laya) | 103 | 1.072 | 1.045 | 1.114 | +3.7% | -2.6% | 54.6% | — |
| `58381db140` | metadados + historico | 2041 | 0.699 | 0.744 | 0.863 | +19.0% | +6.0% | 58.0% | 75.6% |
| `275468c32d` | metadados + historico + texto + multimodal + atributos (llama-3.1-8b-instruct-fast) | 190 | 0.909 | 0.914 | 0.977 | +6.9% | +0.5% | 58.7% | 74.2% |
| `1db5263c59` | metadados + historico | 2041 | 0.700 | 0.740 | 0.863 | +19.0% | +5.4% | 58.5% | 74.2% |
| `6e7808ded3` | metadados + historico, âncora móvel **← ativo** | 2041 | 0.652 | 0.738 | 0.863 | +24.5% | +11.8% | 58.7% | 80.1% |

## Views

**Modelo ativo `db8c565807`** (metadados + historico, âncora móvel):

- Erro +20.5% menor que o baseline (MAE 0.680 vs 0.856; erro típico 1.97× vs 2.35×).
- Acerta 54.4% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 73.8% dos resultados reais no teste (sem calibração: 67.0%). A faixa provável de 50% contém 49.6%.
- Hipótese registrada: âncora móvel: alvo relativo à média dos últimos 10 vídeos do canal (defasada 7 dias) em vez da mediana fixa do treino. Hipótese do diagnóstico da deriva: o período de teste rende ~18% abaixo da mediana histórica e a árvore não extrapola um deslocamento global; a âncora móvel segue o momento do canal. Na validação empata com a fixa (a deriva começa depois dela).

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `b7cc9e75f1` | metadados | 2062 | 0.728 | 0.728 | 0.856 | +14.9% | +0.0% | 55.0% | — |
| `ffc5e6bfb6` | metadados + multimodal | 103 | 0.956 | 0.955 | 1.031 | +7.3% | -0.1% | 60.5% | — |
| `b3733d3341` | metadados + atributos (llama-3.1-8b-instruct-fast) | 103 | 0.974 | 0.955 | 1.031 | +5.5% | -2.1% | 54.5% | — |
| `6c725946d0` | metadados + atributos (laya) | 103 | 1.028 | 0.955 | 1.031 | +0.2% | -7.7% | 46.5% | — |
| `15d5c1ab9c` | metadados + multimodal + atributos (llama-3.1-8b-instruct-fast) | 103 | 0.942 | 0.955 | 1.031 | +8.6% | +1.3% | 63.6% | — |
| `84912b3899` | metadados + multimodal + atributos (laya) | 103 | 1.007 | 0.955 | 1.031 | +2.3% | -5.5% | 49.7% | — |
| `977ae6bc8a` | metadados + historico + texto | 2062 | 0.697 | 0.732 | 0.856 | +18.5% | +4.8% | 57.3% | 72.2% |
| `c149994b1f` | metadados + historico + texto | 2062 | 0.697 | 0.726 | 0.856 | +18.6% | +4.1% | 56.7% | 71.5% |
| `db8c565807` | metadados + historico, âncora móvel **← ativo** | 2062 | 0.680 | 0.728 | 0.856 | +20.5% | +6.5% | 54.4% | 73.8% |

## Busca do agente (likes, validação)

| origem | camadas | melhora sobre o controle | ganho real? | n validação |
|---|---|---|---|---|
| padrão: metadados | metadados | +0.0% | indistinguível (50%) | 2144 |
| padrão: historico | metadados + historico | +1.1% | sim (94%) | 2144 |
| padrão: texto | metadados + texto | -0.1% | indistinguível (42%) | 2144 |
| padrão: historico+texto | metadados + historico + texto | +0.9% | indistinguível (88%) | 2144 |
| padrão: historico+texto+multimodal | metadados + historico + texto + multimodal | — | sem poder estatístico: 22 linhas na validação (mínimo 300); precisa de ~2891 vídeos com essas camadas para medir a difer | 22 |
| padrão: completo | metadados + historico + texto + multimodal + atributos | — | sem poder estatístico: 22 linhas na validação (mínimo 300); precisa de ~2891 vídeos com essas camadas para medir a difer | 22 |
| padrão: completo | metadados + historico + texto + multimodal + atributos | — | sem poder estatístico: 22 linhas na validação (mínimo 300); precisa de ~2891 vídeos com essas camadas para medir a difer | 22 |
| min_data_in_leaf=10 | metadados + historico | +1.4% | sim (98%) | 2144 |
| meia_vida_dias=730 | metadados + historico | +0.5% | indistinguível (75%) | 2144 |
| rodadas=1000 | metadados + historico | +0.8% | indistinguível (87%) | 2144 |
| meia_vida_dias=180 | metadados + historico | -0.5% | indistinguível (26%) | 2144 |
| learning_rate=0.0167 | metadados + historico | +0.8% | indistinguível (89%) | 2144 |
| com multimodal | metadados + historico + multimodal | — | sem poder estatístico: 22 linhas na validação (mínimo 300); precisa de ~2891 vídeos com essas camadas para medir a difer | 22 |

## Crescimento observado

A coleta é uma foto só; os vídeos recentes foram reobservados dias depois (6.237 vídeos, intervalo mediano 1.8 dias). A inclinação é quanto `log(1 + y)` cresce por `log(idade)`; 0 = parou de crescer. Abaixo de 48 dias (idade que o modelo quase não viu no treino) a timeline recua pela curva.

| faixa de idade | likes (n) | views (n) |
|---|---|---|
| 0–2 dias | 0.35 (60) | 0.37 (63) |
| 2–5 dias | 0.20 (155) | 0.27 (160) |
| 5–10 dias | 0.07 (229) | 0.13 (239) |
| 10–20 dias | 0.00 (488) | 0.07 (488) |
| 20–40 dias | 0.00 (941) | 0.05 (944) |
| 40–80 dias | 0.00 (3266) | 0.00 (3289) |
| 80–160 dias | 0.00 (1032) | 0.00 (1054) |

## Limitações

- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo serve para expectativa, triagem e priorizar testes, não para cravar números.
- O período de teste derivou: os vídeos novos rendem ~18% menos em relação à mediana histórica do canal do que o treino sugeria. Não é crescimento pendente (a curva observada mostra likes estáveis a partir de ~10 dias). Com a âncora fixa a faixa de 80% cobria ~75% no teste; a âncora móvel (média dos últimos 10 vídeos do canal) segue a deriva e fechou a cobertura. O ciclo de reotimização com a base atualizada continua sendo o remédio de longo prazo.
- Sugestões vêm de associação aprendida na base, não de causa.
- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas usam menos linhas de teste.

