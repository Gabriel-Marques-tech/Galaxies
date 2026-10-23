# Deck "Stars" — apresentação final (23/10/2026)

## Intenção

Dez minutos na Google, plateia mista (liderança da liga, Google, Galaxies). Objetivo: a
plateia sair lembrando "o calouro do Inteli fez um projeto diferente". O produto é a
ideia: **um cientista de dados portátil** (servidor MCP) que qualquer LLM pluga e que monta
um modelo de previsão de Shorts por setor em ~50 min, dentro de regras que o impedem de se
enganar, e segue iterando. A UI é a janela para mostrar o rastro do que o agente fez.

## Decisões do apresentador

- Nome: **Stars**. Tagline: "um cientista de dados na palma da mão". Logo: a galáxia de
  pontos já existente (`ui/public/logo.svg`), azul → roxo.
- Estética: Gemini (gradiente #4285F4 → #9B72CB → #D96570 com borda de ataque nítida,
  formas circulares, fundo escuro, brilho suave) com a calma tipográfica da OpenAI (texto
  grande, um pensamento por tela, sem bullets). Fonte Google Sans/Inter com fallback.
- Abertura: **gancho invertido**. Números de resultado sobem na tela, depois "Nenhum desses
  modelos fui eu que montei. Bom, pelo menos não 100%."
- Tour de features organizado pelo diferencial (ciclo iterativo, o que a análise faz com um
  vídeo, resultados); **sem** slide de limitações (fica reserva para perguntas) e **sem**
  legendas técnicas; a técnica aparece ao vivo quando o apresentador quiser.
- Demo estilo lançamento (ref.: "OpenAI apresenta modelo Astra", 1:18): a tela do Gemini CLI
  flutua num palco 3D, a câmera entra no prompt, corta para as tool calls, inclina e afasta
  para a UI aparecer. Conteúdo: **replay de uma sessão real** (texto e timing reais), nunca
  respostas encenadas. Setor da sessão: culinária/receitas (melhor acerto esperado).
- UI nos slides: iframe ao vivo (API em :8000, UI em :5173) com **réplica gravada de reserva**
  (HTML autocontido com os dados reais embutidos), como no deck da Cocamar.
- Fecho: "Gabriel Marques".
- Números: nunca inflados; a forma de contar pode impactar (erro típico 2,4× → 1,9×; 4
  setores; faixa de 80% que cumpre 80% em saúde e automotivo).

## Estrutura (10 min)

1. Gancho invertido (60 s): números subindo; a frase.
2. A ideia (60 s): Stars, tagline, "pluga no seu LLM", 50 minutos por setor.
3. Como ele trabalha (3 min): demo 3D com o replay do Gemini CLI; depois UI: busca do agente,
   trava, diagnóstico que separou fitness e saúde.
4. O que faz com um vídeo (2 min, ao vivo): Short real, veredito, faixas, gancho lido,
   "Publiquei", previsto × real, curva de crescimento.
5. Os números com contexto (90 s): tabela dos setores.
6. Diferente em quê (60 s): "não é um modelo; é quem faz os modelos, e se vigia". Nome.

## Como é feito

- `apresentacao/index.html`: arquivo único (CSS e JS inline; fontes do Google Fonts com
  fallback local), navegação por teclado (←/→, Espaço), `data-in` para entradas animadas,
  contador de números, palco 3D com keyframes de câmera sincronizados com a digitação.
- `apresentacao/replica.html`: réplica das telas (Projetos, Início, Modelos, Analisar,
  Vídeos analisados) com dados reais embutidos (JSON da API capturado na montagem) e
  cliques roteirizados; o deck usa o iframe ao vivo e cai na réplica se a API não responder.
- Sessão do Gemini CLI: capturada em texto (`apresentacao/sessao-gemini.json`) a partir de
  uma execução real; o replay digita o prompt e mostra as tool calls e a resposta com os
  tempos reais comprimidos.

## Fora de escopo

Vídeo gravado em MP4; slides sobre limitações (ficam no roteiro em
docs/apresentacao-roteiro.md); integração com Gemini CLI além do MCP já configurado.
