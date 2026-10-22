# Relatório de avaliação: automotivo

Setores: automotivo · alvo padrão: likes · modo: cientista

## Base

- 18.337 Shorts de 45 canais (YouTube Data API. 3.639 unidades de cota gratuita).
- 0 ganchos (primeiros 5s) com frames, descrição, fala e embedding.
- Atributos por extrator: .

## Regras fixas (o agente não altera)

- Alvo: `log((y + 1) / (mediana do canal + 1))`, mediana calculada só no treino.
- Split temporal: os 20% mais recentes são teste, só vídeos com 7+ dias. A otimização compara receitas na validação (fim do treino); o teste é usado uma vez por experimento.
- Teto de 300 vídeos por canal (os mais recentes).
- Baseline: média do canal. Controle: só metadados, hiperparâmetros padrão, nas mesmas linhas.
- Métricas: MAE no log (erro típico = e^MAE vezes), acerto A vs B em pares de vídeos do mesmo canal (acaso = 50%), cobertura real da faixa de 80% depois da calibração.

## Likes

**Modelo ativo `e2b020bfcf`** (metadados + historico, âncora móvel):

- Erro +19.8% menor que o baseline (MAE 0.684 vs 0.853; erro típico 1.98× vs 2.35×).
- Acerta 58.6% dos pares A vs B no mesmo canal (acaso: 50%).
- A faixa de 80% contém 81.4% dos resultados reais no teste (sem calibração: 72.0%). A faixa provável de 50% contém 54.7%.
- Hipótese registrada: otimização: melhor de 6 tentativas na validação (+6.1% sobre o controle). Tentativas: padrão: metadados: +0.0%, padrão: historico: +2.4%, padrão: texto: -2.9%, padrão: movel: +6.1%, padrão: historico+texto: +3.5%, com texto: +6.1%

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `e2b020bfcf` | metadados + historico, âncora móvel **← ativo** | 1722 | 0.684 | 0.696 | 0.853 | +19.8% | +1.8% | 58.6% | 81.4% |

## Views

| id | receita | n teste | MAE | só meta | baseline | vs baseline | vs controle | A vs B | faixa 80% |
|---|---|---|---|---|---|---|---|---|---|
| `e011cb5b36` | metadados + historico + texto, âncora móvel | 1727 | 0.762 | 0.765 | 0.916 | +16.7% | +0.3% | 54.6% | 81.8% |

## Busca do agente (likes, validação)

| origem | camadas | melhora sobre o controle | ganho real? | n validação |
|---|---|---|---|---|
| padrão: metadados | metadados | +0.0% | indistinguível (50%) | 1485 |
| padrão: historico | metadados + historico | +2.3% | sim (100%) | 1485 |
| padrão: texto | metadados + texto | -1.9% | indistinguível (1%) | 1485 |
| padrão: movel | metadados + historico | +5.3% | sim (100%) | 1485 |
| padrão: historico+texto | metadados + historico + texto | +1.9% | sim (98%) | 1485 |
| com texto | metadados + historico + texto | +6.0% | sim (100%) | 1485 |
| min_data_in_leaf=40 | metadados + historico + texto | +6.2% | sim (100%) | 1485 |
| meia_vida_dias=180 | metadados + historico + texto | +6.3% | sim (100%) | 1485 |

## Crescimento observado

- Ainda sem reobservação: rode `observar_recentes` uma vez por dia para medir como likes e views crescem com a idade do vídeo.

## Limitações

- Previsão antes de publicar tem teto natural: algoritmo e acaso pesam muito. O modelo serve para expectativa, triagem e priorizar testes, não para cravar números.
- A base é uma foto só: o período de teste pode render diferente da mediana histórica do canal (deriva). A âncora móvel (média dos últimos 10 vídeos do canal) segue esse movimento; a reobservação diária mede a curva de crescimento; e a reotimização com a base atualizada é o remédio de longo prazo.
- Sugestões vêm de associação aprendida na base, não de causa.
- Camadas de gancho e atributos cobrem só os vídeos com camada bruta; comparações nelas usam menos linhas de teste.

