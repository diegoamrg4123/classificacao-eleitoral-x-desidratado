# Ontologia eleitoral e classificação textual no X

Artefatos de apoio à consulta e revisão do artigo **Ontologia da desinformação eleitoral: bases para modelagem semântica e grafos de conhecimento aplicados à checagem de fatos em modelos de linguagem fundacionais**.

O repositório reúne duas partes independentes: um **recorte público da ontologia**, com representações consultáveis e um grafo reconstruível, e o **pipeline desidratado de classificação no X**, já disponibilizado anteriormente. Não contém o corpus textual, contexto privado ou resultados individuais. A documentação do executor anterior foi preservada em [Classificação no X](documentacao/classificacao-x.md).

## Por onde começar

1. **Quero entender a organização conceitual:** baixe o repositório e abra [o mapa HTML](ontologia-publica/visualizacao/mapa-ontologico.html) no navegador. Não requer instalação, servidor ou credenciais. No GitHub, o arquivo HTML aparece como código: use o download ou um clone para visualizá-lo.
2. **Quero examinar definições e critérios:** consulte [a fonte Synesis](ontologia-publica/ontologia/dominio-eleitoral.syno), [o contrato de campos](ontologia-publica/template.synt) e [as evidências normativas](ontologia-publica/itens/evidencias-publicas.syn).
3. **Quero navegar no Protégé:** comece pelo [OWL simples](ontologia-publica/exportacoes/ontologia-simples.owl). Para proveniência e metadados, use o OWL completo.
4. **Quero consultar o grafo em um banco:** siga o [roteiro ArcadeDB](arcadedb/README.md), que cria uma instância local apenas com os dados deste recorte.
5. **Quero examinar a aplicação no X:** veja [a documentação do executor](documentacao/classificacao-x.md), as [listas de IDs](dados/desidratados/) e a [Figura 3](figuras/figura-3-classificacao-x.png).

## O que cada representação oferece

| Representação | Arquivo ou pasta | Finalidade |
|---|---|---|
| Projeto Synesis | [Manifesto](ontologia-publica/projeto.synp), template, `.syno`, `.syn` e CSVs | Examinar a fonte declarativa do recorte, suas definições, critérios, campos, evidências e relações. Compilável sem acesso à origem privada. |
| OWL simples | [ontologia-simples.owl](ontologia-publica/exportacoes/ontologia-simples.owl) | Visualizar somente as classes, rótulos, definições e hierarquia. Não inclui fontes, evidências, relações complementares ou GraphRAG. |
| OWL completo do recorte | [ontologia-completa.owl](ontologia-publica/exportacoes/ontologia-completa.owl) | Examinar classes conceituais, estrutura técnica Synesis, proveniência normativa, evidências e relação complementar. “Completo” refere-se ao recorte público, não ao acervo restrito. |
| RDF/XML e Turtle | [ontologia.rdf](ontologia-publica/exportacoes/ontologia.rdf) e [ontologia.ttl](ontologia-publica/exportacoes/ontologia.ttl) | Serializações do mesmo grafo semântico do OWL completo, para ferramentas RDF. |
| JSONL | [ontologia.jsonl](ontologia-publica/exportacoes/ontologia.jsonl) | Registros estruturados para inspeção e ingestão: manifesto, entradas com checksum, campos, conceitos, fontes, itens e relações. Não é dataset de fine-tuning. |
| HTML interativo | [mapa-ontologico.html](ontologia-publica/visualizacao/mapa-ontologico.html) | Consultar conceitos, critérios e a relação complementar visualmente, sem infraestrutura. |
| ArcadeDB | [Compose, importador e verificador](arcadedb/) | Reconstruir e consultar a projeção pública por vértices e arestas. Não é backup do banco experimental. |
| Aplicação no X | [Pipeline e documentação](documentacao/classificacao-x.md) | Examinar código, prompt, contrato de saída, IDs desidratados e resultados agregados históricos. Insumos privados necessários ao replay não são distribuídos. |

