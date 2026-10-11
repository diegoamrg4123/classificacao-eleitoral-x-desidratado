# Ontologia pública: fonte declarativa e representações

Este diretório é o perfil `revisao-publica-normativa-v1`, derivado da estrutura conceitual da ontologia eleitoral. Não é o acervo completo de pesquisa.

- `projeto.synp` declara somente fontes e evidências públicas selecionadas.
- `template.synt` preserva o contrato de campos. A presença de um campo no contrato não significa que dados privados desse campo tenham sido distribuídos.
- `ontologia/dominio-eleitoral.syno` preserva os 49 conceitos e seus critérios.
- Os dois CSVs em `ontologia/` preservam o vocabulário e a relação complementar aprovada.
- `fontes/registros/fontes-publicas.syn` contém 15 registros normativos com links oficiais.
- `itens/evidencias-publicas.syn` contém 36 evidências conceituais normativas, todas com revisão pendente.
- `escopo-publico.json` explicita IDs, campos permitidos e SHA-256 das sete entradas do recorte.
- `exportacoes/` contém OWL simples, OWL completo do recorte, RDF/XML, Turtle e JSONL.
- `visualizacao/mapa-ontologico.html` permite consulta independente de instalação.
- `ferramentas/` contém exportadores derivados; o módulo de camada contextual é somente uma barreira que impede carregar dados privados.

Veja o [README principal](../README.md) para escolher uma representação. Abra o HTML localmente, use busca e clique em um conceito para ler critérios no painel lateral. A árvore inteira é ampla: use zoom para ler seus rótulos. Os detalhes continuam disponíveis sem ampliar a árvore.

## Verificar sem regenerar

Da raiz do repositório:

```bash
python3 ontologia-publica/validar_publico.py
```

Verifica checksums, listas permitidas, campos e consistência de todas as exportações com as entradas deste próprio diretório. Não lê a origem restrita, não grava saídas e não acessa banco ou internet.

## Compilar e regenerar

```bash
bash ontologia-publica/validar.sh
```

Exige `uvx`, Bash e Python. Usa Synesis `0.11.0`, compila o projeto e executa os exportadores apenas neste recorte. O primeiro download do compilador pode exigir internet. Não executa o validador complementar do projeto privado, cujas contagens e dependências são diferentes. Não apresenta o recorte como aprovado na suíte canônica privada.

Fontes e evidências foram selecionadas para distribuição, não recodificadas. Estados de revisão, definições e IDs não foram promovidos ou reinterpretados. Alterar as entradas ou listas permitidas exige nova revisão humana de escopo e direitos antes de publicação. As saídas são derivadas; não as edite manualmente.

[Privacidade e recorte](../documentacao/privacidade-e-recorte.md) | [Validação](../documentacao/validacao.md) | [ArcadeDB](../arcadedb/README.md)
