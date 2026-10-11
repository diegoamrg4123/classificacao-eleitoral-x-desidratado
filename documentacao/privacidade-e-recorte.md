# Privacidade e critérios do recorte público

## Decisão de distribuição

Este pacote usa uma lista positiva de arquivos, SOURCEs, ITEMs e campos. Ele foi preparado em clone separado do repositório público. Não é cópia do acervo seguida de remoção de textos, nem backup do banco de trabalho.

A estrutura conceitual, o contrato e a relação complementar foram preservados. A proveniência foi limitada a normas e evidências conceituais vinculadas a elas. Fontes jurisprudenciais, mesmo publicamente acessíveis, ficaram fora deste primeiro perfil por opção conservadora de distribuição. Isso não afirma que sejam privadas ou juridicamente indistribuíveis.

Não foram feitas novas classificações ou anotações. A seleção não confere aprovação metodológica aos ITEMs: todos permanecem pendentes. O projeto continua em revisão. A revisão de distribuição é distinta da conferência substantiva da transcrição, atualização normativa ou aplicação jurídica.

## Fontes incluídas

As 15 fontes têm `tipo_fonte: legislacao`; as URLs oficiais e identificadores normativos estão em [fontes-publicas.syn](../ontologia-publica/fontes/registros/fontes-publicas.syn). Nenhum documento externo integral foi incorporado.

| ID estável | Identificador da norma | Consulta oficial |
|---|---|---|
| `@codigo_penal_1940` | Decreto-Lei 2.848/1940, arts. 138 a 145, 286 e 359-L a 359-T | [Fonte](https://www.planalto.gov.br/ccivil_03/decreto-lei/del2848compilado.htm) |
| `@codigo_eleitoral_1965` | Lei 4.737/1965, arts. 323 a 327 | [Fonte](https://www.planalto.gov.br/ccivil_03/leis/l4737compilado.htm) |
| `@lei_7716_1989` | Lei 7.716/1989, arts. 2-A e 20 | [Fonte](https://www.planalto.gov.br/ccivil_03/leis/l7716.htm) |
| `@lei_14532_2023` | Lei 14.532/2023 | [Fonte](https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/l14532.htm) |
| `@lei_14192_2021` | Lei 14.192/2021, art. 4 | [Fonte](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14192.htm) |
| `@lei_13834_2019` | Lei 13.834/2019, art. 326-A do Codigo Eleitoral | [Fonte](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/l13834.htm) |
| `@constituicao_federal_1988` | Constituicao Federal de 1988, arts. 1 e 14, paragrafo 9 | [Fonte](https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm) |
| `@lc_64_1990` | Lei Complementar 64/1990, art. 22 | [Fonte](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp64.htm) |
| `@resolucao_tse_23610_2019` | Resolucao TSE 23.610/2019, arts. 9 e 9-C | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2019/resolucao-no-23-610-de-18-de-dezembro-de-2019) |
| `@resolucao_tse_23673_2021` | Resolucao TSE 23.673/2021 | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2021/resolucao-no-23-673-14-de-dezembro-de-2021) |
| `@resolucao_tse_23755_2026` | Resolucao TSE 23.755/2026, Instrucao 0600751-65.2019.6.00.0000, arts. 9-B a 9-J, 28 e 38-A | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-755-de-2-de-marco-de-2026) |
| `@resolucao_tse_23757_2026` | Resolucao TSE 23.757/2026, Instrucao 0600043-39.2024.6.00.0000, art. 6, paragrafo 4 | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-757-de-2-de-marco-de-2026) |
| `@resolucao_tse_23758_2026` | Resolucao TSE 23.758/2026, Instrucao 0600747-28.2019.6.00.0000 | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-758-de-2-de-marco-de-2026) |
| `@resolucao_tse_23760_2026` | Resolucao TSE 23.760/2026, Instrucao 0600273-13.2026.6.00.0000 | [Fonte](https://www.tse.jus.br/legislacao/compilada/res/2026/resolucao-no-23-760-de-2-de-marco-de-2026) |
| `@portaria_tse_463_2026` | Portaria TSE 463/2026, DJE 30/07/2026 | [Fonte](https://www.tse.jus.br/legislacao/compilada/prt/2026/portaria-no-463-de-27-de-julho-de-2026) |

## Evidências e campos

Os 36 ITEMs contêm trechos normativos ou adaptações conceituais já existentes, justificativas de vínculo e localizadores em normas. Não contêm textos do corpus, contexto privado, identificação de usuários ou rótulos sensíveis por publicação.

O [manifesto de escopo](../ontologia-publica/escopo-publico.json) lista individualmente os IDs dos ITEMs. O [arquivo de evidências](../ontologia-publica/itens/evidencias-publicas.syn) permite conferir seus conteúdos, forma de registro e estado de revisão. A referência normativa ao Teste de Integridade com Biometria não distribui biometrias, identidades de eleitores ou registros individuais.

Campos de SOURCE distribuídos: `tipo_fonte`, `descricao_fonte`, `data_acesso`, `url`, `identificador_externo`, `idioma`, `ciclo_eleitoral`.

Campos de ITEM distribuídos: `conteudo`, `funcao_item`, `forma_registro`, `status_enquadramento`, `conceitos`, `justificativa`, `identificador_ocorrencia`, `localizacao_na_fonte`, `data_ocorrencia`, `tipo_midia`, `confianca`, `status_revisao`.

Campos opcionais como `contexto`, `rotulo_original`, `notas_revisao`, caminhos de arquivos incorporados e origens operacionais não são transportados nos registros selecionados. Os nomes desses campos continuam no template, preservado como contrato; isso não transporta valores privados. `identificador_ocorrencia` é mantido como ID de evidência normativa, necessário à relação complementar e à proveniência, não como identificador de post.

## Exclusões e representações derivadas

O novo pacote não contém exemplos internos, casos-limite da equipe, registros técnicos de artefatos privados, conteúdo de plataformas, entidades nomeadas, aliases, pistas lexicais, menções, embeddings, snapshots RAG históricos, respostas de modelo, decisões individuais de avaliação, contatos, credenciais, instruções para agentes, documentos do artigo, backups, logs ou arquivos internos do banco.

Todas as exportações são geradas somente das entradas deste recorte. A inclusão da camada contextual auxiliar está bloqueada nesta cópia, inclusive quando a opção técnica antiga for solicitada. O importador do banco só usa o JSONL público validado. Foram conferidos todos os 161 payloads gravados no ambiente isolado, não apenas contagens de conceitos.

As listas de IDs do X já existentes permanecem em `dados/desidratados/`, separadas da ontologia, sem novos rótulos por ID. IDs permitem localizar publicações e não são anonimização. A documentação de classificação esclarece restrições e limites de recuperação legítima.

## Manutenção e direitos

Checksums e comparação das exportações detectam divergências na distribuição atual. Não substituem a revisão humana de uma futura entrada nem tornam um conteúdo publicável apenas porque passa no compilador. A inclusão de nova fonte, ITEM, campo ou camada exige auditoria de conteúdo, direitos e proveniência antes do commit.

A licença autoral concede somente citação e a exceção expressa de consulta e execução local para revisão acadêmica. Não é uma licença aberta, não libera o corpus e não substitui direitos ou condições de uso de terceiros. Segurança por exclusão e desidratação não regulariza automaticamente a coleta histórica.
