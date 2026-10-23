# Stars (Galaxies) · arquitetura em uma conversa

Guia para explicar a arquitetura de cabeça, do mais geral ao mais específico. A versão
completa, módulo por módulo, está em `docs/tecnico/01` a `08`.

## A frase

Stars é um **servidor MCP** que qualquer LLM pluga (Gemini CLI, Claude Code, Codex). Por
trás dele existe um **framework de ciência de dados com regras fixas**: coleta, camadas de
features, busca de receitas, teste uma vez, trava de promoção, operação diária. O LLM decide
*o que tentar*; o framework decide *se valeu* e nunca deixa o LLM mexer na régua.

Quem faz o quê:

| quem | faz | não faz |
|---|---|---|
| LLM (Gemini/Claude) | escolhe o próximo passo, escreve hipóteses, cria atributos novos, explica ao humano | não mede, não decide promoção, não altera split/baseline/métrica |
| Framework (Python) | coleta, features, treino, validação, teste, calibração, promoção, trace, rotina | não "pensa" em linguagem natural; só regras e números |
| Humano | aprova promoções no modo Data Scientist, revisa atributos, anota erros | não precisa saber de ML para operar |

## Cinco camadas, de fora para dentro

```
Interfaces   MCP (stdio, ~40 tools)  ·  API FastAPI → UI React  ·  CLI
                    │ todas chamam a mesma coisa:
Serviços     servicos.Framework  (uma classe; cada método vira um "run" com trace)
                    │
Núcleo       coleta · camada_bruta · atributos · vizinhos · modelagem · experimentos
             otimizacao · analise · acompanhamento · crescimento · diagnostico · humano
                    │ só fala com o mundo por contratos (portas.py)
Adaptadores  YouTube Data API · yt-dlp+ffmpeg · Gemini · Whisper · SigLIP · MiniLM
             LLM (Workers AI) · Laya · Jev     ← todos trocáveis, todos gratuitos
                    │
Dados        um DuckDB por projeto (data/projetos/<setor>/galaxies.duckdb)
             + modelos/ (LightGBM q10/q50/q90 + meta.json) + uploads/
```

Regra de dependência: interfaces só conhecem `Framework`; o núcleo não sabe que existe
MCP ou UI; adaptadores só implementam portas. Trocar Gemini por outro descritor de imagem é
escrever um adaptador.

## O fluxo de um setor (os "50 minutos")

1. **criar_projeto** → DuckDB novo. `descobrir_canais` (busca do YouTube) → `adicionar_canal`
   → `coletar`: só Shorts (vertical, ≤ 180 s), metadados e contagens. Custo em unidades de
   cota, registrado.
2. **Camadas baratas para todos os vídeos**: `calcular_texto` (embedding MiniLM de título e
   descrição) e `calcular_titulos` (perguntas de título, Laya local).
3. **Camadas caras só para um subconjunto**: `processar_ganchos` baixa os 5 primeiros
   segundos, tira frames (Gemini descreve, Whisper transcreve, SigLIP embute);
   `calcular_atributos` faz o LLM responder 15 perguntas tipadas sobre o gancho. Modo leve:
   frames + SigLIP, e `rotular_vizinhos` (kNN) copia os rótulos dos ganchos que o LLM já leu.
4. **otimizar**: busca de receitas (`{camadas, atributos, extrator, params, âncora}`) na
   **validação**; só a vencedora vai ao **teste**, uma vez. Cada tentativa é comparada com o
   **baseline** (média do canal) e com um **controle** (só metadados) nas mesmas linhas.
5. **Trava de promoção**: ganho > 0; camadas extras precisam de ≥ 1% sobre o controle com
   confiança ≥ 90% (bootstrap pareado); só substitui o ativo quem o supera no teste.
6. **analisar**: um vídeo novo entra pela mesma régua: mediana, faixa de 50% e de 80%,
   timeline 1/3/7/14/30 dias, chances, fatores (SHAP), sugestões.
7. **Operação**: `acompanhar` liga a análise ao vídeo publicado; `observar_recentes` reobserva
   todo dia (curva de crescimento); `proximo_passo` e `diagnostico` dizem o que o estado do
   projeto pede; `rotina` empacota o dia.

## O modelo em si (se perguntarem)