## Escopo da ontologia pública

O perfil `revisao-publica-normativa-v1` contém **49 conceitos, 48 vínculos hierárquicos, uma relação complementar aprovada, 15 SOURCEs normativos e 36 ITEMs de evidência conceitual**. O contrato possui 51 campos. O JSONL contém 161 registros; sua projeção ArcadeDB tem 161 vértices e 304 arestas, incluindo relações técnicas de proveniência e navegação, não apenas a árvore conceitual.

A seleção adota uma lista explícita de fontes, itens e campos em [escopo-publico.json](ontologia-publica/escopo-publico.json), com checksums das entradas distribuídas. Foram preservados os IDs, definições, critérios e a hierarquia da fonte conceitual. A relação adicional liga `calunia_eleitoral` a `veracidade_da_informacao`: exige avaliação factual, sem tornar calúnia subclasse de desinformação nem deduzir valor da escala.

A raiz `conteudo_tema_eleitoral` delimita o universo analisado; `dominio_eleitoral` é um ramo temático, separado das dimensões de Veracidade, Integridade e Ilicitude. No artigo, discurso hostil é a terminologia de apresentação. Os arquivos formais preservam os IDs e rótulos canônicos de discurso de ódio para manter a rastreabilidade; não houve renomeação metodológica nesta distribuição.

**Estado de revisão:** o projeto permanece `rascunho_em_revisao` e os 36 ITEMs permanecem `pendente`. A relação complementar já aprovada conserva seu estado próprio. Publicação e validação técnica não promovem evidências a aprovadas, não comprovam acurácia e não produzem decisão jurídica. Os trechos normativos e adaptações devem ser conferidos nas URLs oficiais antes de uso substantivo. `confianca` mede o vínculo ITEM-conceito, não a veracidade ou ilicitude do conteúdo.

### Linguagem Synesis

