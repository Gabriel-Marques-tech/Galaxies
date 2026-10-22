# 03 · Modelagem

## `modelagem.py` — base, split, features, modelo e métricas

**Base** (`montar_base(banco, alvo)`): junta `videos` e `canais`, tira excluídos, aplica o
teto de 300 por canal (mais recentes), calcula `idade_dias = coletado_em − publicado_em` e
`log_y = log1p(alvo)`. Ordenada por `publicado_em`.

**Split** (`dividir`): corte no quantil 80% de `publicado_em`; teste = depois do corte, com
`idade_dias ≥ 7` e canal presente no treino. Devolve `Split` com datas e tamanhos.

**Âncoras por canal** (`estatisticas_dos_canais(treino)`): mediana do alvo, média do log,
posts por 30 dias. Calculadas **só no treino**.

**Features de metadados** (`features_de_metadados`): duração, hora e dia da semana (fuso
São Paulo), `log_idade_dias`, caracteres/palavras/pergunta/número/exclamação/maiúsculas/
emojis do título, hashtags, tamanho da descrição, nº de tags, `log_inscritos`,
`log_mediana_canal`, `posts_por_30d`, código do setor (categorias fixadas pelo treino).

**Histórico do canal** (`historico`, `historico_do_banco`): para cada vídeo, o momento do
canal **antes** dele, sem olhar o futuro: média e desvio do log dos últimos 10 e 30 vídeos
publicados pelo menos `DEFASAGEM_HISTORICO_DIAS = 7` antes (as contagens deles já estavam
visíveis), tendência (10 − 30), nº elegíveis, dias desde o último post, posts nos 7 dias
anteriores. Usa somas acumuladas: O(n) por canal. Vale para todos os vídeos (não só os com
gancho). `hist_rel_10 = hist_media_10 − log_mediana_canal` entra em `_montar_x`.

**Modelo** (`treinar_quantis(x, y, params, rodadas, peso)`): três LightGBM com objetivo
quantílico (`QUANTIS = 0.1, 0.5, 0.9`), parâmetros base em `PARAMS_LGB` (seed fixa; a
variação na 3ª casa vem do multithread). `peso_por_recencia(datas, meia_vida)` dá peso 1 ao
mais recente e metade a cada meia-vida (não ajudou nesta base).

**Métricas** (`medir(pred_log, teste)` → `Metricas`): `mae` no log (erro típico = e^MAE
vezes), `spearman_no_canal` (média dos canais com ≥ `MIN_VIDEOS_CANAL_SPEARMAN`),
`acerto_pares` (A vs B: pares do mesmo canal, acaso = 50%), `n`.
`confianca_pareada(erros_modelo, erros_controle)`: bootstrap pareado (1000 reamostras),
fração em que o MAE do modelo fica abaixo do controle. `faixa_50(lo, mid, hi)`: q25/q75 a
partir da faixa calibrada (razão z(0,75)/z(0,9) = 0,5263 de cada metade).

**Diagnóstico** (`diagnosticar`): piores previsões e MAE por segmento (canal, setor, faixa
de idade). Embeddings: `reduzir_embeddings` ajusta um PCA (`DIMENSOES_SIGLIP = 16`) só nas
linhas de ajuste. `salvar_modelos`/`carregar_modelos`: boosters + `meta.json`.

## `experimentos.py` — a bancada

**`Params`**: `num_leaves` (4–127), `learning_rate` (0,005–0,3), `rodadas` (20–2000),
`min_data_in_leaf` (5–200), `meia_vida_dias` (30–3000 ou `None`). Limites via Pydantic: o
agente não sai do seguro.

**`Receita`**: `camadas` (sempre inclui `metadados`), `atributos` (ids ou `None` = todos),
`extrator` (`None` = o configurado), `params`, `ancora` (`mediana_canal` ou `movel`;
`movel` exige `historico`). `RECEITAS_PADRAO`: metadados, historico, texto, titulo,
movel, historico+texto, historico+texto+multimodal, completo.

**`avaliar(banco, alvo, receita, definicoes, em, cache, min_teste)`** é o coração:

1. Base, split (`em="validacao"` divide o treino de novo), âncoras do treino.
2. `_camadas_extras`: DataFrames das camadas pedidas, indexados como a base, e a máscara
   `tem` das linhas que têm todas (multimodal/atributos cobrem só vídeos com gancho; texto e
   título exigem a resposta; histórico vale para todos, com NaN onde não há passado).
3. Exige `MIN_TREINO = 50` e `MIN_TESTE = 10`; com `min_teste` (a busca passa 300), lança
   `PoucoPoder` **antes de treinar**: a tentativa é marcada "sem poder estatístico" com a
   estimativa de quantos vídeos faltam.
4. `_montar_x`: metadados + histórico (+ `hist_rel_10`) + PCA de embeddings (ajustado só no
   treino) + colunas de título + colunas de atributos.
5. Alvo: `y = log_y − _ancora_log(...)`. Fixa: `log1p(mediana do canal)`. Móvel:
   `hist_media_10` (defasada 7 dias), caindo na fixa onde não há passado.
6. Treina a receita (com peso por recência se houver) e o **controle** (só metadados,
   `Params()`, alvo fixo) nas mesmas linhas.
7. Previsão no teste: `relativo + âncora da linha`. Baseline: mediana do canal.
8. `_calibrar`: conformal. Treina sem os últimos 20% do treino (`FRACAO_CALIBRACAO`), mede
   nesse fim o fator `k` que a faixa q10–q90 precisa alargar para conter `COBERTURA_ALVO =
   0.8`. `cobertura_bruta` (k=1), `cobertura_80` (k) e `cobertura_50` (faixa derivada).