- LightGBM quantílico, três modelos (q10, q50, q90), alvo `log((y+1)/(âncora+1))`: o vídeo é
  previsto **em relação ao próprio canal**, não em valor absoluto. Âncora móvel = média dos
  últimos 10 vídeos do canal, defasada 7 dias (segue o momento do canal).
- Split temporal: 20% mais recentes = teste, só vídeos com 7+ dias. Validação = fim do treino.
- Calibração conformal da faixa de 80% na validação; a de 50% é derivada.
- Métricas: MAE no log (vira "erro típico ×"), acerto A vs B em pares do mesmo canal,
  cobertura real das faixas. Teto de 300 vídeos por canal.

## Por que MCP e não uma API própria para o agente

O agente não é nosso. A plateia usa Gemini, Claude ou Codex; o Stars entra como conector.
Toda tool devolve JSON com motivo (`proximo_passo` diz *por quê*), jobs longos devolvem
`job_id` e o agente consulta `status`. A UI React existe porque humano precisa ver; ela usa
a API FastAPI que chama o **mesmo** `Framework`. Nada que a UI mostra é diferente do que o
agente vê.

## Guardrails que valem citar

- Validação separada do teste; teste usado uma vez por receita escolhida.
- "Sem poder estatístico": uma camada com menos de 300 linhas na validação não entra na
  busca, e a mensagem diz quantos vídeos faltam.
- Troca lateral não vale: um candidato com ganho igual não substitui o ativo.
- Diagnóstico com evidência: setor ruidoso (desvio dentro do canal), canais rasos, camada
  incompleta, setores misturados. Foi assim que fitness e saúde viraram dois projetos.
- Explicação só com números das tools; o LLM não inventa valor (a explicação textual da
  análise é montada por template a partir das faixas).
- Trace de cada run: entrada, saída e tempo por etapa; a análise gravada reabre do trace.

## Custos e infra

Tudo gratuito: YouTube Data API (10 mil unidades/dia; 93k Shorts custaram ~14 mil
unidades somadas), AI Studio (Gemini), Workers AI (LLM dos atributos), Whisper, SigLIP, MiniLM
e Laya rodando localmente. Um laptop. Um DuckDB por projeto, sem servidor de banco.

## Respostas prontas

- *"Por que não um modelo só para todos os setores?"* Setores têm ruído e teto diferentes
  (fitness: likes variam muito dentro do canal). Um projeto por setor dá um diagnóstico
  honesto por setor e deixa o agente decidir dividir.
- *"O gancho ajuda?"* Ainda não dá para afirmar: os ganchos processados caem no período de
  teste; a validação tem 22 linhas com gancho (mínimo 300). O framework recusou medir.
- *"58% em A vs B é pouco?"* Acaso é 50%; o teto vem do dado (o que acontece depois de
  publicar o vídeo não carrega). O valor principal é o erro 24% menor que a média do canal e
  a faixa que cumpre o que promete.
- *"Quanto tempo para um setor novo?"* Coleta + texto + títulos + otimizar: cerca de 50 min
  com a cota disponível. Títulos locais para dezenas de milhares de vídeos levam horas
  (foi o gargalo da sessão real do automotivo).
- *"E se o LLM errar?"* Ele só escolhe receitas e escreve hipóteses; a régua é fixa e a
  promoção passa pela trava. No modo Data Scientist, passa também por você.

---

# A arquitetura do agente