A fonte declarativa utiliza [Synesis, linguagem e compilador para organizar anotações de pesquisa qualitativa](https://github.com/synesis-lang/synesis). O repositório oficial reúne o código-fonte, a documentação e as versões do compilador. A [documentação em português](https://synesis-lang.github.io/synesis-docs/pt/) apresenta a sintaxe e o uso da linguagem. Este pacote fixa a versão `0.11.0` para reproduzir a compilação validada, sem afirmar que seja a versão mais recente.

Os exportadores OWL/RDF, JSONL detalhado, mapa HTML e importador ArcadeDB deste repositório são ferramentas derivadas do projeto de pesquisa, não formatos ou recursos nativos atribuídos ao compilador Synesis.

### GraphRAG não é uma terceira ontologia

O OWL completo, RDF e JSONL incluem políticas derivadas de recuperação e revisão humana. Elas ajudam a distinguir categorias operacionais de contexto estrutural e a citar ITEM e SOURCE. Não acrescentam conceitos nem dispensam revisão. Essa camada pública não é o snapshot RAG histórico usado na classificação do X, que continua excluído.

No Protégé, o OWL completo inclui classes técnicas de apoio e conceitos também representados como indivíduos SKOS. Para uma árvore limpa, prefira o OWL simples, expanda `conteudo_tema_eleitoral` e configure os rótulos por `rdfs:label`. Os arquivos foram validados estruturalmente; não se afirma teste visual desta distribuição no Protégé. As IRIs originais foram mantidas como identificadores estáveis, não como promessa de endereço dereferenciável.

## Privacidade e exclusões

Foram excluídos desta ampliação: fontes e registros internos, exemplos e casos-limite da equipe, registros de artefatos privados, casos jurisprudenciais, conteúdo de plataformas, arquivos integrais de terceiros, entidades nomeadas e suas menções, aliases, pistas lexicais, embeddings, pacotes RAG históricos, respostas de LLM, avaliações individuais, credenciais, logs, backups e estado persistente do banco original. O campo `contexto` não é preenchido nos ITEMs distribuídos. Os exportadores desta cópia bloqueiam o carregamento da camada contextual privada.

A referência normativa a biometria descreve um procedimento público do TSE; não contém dados biométricos ou registros de eleitores. As justificativas distribuídas descrevem vínculos conceituais com normas, não publicações observadas. A seleção e seus limites estão em [Privacidade e recorte](documentacao/privacidade-e-recorte.md).

As listas de **1.461 IDs da base e 223 IDs selecionados**, já publicadas, foram preservadas sem acrescentar rótulos por post. IDs permitem localizar publicações e **não são anonimização**. Não há textos nem autoria nas listas; recuperar posts depende de acesso autorizado, regras da plataforma e disponibilidade. O grafo novo não inclui esses IDs.

## Baixar e verificar

```bash
git clone https://github.com/diegoamrg4123/classificacao-eleitoral-x-desidratado.git
cd classificacao-eleitoral-x-desidratado
python3 -m unittest discover -s tests -v
python3 ontologia-publica/validar_publico.py
```

Python 3.10 ou posterior é suficiente para os testes, validadores e exportadores, que usam biblioteca padrão. Para **recompilar e regenerar** os artefatos, é necessário Bash e `uv`/`uvx`, com Synesis fixado em `0.11.0`:

```bash
bash ontologia-publica/validar.sh
```

A primeira obtenção do Synesis pode requerer internet; a compilação usa somente arquivos deste repositório. O mapa e as exportações prontos dispensam Synesis. O roteiro do banco requer Docker Engine e Compose e pode baixar a imagem fixada do ArcadeDB. Nenhuma dessas etapas faz chamadas a LLMs, coleta posts ou consulta o banco original.

Os testes de distribuição e os resultados reais da reconstrução estão descritos em [Validação](documentacao/validacao.md). Qualquer edição das entradas exige nova revisão da seleção e atualização dos checksums; apenas regenerar saídas não autoriza publicar novas evidências.

## Organização

```text
README.md                       Entrada para o revisor
LICENSE.md                      Citação e exceção limitada de revisão
ontologia-publica/               Fonte declarativa e entregáveis do recorte
  fontes/registros/             Proveniência normativa selecionada
  itens/                       Evidências conceituais normativas
  ontologia/                   Conceitos e relações complementares
  ferramentas/                 Exportadores derivados
  exportacoes/                 OWL, RDF e JSONL
  visualizacao/                Mapa HTML independente
arcadedb/                       Banco público reconstruível via Compose
documentacao/                   Escopo, validação e aplicação histórica
scripts/, prompts/, schemas/    Pipeline desidratado preservado
dados/desidratados/              IDs nativos sem textos ou rótulos
figuras/                        Resultados agregados da aplicação
tests/                          Verificações offline
```

## Reprodução e limites

O clone permite recompilar o **recorte formal**, regenerar suas exportações e reconstruir o **grafo público**. Não reproduz a coleta, triagem, embeddings, RAG congelado, classificação cloud ou avaliação individual da pesquisa. O executor histórico usa `google/gemma-4-31b-it` via OpenRouter e exige insumos privados compatíveis e autorização separada. Sua execução de origem teve 223 selecionados, 69 classificações provisórias, 100 sem categoria, sete contextos insuficientes e 47 abstenções. Os detalhes e ressalvas anteriores estão preservados na documentação própria.

## Licença e como citar

**Este repositório não tem licença aberta.** A [licença](LICENSE.md) permite citação e, exclusivamente para revisão acadêmica, download, consulta, compilação e execução local dos validadores e da reconstrução do grafo público. Não autoriza redistribuição, adaptação, exploração comercial, uso em produção ou treinamento de modelos. Direitos de terceiros permanecem com seus titulares.

GOULART, Diego Amorim. *Ontologia eleitoral e classificação textual no X: artefatos públicos para revisão*. 2026. Disponível em: https://github.com/diegoamrg4123/classificacao-eleitoral-x-desidratado. Acesso em: data de consulta. Para identificar exatamente a versão consultada, acrescente o hash do commit.
