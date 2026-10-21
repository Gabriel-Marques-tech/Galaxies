# Relatório de avaliação: moda-beleza

Setores: moda, beleza · alvo padrão: likes · modo: automatico

## Base

- 46.393 Shorts de 113 canais (YouTube Data API. 2.806 unidades de cota gratuita).
- 474 ganchos (primeiros 5s) com frames, descrição, fala e embedding.
- Atributos por extrator: laya (474), @cf/meta/llama-3.1-8b-instruct-fast (474).

## Regras fixas (o agente não altera)

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.
- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.
- Teto de 300 vídeos por canal (os mais recentes).
- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas mesmas linhas.
- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.

## Likes

**Modelo ativo `58381db140`** (metadados + historico):

- Erro +19.0% menor que o baseline (MAE 0.699 vs 0.863; erro típico 2.01× vs 2.37×).
- Acerta 58.0% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 75.6% dos resultados reais no teste (sem calibração: 63.1%).
- Hipótese registrada: otimização: melhor de 13 tentativas na validação (+2.5% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +0.9%, padrão: texto: -0.5%, padrão: historico+texto: +1.0%, padrão: historico+texto+multimodal: +4.3%, padrão: completo: +4.8%, padrão: completo: +5.4%, min_data_in_leaf=10: +2.5%, min_data_in_leaf=80: +1.7%, min_data_in_leaf=40: +1.0%, learning_rate=0.0361: +1.7%, l

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
| `58381db140` | metadados + historico **← ativo** | 2041 | 0.699 | 0.744 | 0.863 | +19.0% | +6.0% | 58.0% | 75.6% |
| `275468c32d` | metadados + historico + texto + multimodal + atributos (llama-3.1-8b-instruct-fast) | 190 | 0.909 | 0.914 | 0.977 | +6.9% | +0.5% | 58.7% | 74.2% |

## Views

**Modelo ativo `c149994b1f`** (metadados + historico + texto):

- Erro +18.6% menor que o baseline (MAE 0.697 vs 0.856; erro típico 2.01× vs 2.35×).
- Acerta 56.7% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 71.5% dos resultados reais no teste (sem calibração: 58.4%).
- Hipótese registrada: otimização: melhor de 14 tentativas na validação (+4.7% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +2.4%, padrão: texto: +1.7%, padrão: historico+texto: +3.7%, padrão: historico+texto+multimodal: -4.7%, padrão: completo: -3.5%, padrão: completo: +0.8%, min_data_in_leaf=10: +3.9%, min_data_in_leaf=80: +4.6%, min_data_in_leaf=40: +4.0%, learning_rate=0.0361: +3.7%, l

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `b7cc9e75f1` | metadados | 2062 | 0.728 | 0.728 | 0.856 | +14.9% | +0.0% | 55.0% | — |
| `ffc5e6bfb6` | metadados + multimodal | 103 | 0.956 | 0.955 | 1.031 | +7.3% | -0.1% | 60.5% | — |
| `b3733d3341` | metadados + atributos (llama-3.1-8b-instruct-fast) | 103 | 0.974 | 0.955 | 1.031 | +5.5% | -2.1% | 54.5% | — |
| `6c725946d0` | metadados + atributos (laya) | 103 | 1.028 | 0.955 | 1.031 | +0.2% | -7.7% | 46.5% | — |
| `15d5c1ab9c` | metadados + multimodal + atributos (llama-3.1-8b-instruct-fast) | 103 | 0.942 | 0.955 | 1.031 | +8.6% | +1.3% | 63.6% | — |
| `84912b3899` | metadados + multimodal + atributos (laya) | 103 | 1.007 | 0.955 | 1.031 | +2.3% | -5.5% | 49.7% | — |
| `977ae6bc8a` | metadados + historico + texto | 2062 | 0.697 | 0.732 | 0.856 | +18.5% | +4.8% | 57.3% | 72.2% |
| `c149994b1f` | metadados + historico + texto **← ativo** | 2062 | 0.697 | 0.726 | 0.856 | +18.6% | +4.1% | 56.7% | 71.5% |

## Busca do agente (likes, validação)

| origem | camadas | melhora sobre o controle | n validação |
|---|---|---|---|
| padrão: metadados | metadados | +0.0% | 2172 |
| padrão: historico | metadados + historico | +2.4% | 2172 |
| padrão: texto | metadados + texto | +1.7% | 2172 |
| padrão: historico+texto | metadados + historico + texto | +3.7% | 2172 |
| padrão: historico+texto+multimodal | metadados + historico + texto + multimodal | -4.7% | 22 |
| padrão: completo | metadados + historico + texto + multimodal + atributos | -3.5% | 22 |
| padrão: completo | metadados + historico + texto + multimodal + atributos | +0.8% | 22 |
| min_data_in_leaf=10 | metadados + historico + texto | +3.9% | 2172 |
| min_data_in_leaf=80 | metadados + historico + texto | +4.6% | 2172 |
| min_data_in_leaf=40 | metadados + historico + texto | +4.0% | 2172 |
| learning_rate=0.0361 | metadados + historico + texto | +3.7% | 2172 |
| learning_rate=0.0858 | metadados + historico + texto | +4.2% | 2172 |
| num_leaves=7 | metadados + historico + texto | +3.8% | 2172 |
| rodadas=1000 | metadados + historico + texto | +4.7% | 2172 |

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
- A faixa de 80% é calibrada no fim do treino e lá contém 80%; no teste (período mais recente) contém menos porque o período derivou: os vídeos novos rendem menos em relação à mediana histórica do canal do que o treino sugeria. Não é crescimento pendente (a curva observada mostra likes estáveis a partir de ~10 dias). O remédio é o ciclo: reotimizar com a base atualizada move o treino para perto do presente.
- Sugestões vêm de associação aprendida na base, não de causa.
- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas usam menos linhas de teste.