O "agente" não é um programa só. São **três níveis de decisão**, do mais livre ao mais
rígido, e cada um só pode fazer o que o de baixo permite.

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1 · LLM (Gemini CLI, Claude Code, Codex)                             │
│   lê as instruções do servidor MCP, chama tools, escreve hipóteses,  │
│   cria atributos, conversa com o humano. Memória: a conversa.        │
├──────────────────────────────────────────────────────────────────────┤
│ 2 · Políticas do framework (código, sem LLM)                         │
│   proximo_passo (regras sobre o estado)  ·  diagnostico (pistas)     │
│   otimizacao (busca local de receitas)   ·  rotina / aplicar_pistas  │
│   Memória: o DuckDB do projeto (runs, experimentos, notas).          │
├──────────────────────────────────────────────────────────────────────┤
│ 3 · Régua fixa (código, imutável para os níveis de cima)             │
│   split temporal · baseline · controle · teste uma vez · bootstrap   │
│   trava de promoção · calibração · trace de tudo                     │
└──────────────────────────────────────────────────────────────────────┘
```

## Nível 1 · o LLM operando por MCP

- **Contrato**: o servidor (`mcp_servidor.py`) expõe ~40 tools com descrição e um texto de
  instruções que o LLM recebe ao conectar: ordem do fluxo, quando pedir `proximo_passo`,
  o que fazer com `pistas`, "nunca invente números". É o único *prompt* do sistema. O
  Gemini CLI tem ainda um `GEMINI.md` curto no repositório com o mesmo recado.
- **Ciclo do LLM**: `proximo_passo` → executa a tool indicada → se devolveu `job_id`, faz
  polling com `status` → lê o resultado (e `pistas`, quando há) → repete. Delibera só quando
  `proximo_passo` responde `certeza = "ambiguo"` (ex.: processar ganchos custa horas e
  Gemini; decisão de custo com o usuário).
- **Jobs**: operações longas rodam numa thread única por servidor (`Jobs`), porque o DuckDB
  de um projeto aceita um escritor só. O LLM nunca fica bloqueado; consulta `status`. Limite
  conhecido: um job longo (títulos de 8 mil vídeos) segura os seguintes na fila. Foi o que
  aconteceu na sessão real do automotivo: o agente esperou, desistiu de esperar e reportou o
  modelo ativo com os números, sem inventar.
- **Respostas das tools**: sempre JSON com motivo. Listas vêm embrulhadas em
  `{"itens": [...], "n": N}` porque o Gemini valida listas cruas como registro.
- **O que o LLM pode criar**: receitas para `experimentar` com uma hipótese escrita;
  atributos novos (`definir_atributos`, perguntas tipadas sobre o gancho); notas de triagem.
  O que ele **não** pode: mudar alvo, split, baseline, métrica ou promover fora da trava.

## Nível 2 · as políticas (o "cérebro de regras")

**`proximo_passo`**: uma cadeia de regras sobre o estado do projeto, na ordem:
sem canais → `descobrir_canais`; sem vídeos → `coletar`; menos de 90% com texto →
`calcular_texto`; menos de 90% com título → `calcular_titulos`; modo cientista com
experimento aguardando → `aguardar_humano`; sem modelo ativo → `otimizar`; vídeos novos
acima do limiar (2% da base, mínimo absoluto) → `otimizar`; reobservação de mais de um dia →
`observar_recentes`; poucos ganchos para a camada ter poder (~2.900) → `manter`, certeza
ambígua, alternativas listadas. Cada resposta traz `motivo` e o `estado` que a justificou.

**`diagnostico`**: olha o dado e devolve pistas tipadas com evidência e ação:
`setor_ruidoso` (desvio do log dentro do canal acima da referência: teto baixo, compare com
o controle), `canais_rasos` (menos de 30 vídeos: excluir ou coletar mais), `camada_incompleta`,
`ganchos_insuficientes` (quantos faltam), `controle_fraco`, `setores_misturados` (um setor
erra mais que outro: dividir o projeto), `alvo_alternativo`, `idade` (vídeos recentes erram
mais), `sem_reobservacao`. Foi `setores_misturados` que separou fitness de saúde.

**`otimizacao.otimizar`** (a busca do agente, sem LLM): parte das receitas padrão (metadados;
+histórico; +texto; +título; completa) e faz **busca local** sobre a melhor: liga ou desliga
uma camada, sorteia um hiperparâmetro, remove o atributo que mais atrapalha, troca o
extrator. Objetivo: melhora do MAE **sobre o controle** na validação. Orçamento de 16 a 18
tentativas, paciência 6 sem melhora; melhora abaixo de 0,2% é ruído; bootstrap pareado com
confiança 90% separa "ganho real" de "indistinguível de acaso"; receita sem 300 linhas na
validação vira "sem poder estatístico: faltam N vídeos". Só a vencedora vai ao teste.

**`rotina`** (o dia): `observar_recentes` → `atualizar_acompanhamentos` → `coletar` só o
que falta → `aplicar_pistas` (as seguras: completar camadas, reobservar, excluir canais
rasos no automático) → se a base cresceu acima do limiar ou o dado mudou, `calcular_texto` e
`otimizar`. No automático promove; no cientista deixa como candidato aguardando.

## Nível 3 · a régua

Detalhada na seção "O modelo em si" e em `docs/tecnico/03`. O ponto para a fala: **nenhum
nível de cima escreve nela**. O LLM não tem tool para mudar split, âncora, métrica ou para
promover ignorando `motivo_para_nao_promover`. Isso é o que permite dizer "ele não se engana"
sem depender do bom comportamento do LLM.

## O humano no laço (modo Data Scientist)

- `promover` no modo cientista cria status `aguardando_aprovacao`; a UI mostra o candidato
  com os números e a comparação com o ativo; o humano aprova ou recusa.
- **Revisão de atributos**: dois extratores (LLM e vizinhos, ou LLM e Laya) discordam → a
  UI mostra o gancho e o humano desempata; a resposta vira dado de treino.
- **Triagem de erros**: os piores erros do modelo com caixa de nota; `notas` volta ao agente
  como pista ("vídeo era um repost", "canal mudou de nicho") e pode virar exclusão ou
  atributo novo.
- Modo visual no deck: a troca de modo no slide não grava nada; na plataforma grava.

## Como o LLM "aprende" entre sessões

Não aprende no sentido de pesos. A memória é o projeto: `runs` e `trace` (o que foi feito e
deu), `experimentos` (o que já foi tentado, com veredito), `buscas` (as tentativas da
otimização com origem), `notas` e `revisoes` (o que o humano disse), `excluidos`. Uma sessão
nova lê isso por `runs`, `experimentos`, `diagnostico`, `notas` e segue de onde parou. É
replicação por estado, não por conversa: por isso qualquer LLM pode operar o mesmo projeto.

## Limites honestos do agente hoje

- Fila de jobs única por servidor: um job local longo atrasa os outros (próximo passo:
  prioridade e estimativa de duração em `proximo_passo`).
- `proximo_passo` recomenda `calcular_titulos` sem estimar o tempo (8 mil vídeos = horas).
- O LLM gratuito disponível hoje (`gemini-3.5-flash-lite`) faz polling demais e às vezes
  desiste cedo; o framework compensa com respostas que sempre trazem o estado.
- O gancho ainda não provou valor no modelo: os ganchos processados caem no teste; a
  validação tem 22 linhas (mínimo 300).

---

# "780 a 15 mil não diz nada": o que a faixa vale e o que não vale

Medido em 23/10 no teste de moda e beleza (3.014 vídeos, modelo ativo `1786c3fd7c`):

- **A faixa de 80% é larga porque o dado é ruidoso**, não porque o modelo é frouxo. Dentro
  de um mesmo canal, likes variam com desvio ~1,0 em log: o mesmo criador oscila 2,7× para
  cima e para baixo sem mudar nada. Uma faixa ingênua ("média do canal ± c") precisa de
  **~10× de largura** para cobrir 80%; a do modelo cobre o mesmo com **~6×**. Metade da
  largura, mesma honestidade. Estreitar além disso seria mentir (a faixa sem calibração
  cobre bem menos que 80%).
- **O valor de decisão não está na faixa; está em três coisas que a faixa sustenta:**
  1. **Veredito "acima / abaixo do normal do canal"**: quando o modelo diz *acima* (q50 ≥
     1,3× a mediana), **81%** dos vídeos ficaram acima da mediana do canal; quando diz
     *abaixo*, só **17%** ficaram acima.
  2. **Chance de viralizar (3× a mediana em 30 dias) é calibrada**: quando ele diz 0–5%,
     viralizam 4%; 5–10% → 8%; 10–20% → 16%; 20–40% → 26%. AUC 0,71 (acaso 0,50). Ele não
     diz "vai viralizar"; diz "este tem 4× mais chance que aquele", e acerta a proporção.
  3. **A vs B no mesmo canal**: 58,9% (acaso 50%).
- **Frase**: "Ninguém prevê o viral de um Short antes de publicar; o que dá para prever, e
  conferir, é a chance. Quando o Stars diz 20%, um em cada quatro viraliza. Quando diz 2%,
  quase nenhum."
