# Relatório de avaliação: fitness

Setores: fitness · alvo padrão: likes · modo: automatico

## Base

- 13.206 Shorts de 30 canais (YouTube Data API. 2.797 unidades de cota gratuita).
- 0 ganchos (primeiros 5s) com frames, descrição, fala e embedding.
- Atributos por extrator: laya (288).

## Regras fixas (o agente não altera)

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.
- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.
- Teto de 300 vídeos por canal (os mais recentes).
- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas mesmas linhas.
- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.

## Likes

**Modelo ativo `e3b1679a4a`** (metadados + historico, âncora móvel):

- Erro +7.3% menor que o baseline (MAE 0.759 vs 0.819; erro típico 2.14× vs 2.27×).
- Acerta 52.0% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 82.5% dos resultados reais no teste (sem calibração: 70.6%). A faixa provável de 50% contém 56.4%.
- Hipótese registrada: otimização: melhor de 14 tentativas na validação (+11.2% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +5.4%, padrão: texto: +2.2%, padrão: movel: +9.4%, padrão: historico+texto: +6.8%, com texto: +10.0%, min_data_in_leaf=40: +10.7%, meia_vida_dias=180: +10.3%, learning_rate=0.0858: +10.0%, rodadas=150: +11.0%, sem texto: +11.2%, ancora mediana_canal: +5.6%, meia_vida

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `7883ca00ed` | metadados + historico + texto, âncora móvel | 2101 | 0.800 | 0.860 | 0.912 | +12.4% | +7.0% | 57.3% | 79.1% |
| `e3b1679a4a` | metadados + historico, âncora móvel **← ativo** | 892 | 0.759 | 0.784 | 0.819 | +7.3% | +3.2% | 52.0% | 82.5% |

## Views

**Modelo ativo `ebab86e22c`** (metadados + historico + texto, âncora móvel):

- Erro +6.7% menor que o baseline (MAE 0.805 vs 0.863; erro típico 2.24× vs 2.37×).
- Acerta 53.6% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 76.3% dos resultados reais no teste (sem calibração: 64.7%). A faixa provável de 50% contém 49.9%.
- Hipótese registrada: otimização: melhor de 8 tentativas na validação (+7.5% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +1.7%, padrão: texto: +2.4%, padrão: movel: +3.7%, padrão: historico+texto: +6.1%, ancora movel: +7.5%, min_data_in_leaf=40: +7.1%

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `ebab86e22c` | metadados + historico + texto, âncora móvel **← ativo** | 892 | 0.805 | 0.828 | 0.863 | +6.7% | +2.7% | 53.6% | 76.3% |

## Busca do agente (likes, validação)

| origem | camadas | melhora sobre o controle | ganho real? | n validação |
|---|---|---|---|---|
| padrão: metadados | metadados | +0.0% | indistinguível (50%) | 607 |
| padrão: historico | metadados + historico | +1.7% | sim (91%) | 607 |
| padrão: texto | metadados + texto | +2.4% | sim (99%) | 607 |
| padrão: titulo | metadados + historico + titulo | — | receita com poucos dados (0 treino, 0 teste): processe mais ganchos, calcule os atributos ou o texto | 0 |
| padrão: movel | metadados + historico | +3.7% | sim (99%) | 607 |
| padrão: historico+texto | metadados + historico + texto | +6.1% | sim (100%) | 607 |
| ancora movel | metadados + historico + texto | +7.5% | sim (100%) | 607 |
| min_data_in_leaf=40 | metadados + historico + texto | +7.1% | sim (100%) | 607 |

## Crescimento observado

- Ainda sem reobservação: rode `observar_recentes` uma vez por dia para medir como likes e views crescem com a idade do vídeo.

## Limitações

- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo serve para expectativa, triagem e priorizar testes, não para cravar números.
- A base é uma foto só: o período de teste pode render diferente da mediana histórica do canal (deriva). A âncora móvel (média dos últimos 10 vídeos do canal) segue esse movimento; a reobservação diária mede a curva de crescimento; e a reotimização com a base atualizada é o remédio de longo prazo.
- Sugestões vêm de associação aprendida na base, não de causa.
- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas usam menos linhas de teste.

