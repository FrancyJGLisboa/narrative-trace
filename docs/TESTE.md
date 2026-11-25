# Roteiro de teste: a história ajuda iniciantes a entender?

Uma página. Teste pequeno e exploratório. Ele diz se vale insistir. Ele não prova nada com certeza.

## Pergunta
Um iniciante que lê a história do Narrative Trace explica melhor o que o agente fez do que quem lê só o log?

## Hipótese (escrita antes de ver dados)
A pessoa acerta pelo menos 1 ponto a mais (de 5) com a história do que com o log.

## Quem
- 6 pessoas que não programam, ou programam há menos de 1 ano. Se não houver 6, use 4.
- Ninguém que já viu o projeto.
- Peça consentimento. As respostas ficam só na sua máquina.

## O que cada pessoa lê
Duas sessões gravadas do agente, com o mesmo nível de dificuldade. Cada uma tem uma edição e uma falha no meio.
- **Sessão 1** e **Sessão 2**: grave com Claude Code numa pasta de teste. Congele os arquivos antes do teste.
- **Condição H (história):** o `story.md` da sessão, com notas e perguntas apagadas das últimas linhas do bloco "Confira se entendeu".
- **Condição L (log):** a lista de eventos do `trace.jsonl` (número, ferramenta, alvo, status), sem texto de narração.

## Como distribuir (cruzado)
| Grupo | Primeira leitura | Segunda leitura |
|---|---|---|
| A (3 pessoas) | Sessão 1 com H | Sessão 2 com L |
| B (3 pessoas) | Sessão 1 com L | Sessão 2 com H |

Sorteie quem vai para A ou B. Metade lê cada sessão com cada condição, então a dificuldade da sessão não decide o resultado.

## Passo a passo (cerca de 40 minutos por pessoa)
1. 3 min: explique só "leia e depois responda sem olhar". Não explique o projeto.
2. 8 min: a pessoa lê a primeira sessão. Sem pesquisar, sem perguntar.
3. 8 min: ela responde às 5 perguntas, por escrito, sem o texto na tela. Antes de cada resposta, ela marca a certeza (1 chute, 2 talvez, 3 certeza).
4. 3 min: pausa.
5. Repita os passos 2 e 3 com a segunda sessão e a outra condição.
6. 5 min: 2 perguntas abertas: "O que ajudou?" e "O que atrapalhou?"
7. **7 dias depois:** 10 minutos. A pessoa responde de novo às 5 perguntas da primeira sessão, sem reler.

## As 5 perguntas (iguais nas duas sessões, com o nome do arquivo trocado)
1. O que estava errado no código?
2. O que o agente trocou, antes e depois?
3. Como o agente conferiu se funcionou? Passou?
4. O que deu errado pelo caminho?
5. O que você conferiria antes de confiar neste resultado?

**Pontuação:** 0 ou 1 por pergunta, pela chave de respostas que você escreve **antes** do teste. Quem corrige não sabe a condição: embaralhe as folhas e esconda o rótulo.

## O que medir
| Medida | Como | Papel |
|---|---|---|
| Acertos (de 5) | chave de respostas | principal |
| Certeza 3 e errou | contagem por pessoa | secundária: o equívoco escondido |
| Acertos após 7 dias | mesmas 5 perguntas | secundária: o que ficou |
| Tempo de leitura | cronômetro | só para contexto |

## Regra de decisão (minha proposta, ajuste antes de começar e não mude depois)
- **Seguir em frente:** diferença média de acertos (H menos L) de pelo menos 1 ponto, e no máximo 1 pessoa pior com H.
- **Refazer o produto:** diferença entre 0 e 1 ponto. Leia as respostas abertas e mude o que atrapalhou.
- **Parar:** H igual ou pior que L.

## Como ler o resultado
- Com 6 pessoas, um resultado bom é um sinal, não uma prova. Se a diferença for de 1 ponto, repita com 20 pessoas antes de dizer que funciona.
- Se H ajudou na semana 0 e não ajudou aos 7 dias, a história é boa para ler e fraca para ensinar.

## Riscos que o desenho não cobre
- O validador e as notas foram escritos por quem fez o projeto, então a história pode estar "afinada" para essas duas sessões. Use sessões que ninguém ajustou.
- A condição L é um log duro. Um resumo simples do próprio agente seria um adversário mais justo. Se der tempo, rode um terceiro grupo com o texto final do agente.
- Pessoas que sabem que estão num teste leem com mais atenção.

## Folha de registro (uma linha por pessoa e leitura)
`pessoa, grupo, sessao, condicao, p1, p2, p3, p4, p5, certeza3_errou, minutos, ret7_p1..p5, ajudou, atrapalhou`

## Antes de começar (30 minutos)
1. Grave as duas sessões e congele as pastas.
2. Escreva a chave de respostas.
3. Gere os dois materiais (`story.md` e a lista de eventos) e confira que um não contém o outro.
4. Escreva a regra de decisão acima neste arquivo e faça um commit. Só então recrute.