9. `Resultado`: n, colunas, baseline, controle, modelo, ganho, melhora e confiança sobre o
   controle, coberturas, `calibracao`, `ganho_por_atributo` (permutação), piores, segmentos,
   `sugestoes` (`sugerir`: heurísticas em texto para o agente).

**`treinar`** = `avaliar` no teste + `_modelo_final`: retreina em todas as linhas com as
camadas da receita, salva boosters e `meta.json` (receita, setores, calibração, PCAs,
atributos e extrator, `titulo`, colunas, âncoras dos canais, n). `Experimento` guarda
receita, hipótese, resultado, status (`candidato`, `aguardando_aprovacao`, `ativo`,
`aposentado`, `rejeitado`) e `nota_humana`.

**Trava** (`motivo_para_nao_promover(exp, ativo)`), nesta ordem: ganho ≤ 0; camadas extras
com melhora < `MARGEM_SOBRE_CONTROLE = 1%`; confiança < `CONFIANCA_MINIMA = 90%`; ganho no
teste que não supera o do ativo (uma troca lateral não vale o risco; aprendido quando o
`otimizar` substituiu −24,5% por −23,8% dentro de uma tolerância de 2 pontos). `ativar` aposenta o anterior.

## `otimizacao.py` — a busca do agente

`otimizar(banco, alvo, definicoes, ex, orcamento=16, paciencia=6)`:

1. `disponiveis`: quais camadas têm dados (texto, multimodal, título, atributos por extrator).
2. Avalia as `RECEITAS_PADRAO` possíveis **na validação** (atributos: uma por extrator).
3. Busca local a partir da melhor: `_mutar` liga/desliga uma camada, sorteia um
   hiperparâmetro (inclui `meia_vida_dias`), remove o atributo que mais atrapalha, troca o
   extrator ou alterna a âncora. Para no orçamento ou após `paciencia` tentativas sem
   melhora > `MELHORA_MINIMA = 0,2%`.
4. `_melhor`: entre as com ganho > 0, prefere as de confiança ≥ `CONFIANCA = 0,9` ("ganho
   real"); em empate dentro do ruído, a receita mais simples. Tentativas com menos de
   `MIN_VALIDACAO = 300` linhas não contam.
5. Cada tentativa vira uma etapa do trace (`origem`, receita, objetivo, confiança, n, erro).

O serviço `otimizar` então roda `experimentar` com a escolhida (teste, uma vez), aplica a
trava e, no modo automático, promove. `ciclo_automatico` é isso com a checagem do modo.

Limites conhecidos: a validação é o fim do treino; uma deriva que começa depois dela (caso
desta base) não aparece na busca. A âncora móvel foi encontrada por diagnóstico, não pela
busca, e está registrada assim na hipótese.

## `analise.py` — prever um vídeo novo

`prever(modelos, meta, linha, limite_viral, embedding, respostas, historico, texto, curva,
idade_minima, titulo)`:

- Monta uma linha por dia da timeline (`DIAS_DA_TIMELINE = 1, 3, 7, 14, 30`) com a idade
  fixada em `max(dia, idade_minima)`; `features` reproduz exatamente as colunas do modelo
  (PCA com média e componentes salvos, atributos, título).
- Quantis relativos (ordenados). Se a receita usa âncora móvel, soma o deslocamento
  `hist_media_10 − log1p(mediana)` para voltar à referência fixa, que é a das chances.
- Abaixo de `idade_minima`, recua pela `Curva.fator`. Acumula máximo: a timeline nunca
  decresce.
- Faixa calibrada com `k`; `faixa_50` dentro dela. `PontoTimeline` com q10/q25/q50/q75/q90
  absolutos.
- Chances em 30 dias (`DIAS_DO_VIRAL`): passar a mediana, dobrar, viralizar (`limite_viral`
  ×). Normal no log com σ da faixa calibrada (`_prob_acima`).
- Fatores: contribuições SHAP (`pred_contrib`) do booster da mediana aos 7 dias, sem
  `log_idade_dias`.
- `sugerir`: para cada alavanca que o criador controla (`_alavancas`: hora, dia, duração,
  pergunta/número/emoji no título, atributos de gancho quando houver), a alternativa que
  mais aumenta a chance de viralizar; devolve mudança, previsto em 7 dias, ganho, p_viral e
  delta. Associação aprendida, não causa.

`Analise` (Pydantic) é o que sai do serviço: run_id, experimento, mediana do canal,
previsão 7d, timeline, chances, fatores, sugestões, gancho analisado e atributos quando
houver vídeo. `comparar` roda duas análises e aponta a melhor em 7 dias.

## `acompanhamento.py` — previsto × real em produção

`registrar(video, run, canal, alvo, publicado_em, timeline)` guarda a timeline prevista;
`observar(video)` grava uma observação (idade, likes, views). `listar` interpola a timeline
no log para a idade de cada observação (`_interpolar`) e compara: dentro da faixa de 80%,
dentro da provável (50%), erro em log. Agrega `cobertura`, `cobertura_50`, `erro_mediano`.

## `treino.py` — diagnóstico por ablação

`treinar(banco, alvo)`: no split fixo, avalia metadados, +histórico, +texto, +multimodal,
+atributos e mede o ganho por permutação de cada atributo. Serve para o agente entender a
base antes de desenhar receitas; não promove nada.

## `relatorio.py` — `docs/avaliacao.md`

`gerar(projeto, config, resumo, exps, otimizacoes, curvas, idade_minima)`: base, regras
fixas, por alvo (modelo ativo com números e hipótese; tabela de todos os experimentos),
tabela da busca (origem, camadas, melhora, "ganho real?" ou "sem poder estatístico", n),
crescimento observado, limitações. Reproduzível com `uv run python -m galaxies relatorio
<projeto> > docs/avaliacao.md`.
