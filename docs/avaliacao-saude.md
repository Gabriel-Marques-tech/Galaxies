# Relatório de avaliação: saude

Setores: saude · alvo padrão: likes · modo: automatico

## Base

- 9.358 Shorts de 42 canais (YouTube Data API. 2.797 unidades de cota gratuita).
- 0 ganchos (primeiros 5s) com frames, descrição, fala e embedding.
- Atributos por extrator: laya (288).

## Regras fixas (o agente não altera)

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.
- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.
- Teto de 300 vídeos por canal (os mais recentes).
- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas mesmas linhas.
- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.

## Likes

**Modelo ativo `2377ff9de9`** (metadados + historico + texto, âncora móvel):

- Erro +23.0% menor que o baseline (MAE 0.769 vs 1.000; erro típico 2.16× vs 2.72×).
- Acerta 57.1% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 82.8% dos resultados reais no teste (sem calibração: 73.5%). A faixa provável de 50% contém 59.8%.
- Hipótese registrada: otimização: melhor de 10 tentativas na validação (+21.4% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +6.7%, padrão: texto: -3.9%, padrão: movel: +14.5%, padrão: historico+texto: +10.4%, com texto: +21.4%, min_data_in_leaf=40: +21.1%, meia_vida_dias=180: +21.1%, learning_rate=0.0858: +18.5%

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `2377ff9de9` | metadados + historico + texto, âncora móvel **← ativo** | 895 | 0.769 | 0.836 | 1.000 | +23.0% | +8.0% | 57.1% | 82.8% |

## Views

**Modelo ativo `2b2d715474`** (metadados + historico + texto, âncora móvel):

- Erro +17.4% menor que o baseline (MAE 0.810 vs 0.980; erro típico 2.25× vs 2.66×).
- Acerta 55.0% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 83.5% dos resultados reais no teste (sem calibração: 71.9%). A faixa provável de 50% contém 58.5%.
- Hipótese registrada: otimização: melhor de 14 tentativas na validação (+23.6% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +2.7%, padrão: texto: -1.3%, padrão: movel: +17.0%, padrão: historico+texto: +7.3%, com texto: +21.3%, min_data_in_leaf=40: +22.9%, meia_vida_dias=180: +22.5%, learning_rate=0.0858: +21.1%, rodadas=150: +23.6%, sem texto: +19.9%, ancora mediana_canal: +5.8%, meia_vid

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `2b2d715474` | metadados + historico + texto, âncora móvel **← ativo** | 955 | 0.810 | 0.903 | 0.980 | +17.4% | +10.3% | 55.0% | 83.5% |

## Busca do agente (likes, validação)

| origem | camadas | melhora sobre o controle | ganho real? | n validação |
|---|---|---|---|---|
| padrão: metadados | metadados | +0.0% | indistinguível (50%) | 1073 |
| padrão: historico | metadados + historico | +2.7% | sim (100%) | 1073 |
| padrão: texto | metadados + texto | -1.3% | indistinguível (2%) | 1073 |
| padrão: titulo | metadados + historico + titulo | — | receita com poucos dados (0 treino, 0 teste): processe mais ganchos, calcule os atributos ou o texto | 0 |
| padrão: movel | metadados + historico | +17.0% | sim (100%) | 1073 |
| padrão: historico+texto | metadados + historico + texto | +7.3% | sim (100%) | 1073 |
| com texto | metadados + historico + texto | +21.3% | sim (100%) | 1073 |
| min_data_in_leaf=40 | metadados + historico + texto | +22.9% | sim (100%) | 1073 |
| meia_vida_dias=180 | metadados + historico + texto | +22.5% | sim (100%) | 1073 |
| learning_rate=0.0858 | metadados + historico + texto | +21.1% | sim (100%) | 1073 |
| rodadas=150 | metadados + historico + texto | +23.6% | sim (100%) | 1073 |
| sem texto | metadados + historico | +19.9% | sim (100%) | 1073 |
| ancora mediana_canal | metadados + historico + texto | +5.8% | sim (100%) | 1073 |
| meia_vida_dias=180 | metadados + historico + texto | +23.1% | sim (100%) | 1073 |

## Crescimento observado

- Ainda sem reobservação: rode `observar_recentes` uma vez por dia para medir como likes e views crescem com a idade do vídeo.

## Limitações

- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo serve para expectativa, triagem e priorizar testes, não para cravar números.
- A base é uma foto só: o período de teste pode render diferente da mediana histórica do canal (deriva). A âncora móvel (média dos últimos 10 vídeos do canal) segue esse movimento; a reobservação diária mede a curva de crescimento; e a reotimização com a base atualizada é o remédio de longo prazo.
- Sugestões vêm de associação aprendida na base, não de causa.
- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas usam menos linhas de teste.

