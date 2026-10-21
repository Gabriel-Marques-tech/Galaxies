# 07 · Testes: como rodar e o que cada um prova

## Como rodar

```bash
uv run pytest                          # tudo (~8 min: treina e otimiza de verdade)
uv run pytest -m "not lento"           # ciclo rápido (~2 min)
uv run pytest tests/test_coleta.py     # um arquivo
uv run pytest tests/test_analisar.py -k "schema"        # testes cujo nome contém a palavra
uv run pytest -x                       # para na primeira falha
uv run pytest --lf                     # só os que falharam da última vez
uv run pytest -q --durations=10        # os 10 mais lentos
uv run pytest -s tests/test_mcp.py     # mostra prints
```

Não rode a suíte completa com um job pesado em paralelo (Laya, otimização): disputa CPU e
já derrubou a máquina uma vez.

Tudo roda sobre **falsos** (`tests/fakes.py`): `YouTubeFalso` (canais e vídeos em memória,
conta chamadas), `ExtratorFalso`, `DescritorFalso`, `TranscritorFalso`, `EmbedderFalso`,
`TextoFalso`, `JevFalso` (choice na 1ª opção, score no meio, noul 0,8; registra as perguntas
feitas). `base_com_sinal(canais, por_canal)` gera uma base com padrões aprendíveis (título
com pergunta rende mais, etc.), de jan/2025 a set/2026. Cada teste cria um projeto em
`tmp_path`: nada toca `data/`. `tests/conftest.py` baixa `MIN_VALIDACAO` para 10 porque as
bases falsas são pequenas.

## O que cada arquivo prova

| arquivo | prova que | marcador |
|---|---|---|
| `test_projeto.py` | criar/ler projeto, config inválida recusada, nome repetido não sobrescreve, nome com caminho não sai da raiz, viral padrão 3× | |
| `test_coleta.py` | só Shorts dos canais-semente; paginação completa e cota registrada; canal inexistente/erro de rede não derruba o lote; `adicionar_canal`; descoberta para no teto de cota; `desde` para a paginação; retomar pula coletados | |
| `test_camada_bruta.py` | gancho guarda descrição, fala e embedding; 2ª rodada não chama VLM/Whisper de novo; falha isolada registrada; limite por canal espalha no tempo; `canais` e `desde` restringem; cota do Gemini esgotada para o lote sem marcar falha | |
| `test_atributos.py` | 15 atributos padrão; respostas viram features numéricas; malformado/repetido/>30 recusados; atributo novo só pergunta o que mudou; mudar o texto invalida a resposta antiga | |
| `test_jev.py` | schema JSON por tipo; conversão para o formato do Jev; rótulo fora das opções recusado | |
| `test_titulo.py` | Laya responde título para todos os vídeos e só o que falta; camada `titulo` treina e a análise pergunta ao extrator rápido; sem respostas, o erro diz o que rodar | |
| `test_historico.py` | histórico só usa vídeos publicados 7+ dias antes (sem vazamento); ritmo e tendência; canais não se misturam | |
| `test_treino.py` | diagnóstico usa split temporal e supera o baseline do canal | |
| `test_experimentos.py` | receita, hipótese e métricas nas mesmas linhas; atributos só em vídeos com resposta e controle medido; PCA salvo; receita fora dos limites recusada; automático promove, cientista exige aprovação, rejeição com nota; aposentar o anterior; modelo com atributos exige vídeo; ciclo otimiza na validação e testa só a escolhida; extratores convivem; histórico e texto cobrem todos; faixa calibrada e cobertura medida; chances e sugestões; orçamento e trace da busca; relatório reproduz o banco; **não promove receita que só brilha na validação** | lento |
| `test_ancora.py` | âncora móvel treina, prevê e compara com o mesmo baseline/controle; exige histórico | |
| `test_crescimento.py` | reobservação semeia a coleta e acrescenta observações; curva por faixa; curva vazia não muda nada; `fator` integra só faixas cobertas; timeline recua pela curva; faixa provável dentro da quase certa; peso por recência e bootstrap; tentativa sem poder marcada; rotina reobserva, coleta e só reotimiza quando a base cresce | parte lento |
| `test_analisar.py` | timeline ordenada e não decrescente; saída válida contra o schema; previsão reage ao que o modelo aprendeu; canal fora da base recusado; sem treino pede treinar; vídeo com arquivo roda gancho e atributos sem sujar a base; sugestões; comparar; acerto em pares | |
| `test_acompanhar.py` | acompanhar liga análise a vídeo publicado; atualizar busca de novo e compara; exige run de `analisar`; faixa provável dentro da quase certa | |
| `test_erros.py` | reprocessar limpa e refaz; excluído não entra em processamento nem treino; `erros` mostra piores, segmentos e falhas | |
| `test_humano.py` | amostra com contexto e resposta; concordância; não repete revisados; valor inválido recusado; dado ruim exclui, padrão vira pista; **discordância entre extratores vai primeiro** | lento |
| `test_roadmap.py` | `proximo_passo` segue coletar → texto → títulos → otimizar; com modelo em dia pede reobservação e depois fica ambíguo (ganchos) | |
| `test_trace.py` | serviço vira run com etapas; `andamento.json` existe durante o run e some no fim | |
| `test_mcp.py` | tools expostas; loop criar → coletar → treinar → avaliar → analisar pelo MCP; erro de domínio volta como mensagem; job que falha guarda o erro | |
| `test_api.py` | rotas chegam nos serviços e igualam o MCP; humano aprova e anota; erro vira HTTP legível; visão geral, canais e troca de modo | |
| `test_youtube_api.py` | parse de duração ISO 8601 | |

