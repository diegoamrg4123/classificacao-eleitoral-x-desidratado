# Verificação técnica da distribuição pública

Verificações executadas em 11 de outubro de 2026, no perfil `revisao-publica-normativa-v1`. Elas certificam o que foi exercitado tecnicamente, não a qualidade interpretativa ou jurídica da ontologia.

| Verificação | Resultado observado |
|---|---|
| Template e compilação com Synesis 0.11.0 | Código de saída zero; 15 SOURCEs, 36 ITEMs, 49 ONTOLOGY, 49 códigos e zero chains. |
| Validador próprio do recorte | Checksums das sete entradas, IDs e campos permitidos e consistência das seis saídas confirmados. |
| Testes offline | 29 testes aprovados, incluindo os 23 testes anteriores do pipeline. Nenhuma chamada a LLM ou coleta. |
| Testes negativos | Entrada alterada, exportação com registro extra privado e tentativa de carregar a camada contextual privada foram rejeitadas. |
| RDF/XML, OWL completo e Turtle | Parsing com RDFLib 7.2.1; 3.529 triplas em cada serialização do grafo completo, com equivalência por isomorfismo. |
| OWL simples | 49 classes conceituais e 48 axiomas `rdfs:subClassOf`. |
| HTML | 49 nós carregados em navegador local; busca e painel de definição, inclusão e exclusão de Calúnia Eleitoral exercitados. |
| Compose | Configuração validada; ArcadeDB 26.5.1 com imagem fixada também por digest, porta em loopback e volumes próprios. |
| Importação do grafo | 161 vértices e 304 arestas; contagens por tipo, 161 payloads e propriedades semânticas conferidos por leitura posterior. |
| Reimportação do mesmo snapshot | Mesmos totais e payloads, sem duplicação. |
| Consulta hierárquica real | `MATCH ... RETURN $pathElements LIMIT 500` retornou 144 elementos de caminhos; a relação complementar retornou três. Esses números não são contagens de conceitos ou relações taxonômicas. |
| Inspeção de schema do banco isolado | Somente os oito tipos de vértice e os tipos de aresta da projeção pública. |
| Auditoria de seleção | 64 registros excluídos da origem inspecionados; nenhum trecho de conteúdo ou contexto excluído com pelo menos 60 caracteres encontrado nas exportações ou no HTML. A lista positiva e a comparação de saídas complementam essa busca textual, que isoladamente não provaria ausência de todo risco. |
| Preservação | Template e arquivo conceitual iguais byte a byte à fonte; código, IDs, figuras, prompts, schemas e testes preexistentes do repositório público preservados. |

SHA-256 do JSONL público utilizado na importação: `8c677bb5e923bf381a707cdcc5df89d8d2b686eb148dbd69fcc7ece98556b22a`.

## Reexecutar a verificação

Na raiz do repositório:

```bash
python3 -m unittest discover -s tests -v
python3 ontologia-publica/validar_publico.py
bash ontologia-publica/validar.sh
```

A compilação e a regeneração usam apenas os arquivos deste recorte. O Synesis é obtido por `uvx`; a primeira obtenção pode exigir internet. As contagens da suíte privada canônica não são critérios desta distribuição e não foram reescritas.

Para repetir o teste do banco, siga [o roteiro ArcadeDB](../arcadedb/README.md), importe, verifique, importe novamente e verifique outra vez. Use uma instância nova, sem dados de trabalho. Não confunda a recriação deste grafo público com a restauração do ambiente experimental.

A checagem adicional de RDF pode ser repetida com RDFLib 7.2.1 em ambiente temporário. RDFLib não é dependência dos exportadores ou dos testes offline do repositório.

## Limitações do que foi verificado

- Não foi feita revisão visual desta distribuição no Protégé ou no ArcadeDB Studio. O mapa HTML foi inspecionado no navegador; as consultas do banco foram exercitadas por HTTP/JSON.
- Compilação, parsing e contagens não validam transcrições legais, atualização normativa, decisões de enquadramento ou acurácia.
- Nenhuma evidência pendente foi promovida a aprovada. A licença de distribuição não libera corpus de terceiros.
- Não houve reidratação online de posts, execução de classificação cloud ou avaliação nova de modelos.
- Não se oferece reprodução integral do corpus, triagem, RAG histórico, respostas ou decisões individuais, deliberadamente não distribuídos.
