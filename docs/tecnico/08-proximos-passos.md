# 08 · Revisão da modelagem e próximos passos

Revisão de código feita em 21/10/2026 por um agente leitor (sem rodar nada), conferida e
anotada aqui. Separa o que já foi corrigido, o que é limitação conhecida e o que vale
tentar, com estimativa de ganho e esforço. É o roadmap técnico depois da entrega.

## Corrigido na mesma noite

- **Sugestões fora da referência da timeline**: `analise.sugerir` usava a previsão na idade
  recortada (48 d) sem o recuo da curva de crescimento; `previsto_7d` saía ~2% (likes) /
  ~13% (views) acima da timeline. Agora recebe o mesmo deslocamento da timeline em 7 e 30
  dias.
- **Excluídos entravam no histórico do canal** (`historico_do_banco`, `_historico_do_novo`):
  um vídeo marcado como dado ruim ainda puxava a âncora móvel. Filtrado.
- **`acerto_pares` com padrão 0,5**: experimentos antigos apareciam como "50,0%" no relatório
  como se tivessem sido medidos. Virou `None` e aparece como "—".

## Limitações conhecidas (documentar, não esconder)

- **Idade é proxy de calendário.** Com uma coleta só, `idade_dias = coletado_em −
  publicado_em` é função da data de publicação. `log_idade_dias` como feature aprende
  "quando" o vídeo saiu, não "quanto ele cresceu". Todo o teste tem idade abaixo do 5º
  percentil do treino e cai na folha extrema da árvore. Em likes o efeito é pequeno (a
  curva observada estabiliza em ~10 dias); em views, que ainda crescem até ~40 dias, parte
  da "deriva" e dos 74% de cobertura é isso. A timeline já usa a curva; o alvo, ainda não.
- **Histórico com números maduros.** Os "últimos 10 vídeos" usam a contagem da coleta, não a
  que estava visível no dia da publicação. A defasagem de 7 dias atenua em likes. No teste,
  anteriores e alvo estão igualmente "verdes", e parte do ganho da âncora móvel vem desse
  cancelamento; ao vivo, `_historico_do_novo` deveria usar `observacoes` (números frescos).
- **Teste reutilizado na seleção.** Cada experimento usa o teste uma vez, mas foram 14
  experimentos de likes nas mesmas 2.041 linhas. O erro padrão da diferença pareada de MAE
  é ~0,007 (~1% do MAE): `MARGEM_SOBRE_CONTROLE = 1%` está no piso de ruído e o melhor entre
  muitos é otimista. Além disso, `ganho_por_atributo` em `treinar` roda no teste e alimenta
  sugestões de atributos novos.
- **Bootstrap iid com dados agrupados.** As linhas vêm de ~100 canais; reamostrar linhas
  superestima a confiança ("98%" para +1,4%). Reamostrar canais é o correto.
- **Teto de 300 por canal** descarta ~70% dos 46k Shorts e, por manter os mais recentes,
  empurra canais prolíficos para o teste. Peso `300/n_canal` em vez de truncar preservaria a
  intenção sem jogar dado fora. Decisão de regra fixa: humana.

## O que vale tentar (ganho esperado × facilidade)

| # | o quê | onde | por quê | esforço | como medir |
|---|---|---|---|---|---|
| 1 | padronizar `y` pela idade com a curva de crescimento e tirar `log_idade_dias` das features | `modelagem.montar_base`, `historico`, `features_de_metadados` | tira o proxy de calendário; views medidos no teste deixam de estar "verdes"; A vs B honesto | 3 h | MAE e cobertura de views no teste |
| 2 | validação em janelas rolantes (cortes em 60/70/80% do treino, média como objetivo) | `experimentos.avaliar`, `otimizacao.testar` | a validação atual não prevê o teste (historico +1,1% → +6,0%; móvel empate → +11,8%) | 3 h; 2–3× CPU | correlação de postos val × teste nas receitas já rodadas |
| 3 | bootstrap por canal + métrica de largura média da faixa | `modelagem.confianca_pareada`, `Resultado` | confiança honesta; cobertura sozinha se atinge alargando `k` | 1–2 h | refazer a confiança das tentativas |
| 4 | âncora móvel encolhida (`n/10·m10 + (1−n/10)·fixa`) ou mediana móvel | `experimentos._ancora_log` | com `hist_n` < 10 um viral recente desloca o alvo | 2 h | MAE nos canais com poucos vídeos (1 experimento) |
| 5 | texto por projeção supervisionada (ridge 384-d → resíduo, out-of-fold) em vez de PCA-16 | `experimentos._montar_x` | PCA preserva variância, não sinal (texto −0,1%) | 4–5 h | validação n≈2,1k e A vs B |
| 6 | `canal_id` categórico com `cat_smooth`; histórico do outro alvo (views ao prever likes) | `features_de_metadados`, `historico_do_banco` | canal já é memorizado por constantes; `min_data_in_leaf=10` vencer sugere isso | 2 h | validação |
| 7 | controle só com q50 e cache por conjunto de linhas | `experimentos.avaliar` | −40% de CPU por ciclo, paga o item 2 | 1 h | tempo do `otimizar` |
| 8 | histórico ao vivo com `observacoes` | `servicos._historico_do_novo` | números frescos em vez da coleta | 1 h | `acompanhamentos` (cobertura, erro mediano) |

## O que não vale

- Ensembles ou stacking de GBMs: +1–2% esperado, abaixo do piso de ruído do teste.
- Redes ou fine-tuning de embeddings: ~13k linhas pós-teto; gancho com 22 linhas na validação.
- Mais busca de hiperparâmetros: a tabela da busca mostra ±1%; espaço saturado.
- Peso por recência: medido, não ajuda (a validação não vê a deriva).
- LambdaRank para A vs B: não há sinal intra-canal a ordenar (metadados 58,5%, histórico não
  soma) e perderia a magnitude calibrada.
- Conformal mais sofisticado: cobertura já em 80%; sem métrica de largura não dá para saber
  se há o que ganhar (item 3 primeiro).

## Além do modelo

- Mais canais é a única alavanca do teto (A vs B ~58%).
- ~2,9k ganchos para a camada de gancho virar testável.
- Medir o efeito do `proximo_passo` no agente real: setor novo duas vezes, com e sem a tool.