## O que você precisa testar à mão (os falsos não cobrem)

**Integrações reais** (uma vez por ambiente, com `.env` preenchido):

1. `uv run python -m galaxies coletar <projeto-teste>` com 1 canal pequeno: vídeos no banco,
   cota registrada (`cota`).
2. `processar-ganchos --limite-por-canal 2`: frames na pasta, descrição do Gemini em
   português, transcrição, sem `falhas`.
3. `calcular-atributos`: respostas do LLM com `extrator` igual ao `ATRIBUTOS_MODELO`.
4. `calcular-titulos --limite 50` e `calcular-texto`: contagens em `respostas` e
   `texto_embedding`.
5. `observar-recentes` e `crescimento`: cota ~1 por 50 vídeos.

**Modelo com dados reais** (`moda-beleza`):

6. `otimizar --alvo likes`: tabela de tentativas com "ganho real"/"indistinguível"/"sem
   poder estatístico"; escolhida testada uma vez; `promovido` só se passar na trava.
7. `relatorio moda-beleza > docs/avaliacao.md`: números batem com `experimentos`.
8. Análise de um vídeo publicado há 2–7 dias (título real, canal da base) → `acompanhar` →
   `acompanhamentos`: real dentro da faixa quase certa na maioria dos casos.

**UI** (http://127.0.0.1:5173, API em :8000):

9. Projetos: feed rola um por vez; arrastar para o lado abre "Novo projeto"; insights do
   projeto em foco mudam ao rolar.
10. Início: cards (Shorts, ganchos, modelo ativo com "+X% mais preciso", em produção, curva
    de crescimento), card "Próximo passo", troca de modo com onda e cor (azul ↔ roxo).
11. Analisar: Short 9:16 centralizado; upload ou link; resultado com mediana, faixa provável
    e quase certa (texto e duas bandas no gráfico), chances, fatores, sugestões; "Publiquei"
    pede o id e cria o acompanhamento.
12. Modelos: vista Simplificada e Avançada; rótulo "âncora móvel"; em modo cientista, aprovar
    e rejeitar funcionam e mudam o status.
13. Revisão: casos com "extratores discordam" aparecem primeiro, com as duas respostas;
    responder tira o cartão; concordância atualiza.
14. Erros: triagem "dado ruim" exclui (contagem de Shorts cai no Início), "padrão" vira nota.
15. Trace: linha do tempo horizontal; clicar num nó abre as etapas.
16. Banner de andamento aparece enquanto um job roda pela CLI/MCP e some ao terminar.

**Agente (Claude Code no repo, MCP)**:

17. "O que o projeto moda-beleza precisa agora?" → ele chama `proximo_passo` e segue.
18. Setor novo do zero em modo cientista: criar → coletar → texto → títulos → otimizar;
    a promoção deve ficar aguardando você na UI.
19. Pedir uma hipótese específica ("testa título + histórico com âncora móvel"): ele usa
    `experimentar` com a hipótese escrita e lê o resultado contra baseline e controle.

Se algo desses 19 falhar, abra uma issue com o comando, a saída e o `trace` do run.
