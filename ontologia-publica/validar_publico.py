#!/usr/bin/env python3
"""Confere entradas permitidas e exportações do recorte, sem ler a origem privada."""
from pathlib import Path
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'ferramentas'))
from exportar_ontologia_owl_rdf import parse_project, parse_annotation_records, parse_concepts, build_graph, serialize_rdfxml, serialize_turtle
from exportar_ontologia_jsonl import build_records, serialize_jsonl
from exportar_ontologia_owl_simples import read_concepts, build_document, serialize
from gerar_visualizacao_ontologica import build_payload, render_html


def validate(root=ROOT):
    root = Path(root).resolve()
    scope = json.loads((root / 'escopo-publico.json').read_text(encoding='utf-8'))
    for relative, digest in scope['input_sha256'].items():
        path = root / relative
        if path.resolve().is_relative_to(root) is False or path.is_symlink():
            raise ValueError('Entrada fora do recorte público')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Entrada modificada: ' + relative)
    project = parse_project(root / 'projeto.synp')
    sources, items = parse_annotation_records(root, project)
    concepts = parse_concepts(root)
    if set(sources) != set(scope['source_ids']) or set(items) != set(scope['item_ids']):
        raise ValueError('SOURCEs ou ITEMs fora da lista permitida')
    if len(concepts) != scope['concept_count']:
        raise ValueError('Contagem conceitual divergente')
    for rows, permitted in ((sources, scope['source_fields']), (items, scope['item_fields'])):
        for row in rows.values():
            if set(row) - set(permitted) - {'kind', 'header', 'path'}:
                raise ValueError('Campo não permitido no recorte público')
    if any(row['tipo_fonte'] != 'legislacao' for row in sources.values()):
        raise ValueError('Fonte não normativa')
    if any(row['funcao_item'] != 'evidencia_conceitual' or row['status_revisao'] != 'pendente' for row in items.values()):
        raise ValueError('Estado ou função de evidência divergente')
    records, counts = build_records(root)
    graph, graph_counts = build_graph(root)
    payload = build_payload(root)
    # Comparar serializações de XML pela árvore evita depender de prefixos globais do ElementTree.
    expected = {
        'exportacoes/ontologia.jsonl': serialize_jsonl(records),
        'exportacoes/ontologia.ttl': serialize_turtle(graph),
        'visualizacao/mapa-ontologico.html': render_html(payload),
    }
    for relative, text in expected.items():
        if (root / relative).read_text(encoding='utf-8') != text:
            raise ValueError('Exportação desatualizada: ' + relative)
    for relative, text in (
        ('exportacoes/ontologia-completa.owl', serialize_rdfxml(graph)),
        ('exportacoes/ontologia.rdf', serialize_rdfxml(graph)),
        ('exportacoes/ontologia-simples.owl', serialize(build_document(read_concepts(root / 'ontologia/dominio-eleitoral.syno')))),
    ):
        actual = ET.canonicalize((root / relative).read_text(encoding='utf-8'), rewrite_prefixes=True)
        wanted = ET.canonicalize(text, rewrite_prefixes=True)
        if actual != wanted:
            raise ValueError('XML derivado divergente: ' + relative)
    return {'profile': scope['profile'], 'jsonl': counts, 'rdf': graph_counts,
            'hierarchy_edges': payload['hierarchy_edge_count'],
            'supplementary_relations': payload['supplementary_relation_count']}


if __name__ == '__main__':
    try:
        print(json.dumps(validate(), ensure_ascii=False, sort_keys=True))
    except (OSError, ValueError, KeyError) as error:
        print('VALIDACAO_PUBLICA_FALHOU: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
