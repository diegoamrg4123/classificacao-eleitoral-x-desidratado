# Classificação textual de publicações do X

Cópia pública desidratada do executor de pesquisa, com o modelo `google/gemma-4-31b-it` via OpenRouter. O modelo foi substituído por pedido de Diego, mantendo dados, contexto, prompt, contrato e parâmetros. Compartilha somente os IDs nativos dos posts: 1.461 na base e 223 na seleção histórica. Não contém textos das publicações, autoria, triagem detalhada, pacotes RAG, respostas de modelo ou credenciais. Não há liberação jurídica implícita para os materiais de terceiros usados no projeto original. Repositório público não significa corpus textual com licença aberta.

## Conteúdo

- `scripts/reclassificar.py`: executor e contrato preservados da cópia de origem.
- `scripts/preparar_insumos.py`: preparação offline de entrada, triagem e RAG autorizados pelo usuário.
- `scripts/exportar_ids.py`: exportação literal e validada de IDs, sem texto ou autoria.
- `dados/desidratados/post_ids_base.txt`: 1.461 IDs únicos, um por linha.
- `dados/desidratados/post_ids_selecionados.txt`: os 223 IDs selecionados, sem rótulos por post.
- `figuras/`: Figura 3 em PNG e SVG, com contagens agregadas da execução.
- `prompts/` e `schemas/`: instruções e schema de classificação.
- `tests/`: testes do contrato e testes sintéticos de preparação/privacidade.
- `dados/privados/`: diretório local ignorado pelo Git, vazio no pacote.
- `resultados/`: diretório local ignorado pelo Git, vazio no pacote.

O snapshot RAG original foi excluído: seus campos de evidência podem conter texto de posts e conteúdo de terceiros, não apropriados para republicação. O executor precisa de pacotes RAG compatíveis fornecidos localmente. Este pacote não promete nem testa reidratação a partir da web, ArcadeDB ou recomposição do corpus. Contexto e resultados privados originais não são reconstruíveis apenas a partir do código.

## Requisitos e preparação local

Python 3.10 ou posterior. A execução do executor usa biblioteca padrão; não foi instalado nenhum pacote. Obtenha legalmente e por canal autorizado um conjunto correspondente de três insumos. Eles podem estar na raiz da pasta ou organizados assim:

```text
insumos-autorizados/
  x__x_posts.csv
  triagem.csv
  contexto-rag.jsonl
```

ou em subpastas `entrada/`, `triagem/` e `rag/` com os nomes acima. Depois:

```bash
python3 scripts/preparar_insumos.py --source /caminho/local/insumos-autorizados
python3 -m unittest discover -s tests -v
python3 scripts/reclassificar.py
```

O preparador copia somente esses três arquivos para `dados/privados/`, atualiza `proveniencia.json` com hashes e executa validações de identidade, integridade e alinhamento. Não altera identificadores: IDs nativos são consumidos como strings literais. A seleção original de 223 em base de 1.461 foi confirmada na origem; o preparador não fabrica os números nem considera qualquer conjunto compatível sem validar os arquivos reais. O preflight precisa terminar com `preflight: ok` e zero chamadas API.

O código preserva a lógica e contrato do executor original, que neste pacote não executou inferência. Para uma futura execução, é necessária autorização explícita para enviar texto privado à nuvem, chave OpenRouter fornecida localmente em `.env` ou variável de ambiente, e revisão humana. Configure `.env` a partir de `.env.example`; nunca compartilhe o arquivo. Requisições usam o modelo fixado no código. Nenhuma chamada cloud foi feita durante a preparação deste pacote.

## Resultados de origem, agregados

A execução vigente de origem usa `google/gemma-4-31b-it` via OpenRouter, mantendo insumos, contexto, prompt, contrato e parâmetros anteriores. A run anterior `20261006T121012788430Z`, com `google/gemma-4-26b-a4b-it`, permanece preservada na origem, separada da nova execução.

A run `20261007T223819272404Z` foi concluída e auditada com 223 selecionados: 69 classificações provisórias, 100 sem categoria, nenhuma resposta rejeitada ao final pelo contrato, sete decisões de contexto insuficiente e 47 abstenções. Foram 224 tentativas de chamada, todas com o modelo solicitado na auditoria local. Os 69 registros classificados somam 69 atribuições primárias e três secundárias, totalizando 72 atribuições. São 66 registros com uma categoria e três com duas. Os resultados e rótulos associados a indivíduos foram deliberadamente excluídos; nenhuma categoria sensível é publicada por ID. Os totais são apenas um registro agregado da run de origem, não resultado reproduzido por esta cópia. A Figura 3 apresenta essa execução.

## Licença e citação

**Todos os direitos reservados, exceto citação.** Permite-se citar ou mencionar este repositório com referência completa. Reprodução, redistribuição, adaptação, uso comercial ou incorporação em conjuntos de dados, sistemas ou modelos exige autorização prévia por escrito do autor. Direitos de terceiros permanecem com seus titulares. Esta licença não afirma que os insumos ou materiais de terceiros estejam liberados juridicamente.

Como citar: GOULART, Diego Amorim. *Classificação textual de publicações do X: pipeline e amostra desidratada*. 2026. Disponível em: https://github.com/diegoamrg4123/classificacao-eleitoral-x-desidratado. Acesso em: data de consulta.

## Escopo e limites

A triagem detalhada, hashes e RAG são recursos externos locais. O processo não recalcula embeddings nem consulta o ArcadeDB. Validação estrutural não comprova acurácia, fatos ou enquadramento jurídico. Ausência de categoria não é um negativo confirmado; toda atribuição exige revisão humana.

## Reidratação e reprodução

IDs não são textos nem anonimizam as publicações: permitem localizá-las. Para recuperar conteúdos, cada pesquisador deve usar acesso próprio autorizado à API do X, sujeito às regras e custos vigentes. Posts excluídos, protegidos ou indisponíveis podem não ser recuperados. Nenhuma reidratação online foi executada ou testada neste pacote.

A recuperação dos textos, por si só, não recompõe os pacotes ontológicos nem a triagem histórica. O replay exato exige também os insumos RAG e de triagem compatíveis fornecidos por canal autorizado. O preparador não converte uma resposta da API em todos esses insumos automaticamente. Não confundir um clone autocontido de código com uma cópia autocontida do corpus privado.

Foram executados testes offline e um preflight isolado usando os insumos locais de origem: 1.461 entradas, 223 selecionados, 223 pacotes, zero chamadas API. Os insumos reais não foram gravados nesta pasta pública. A figura registra a execução histórica com um post por chamada, não lotes de cinco.

As condições de redistribuição de IDs e a origem da coleta precisam ser consideradas pelo usuário; este pacote não declara autorização jurídica geral nem afasta os direitos dos autores. Não aplicar a licença autoral deste código aos posts recuperados. Segredos, textos, citações e resultados individuais devem continuar fora do Git, inclusive do histórico.
