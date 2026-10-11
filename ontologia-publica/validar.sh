#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
uvx --from synesis==0.11.0 synesis validate-template template.synt
uvx --from synesis==0.11.0 synesis compile projeto.synp --stats
python3 ferramentas/exportar_ontologia_owl_rdf.py --root . --owl-output exportacoes/ontologia-completa.owl --rdf-output exportacoes/ontologia.rdf --turtle-output exportacoes/ontologia.ttl
python3 ferramentas/exportar_ontologia_owl_simples.py --syno ontologia/dominio-eleitoral.syno --output exportacoes/ontologia-simples.owl
python3 ferramentas/exportar_ontologia_jsonl.py --root . --output exportacoes/ontologia.jsonl
python3 ferramentas/gerar_visualizacao_ontologica.py --root . --output visualizacao/mapa-ontologico.html
python3 validar_publico.py
