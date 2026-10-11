#!/usr/bin/env python3
"""Exporta somente a hierarquia taxonômica do arquivo Synesis .syno.

A saída é uma projeção derivada e mínima para visualização no Protégé:
classes conceituais, rótulos, definições e relações rdfs:subClassOf. Não
inclui cabeçalho de ontologia, propriedades auxiliares, SOURCEs, ITEMs,
template, proveniência, relações complementares, GraphRAG ou entidades.
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


BASE_IRI = "https://github.com/diegoamrg4123/dominio-eleitoral-synesis/ontology"
CONCEPT_NAMESPACE = BASE_IRI + "#"

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XML = "http://www.w3.org/XML/1998/namespace"

PREFIXES = {
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
}

for prefix, namespace in PREFIXES.items():
    ET.register_namespace(prefix, namespace)

ONTOLOGY_BLOCK_RE = re.compile(
    r"(?ms)^ONTOLOGY\s+([a-z_][a-z0-9_]*)\s*\n(.*?)^END ONTOLOGY\s*$"
)
FIELD_RE = re.compile(r"^\s+([a-z_][a-z0-9_]*):\s*(.*?)\s*$")


def concept_iri(concept_id: str) -> str:
    return f"{CONCEPT_NAMESPACE}concept/{concept_id}"


def read_concepts(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"Arquivo .syno não encontrado: {path}")

    concepts: dict[str, dict[str, str]] = {}
    text = path.read_text(encoding="utf-8")
    for concept_id, body in ONTOLOGY_BLOCK_RE.findall(text):
        if concept_id in concepts:
            raise ValueError(f"Conceito duplicado no .syno: {concept_id}")
        fields: dict[str, str] = {}
        for line in body.splitlines():
            match = FIELD_RE.match(line)
            if match:
                fields[match.group(1)] = match.group(2)
        concepts[concept_id] = fields

    if not concepts:
        raise ValueError(f"Nenhum bloco ONTOLOGY encontrado em: {path}")

    for concept_id, fields in concepts.items():
        parent = fields.get("conceito_pai")
        if parent and parent not in concepts:
            raise ValueError(f"Conceito {concept_id} referencia pai inexistente: {parent}")

    return concepts


def add_literal(parent: ET.Element, namespace: str, local_name: str, value: str) -> None:
    element = ET.SubElement(
        parent,
        f"{{{namespace}}}{local_name}",
        {f"{{{XML}}}lang": "pt-BR"},
    )
    element.text = value


def add_resource(parent: ET.Element, namespace: str, local_name: str, iri: str) -> None:
    ET.SubElement(parent, f"{{{namespace}}}{local_name}", {f"{{{RDF}}}resource": iri})


def build_document(concepts: dict[str, dict[str, str]]) -> ET.Element:
    root = ET.Element(f"{{{RDF}}}RDF")

    for concept_id, fields in sorted(concepts.items()):
        concept = ET.SubElement(
            root,
            f"{{{OWL}}}Class",
            {f"{{{RDF}}}about": concept_iri(concept_id)},
        )
        preferred_label = fields.get("rotulo_preferido", concept_id)
        add_literal(concept, RDFS, "label", preferred_label)

        definition = fields.get("definicao_operacional")
        hierarchical_role = fields.get("papel_hierarquico")
        comment_parts = []
        if hierarchical_role:
            comment_parts.append(f"Papel hierárquico: {hierarchical_role}.")
        if definition:
            comment_parts.append(f"Definição operacional: {definition}")
        if comment_parts:
            add_literal(concept, RDFS, "comment", " ".join(comment_parts))

        parent = fields.get("conceito_pai")
        if parent:
            add_resource(concept, RDFS, "subClassOf", concept_iri(parent))

    return root


def serialize(root: ET.Element) -> str:
    ET.indent(root, space="  ")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + ET.tostring(
        root, encoding="unicode"
    ) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--syno",
        type=Path,
        default=Path("ontologia/dominio-eleitoral.syno"),
        help="Arquivo .syno usado como fonte da projeção.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Entregáveis/OWL/ontologia-dominio-eleitoral-simples.owl"),
        help="Destino do OWL simplificado em RDF/XML.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        concepts = read_concepts(args.syno)
        document = build_document(concepts)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialize(document), encoding="utf-8", newline="\n")
    except (OSError, ValueError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1

    subclass_count = sum(1 for concept in document if concept.tag == f"{{{OWL}}}Class" for child in concept if child.tag == f"{{{RDFS}}}subClassOf")
    print(f"OWL_SIMPLES_EXPORTADO classes={len(concepts)} subclass_axioms={subclass_count} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
