# Consultar o recorte público no ArcadeDB

Este ambiente reconstrói um grafo exclusivamente a partir de `ontologia-publica/exportacoes/ontologia.jsonl`. Não contém nem restaura o banco experimental, posts, entidades nomeadas, embeddings ou contexto RAG privado. Alterações no banco não retornam automaticamente à fonte Synesis.

## Requisitos

- Docker Engine e Docker Compose v2, com permissão para executar contêineres.
- Python 3.10 ou posterior, sem pacotes Python adicionais.
- Porta local 2481 livre. A instância de trabalho na porta 2480 não é utilizada.
- Internet apenas se a imagem ainda precisar ser baixada.

A imagem é `arcadedata/arcadedb:26.5.1`, fixada também por digest no Compose. A configuração limita a JVM a 768 MB de heap; o consumo total do contêiner pode ser maior. A porta HTTP fica vinculada somente a `127.0.0.1`. Não altere para exposição pública.

## Executar, na ordem

Partindo da raiz do repositório:

```bash
python3 ontologia-publica/validar_publico.py
python3 arcadedb/scripts/inicializar_ambiente.py
docker compose -f arcadedb/compose.yaml --env-file arcadedb/.env config --quiet
docker compose -f arcadedb/compose.yaml --env-file arcadedb/.env up -d
python3 arcadedb/scripts/importar_synesis.py
python3 arcadedb/scripts/verificar_arcadedb.py
```

O inicializador cria uma senha aleatória em `arcadedb/.env`, com permissão 0600. Não a imprime, não a envia a serviços externos e não sobrescreve um ambiente existente. Nunca versione ou compartilhe esse arquivo. O `.env.example` não contém senha funcional. O importador aguarda a resposta real do servidor e valida as entradas e exportações públicas antes de escrever. Não aceita selecionar a pasta privada de origem nem um snapshot alternativo.

Servidor: **http://127.0.0.1:2481**. Usuário: `root`. Use no Studio a senha gerada no seu arquivo `.env`, sem compartilhá-la. Banco: **synesis_eleitoral_publica**. Credenciais ficam restritas à instalação local; usuários com acesso administrativo ao Docker podem inspecionar a configuração de execução.

A importação e a reimportação do mesmo snapshot foram testadas sem duplicação. O verificador exige 161 vértices e 304 arestas, confere contagens por tipo, os 161 payloads e as propriedades semânticas dos 49 conceitos. Os payloads reproduzem apenas o JSONL público, não dados de outros bancos.

## Consultas para começar

No Studio, selecione SQL e o banco `synesis_eleitoral_publica`.

### Tabela legível dos conceitos

```sql
SELECT concept_id, label, concept_type, parent_concept_id,
       operational_definition, inclusion_criterion, exclusion_criterion
FROM OntologyConcept
ORDER BY label
```

### Hierarquia com nós e arestas

```sql
MATCH
  {type: OntologyConcept, as: pai}
  .outE('PARENT_OF'){}
  .inV(){type: OntologyConcept, as: filho}
RETURN $pathElements
LIMIT 500
```

Para visualizar as arestas na aba Graph, use `$pathElements`, não somente colunas. Ajuste o Auto Limit para pelo menos 500. A árvore possui 49 conceitos e 48 relações pai-filho; as linhas retornadas por `$pathElements` incluem elementos de caminhos e não equivalem diretamente à contagem de relações.

### Relação complementar aprovada

```sql
MATCH
  {type: OntologyConcept, as: origem}
  .outE('REQUER_AVALIACAO_DE_VERACIDADE'){}
  .inV(){type: OntologyConcept, as: destino}
RETURN $pathElements
LIMIT 20
```

Ela conecta Calúnia Eleitoral a Veracidade da Informação. Há também um vértice `OntologyRelation`, que preserva status, justificativa e vínculos com as evidências; a aresta direta não substitui essa proveniência.

### Evidências e fontes normativas

```sql
SELECT item_id, source_id, review_status, classification_status, payload_json
FROM Item
LIMIT 50
```

```sql
SELECT source_id, source_type, description, payload_json
FROM Source
LIMIT 20
```

Os ITEMs continuam pendentes de revisão. O banco não transforma esses vínculos em confirmação de veracidade, crime ou ilicitude. As consultas gráficas foram executadas por HTTP/JSON; a interface Studio não foi testada visualmente nesta distribuição.

## Reexecutar, parar e limpar

Para verificar idempotência no seu ambiente, execute novamente o importador e depois o verificador. O importador não é um sincronizador destrutivo: não remove registros obsoletos nem experimentos manuais. Para uma versão de recorte diferente, use ambiente novo ou faça backup antes de qualquer limpeza.

Para parar sem perder o banco:

```bash
docker compose -f arcadedb/compose.yaml --env-file arcadedb/.env down
```

Para iniciar novamente, use `up -d` com o mesmo `.env`. Não gere outra senha para volumes já inicializados.

**Limpeza destrutiva opcional:** `down -v` remove os volumes deste projeto Compose e seus dados públicos locais. Faça backup de eventuais experimentos antes e confira o nome do projeto. Não execute contra outro ambiente. O repositório não distribui dados persistentes, configuração de usuários, logs ou backups.

Se 2481 estiver ocupada, escolha outra porta livre em `ARCADEDB_HTTP_PORT` no seu `.env` e informe a URL correspondente aos dois scripts com `--url http://127.0.0.1:PORTA`. Não use a URL do banco original para estes testes.

## Modelo da projeção

Os tipos de vértice são `SynesisProject`, `CanonicalInput`, `TemplateField`, `OntologyConcept`, `Source`, `Item`, `RelationType` e `OntologyRelation`. As relações incluem hierarquia, ligações ITEM-SOURCE, códigos de conceitos, evidências da relação complementar e vínculos técnicos com o manifesto. Por isso o total de 304 arestas não representa 304 relações taxonômicas.

O ambiente é uma projeção pública para revisão, não um classificador, serviço de produção ou réplica integral do experimento. A permissão de execução é limitada à [licença](../LICENSE.md).
