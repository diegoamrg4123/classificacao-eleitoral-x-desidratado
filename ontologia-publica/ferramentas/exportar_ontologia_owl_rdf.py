#!/usr/bin/env python3
"""Exporta o projeto Synesis eleitoral para OWL e serializações RDF.

O exportador é derivado e somente leitura. Ele materializa a descrição formal
canônica do Synesis em uma camada semântica sem modificar template, ontologia,
SOURCEs, ITEMs ou relações complementares.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from camada_contextual_auxiliar import PrivateEntityLayer, load_private_entity_layer


NAMESPACE = "https://github.com/diegoamrg4123/dominio-eleitoral-synesis/ontology#"
ONTOLOGY_IRI = NAMESPACE.removesuffix("#")

RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS = "http://purl.org/dc/terms/"
XSD = "http://www.w3.org/2001/XMLSchema#"
PROV = "http://www.w3.org/ns/prov#"

PREFIXES = {
    "rdf": RDF,
    "rdfs": RDFS,
    "owl": OWL,
    "skos": SKOS,
    "dcterms": DCTERMS,
    "xsd": XSD,
    "prov": PROV,
    "syn": NAMESPACE,
}

GRAPH_RAG_ANNOTATION_PROPERTIES = (
    "graph_rag_profile_id",
    "graph_rag_purpose",
    "graph_rag_project_status",
    "graph_rag_human_review_required",
    "graph_rag_selection_policy",
    "graph_rag_evidence_policy",
    "graph_rag_classification_role",
    "graph_rag_hierarchy_role",
    "graph_rag_structural_context_only",
    "graph_rag_observable_signal",
    "graph_rag_classification_guidance",
    "graph_rag_source_role",
    "graph_rag_legal_source",
    "graph_rag_evidence_role",
    "graph_rag_evidence_review_status",
    "graph_rag_evidence_reviewed",
    "graph_rag_citation_source_id",
    "graph_rag_citation_guidance",
)

for prefix, iri in PREFIXES.items():
    ET.register_namespace(prefix, iri)

BLOCK_RE = re.compile(r"(?ms)^\s*(ONTOLOGY|SOURCE|ITEM)\s+([^\n]+)\n(.*?)^\s*END\s+\1\s*$")
BLOCK_FIELD_RE = re.compile(r"^\s+([a-z_][a-z0-9_]*):\s*(.*)$")
FIELD_BLOCK_RE = re.compile(r"(?ms)^FIELD\s+([a-z_][a-z0-9_]*)\s+TYPE\s+([A-Z]+)\n(.*?)^END FIELD$")
FIELD_SCOPE_RE = re.compile(r"(?m)^\s*SCOPE\s+(SOURCE|ITEM|ONTOLOGY)\s*$")
FIELD_DESCRIPTION_RE = re.compile(r"(?m)^\s*DESCRIPTION\s+(.+?)\s*$")
FIELD_FORMAT_RE = re.compile(r"(?m)^\s*FORMAT\s+(.+?)\s*$")
FIELD_GUIDELINES_RE = re.compile(r"(?ms)^\s*GUIDELINES\s*\n(.*?)^\s*END GUIDELINES\s*$")
FIELD_VALUES_RE = re.compile(r"(?ms)^\s*VALUES\s*\n(.*?)^\s*END VALUES\s*$")
VALUE_RE = re.compile(r"^\s*([a-z_][a-z0-9_]*):\s*(.+?)\s*$")
SCOPE_FIELDS_RE = re.compile(r"(?ms)^(SOURCE|ITEM|ONTOLOGY) FIELDS\s*\n(.*?)^END\s+\1\s+FIELDS$")
PROJECT_RE = re.compile(r"(?m)^PROJECT\s+([^\s]+)")
PROJECT_INCLUDE_RE = re.compile(r'^\s*INCLUDE\s+(ANNOTATIONS|ONTOLOGY)\s+"([^"]+)"\s*$', re.MULTILINE)


class ExportError(ValueError):
    """Erro de integridade que impede uma exportação semântica confiável."""


@dataclass(frozen=True)
class Iri:
    value: str


@dataclass(frozen=True)
class Literal:
    value: str
    datatype: str | None = None
    language: str | None = None


@dataclass(frozen=True)
class Triple:
    subject: str
    predicate: str
    object: Iri | Literal


class Graph:
    """Grafo RDF mínimo, determinístico e sem dependência externa."""

    def __init__(self) -> None:
        self.triples: set[Triple] = set()

    def iri(self, subject: str, predicate: str, object_iri: str) -> None:
        self.triples.add(Triple(subject, predicate, Iri(object_iri)))

    def literal(
        self,
        subject: str,
        predicate: str,
        value: str | int | bool,
        *,
        datatype: str | None = None,
        language: str | None = None,
    ) -> None:
        literal_value = (
            ("true" if value else "false")
            if isinstance(value, bool)
            else str(value)
        )
        self.triples.add(Triple(subject, predicate, Literal(literal_value, datatype, language)))

    def by_subject(self) -> dict[str, list[Triple]]:
        grouped: dict[str, list[Triple]] = defaultdict(list)
        for triple in self.triples:
            grouped[triple.subject].append(triple)
        return grouped


def syn(local_name: str) -> str:
    return NAMESPACE + local_name


def resource(kind: str, identifier: str) -> str:
    return syn(f"{kind}/{identifier}")


def camel_case(value: str) -> str:
    parts = [part for part in value.split("_") if part]
    if not parts:
        raise ExportError(f"Identificador vazio para propriedade: {value!r}")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


def parse_blocks(path: Path, expected_kind: str | None = None) -> list[dict[str, str]]:
    if not path.is_file():
        raise ExportError(f"Arquivo Synesis não encontrado: {path}")

    blocks: list[dict[str, str]] = []
    for kind, raw_identifier, body in BLOCK_RE.findall(path.read_text(encoding="utf-8")):
        if expected_kind and kind != expected_kind:
            continue
        fields: dict[str, str] = {}
        for line in body.splitlines():
            match = BLOCK_FIELD_RE.match(line)
            if match:
                fields[match.group(1)] = match.group(2).strip()
        blocks.append(
            {
                "kind": kind,
                "header": raw_identifier.strip().lstrip("@"),
                "path": path.relative_to(path.parent.parent if path.parent.name == "ontologia" else path.parent).as_posix(),
                **fields,
            }
        )
    return blocks


def parse_template(path: Path) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    if not path.is_file():
        raise ExportError(f"Template não encontrado: {path}")
    text = path.read_text(encoding="utf-8")
    requiredness: dict[str, str] = {}
    for scope, body in SCOPE_FIELDS_RE.findall(text):
        for line in body.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.fullmatch(r"(REQUIRED|OPTIONAL)\s+(.+)", line)
            if not match:
                continue
            state, names = match.groups()
            for name in names.split(","):
                requiredness[name.strip()] = state.lower()

    fields: dict[str, dict[str, object]] = {}
    for name, field_type, body in FIELD_BLOCK_RE.findall(text):
        scope_match = FIELD_SCOPE_RE.search(body)
        description_match = FIELD_DESCRIPTION_RE.search(body)
        if not scope_match or not description_match:
            raise ExportError(f"Campo incompleto no template: {name}")
        values: list[dict[str, str]] = []
        values_match = FIELD_VALUES_RE.search(body)
        if values_match:
            for raw_line in values_match.group(1).splitlines():
                value_match = VALUE_RE.match(raw_line)
                if value_match:
                    values.append(
                        {"id": value_match.group(1), "description": value_match.group(2)}
                    )
        guidelines_match = FIELD_GUIDELINES_RE.search(body)
        format_match = FIELD_FORMAT_RE.search(body)
        fields[name] = {
            "type": field_type,
            "scope": scope_match.group(1),
            "description": description_match.group(1),
            "requiredness": requiredness.get(name, "optional"),
            "format": format_match.group(1) if format_match else "",
            "guidelines": guidelines_match.group(1).strip() if guidelines_match else "",
            "values": values,
        }

    if not fields:
        raise ExportError(f"Nenhum FIELD foi encontrado em {path}")
    return fields, requiredness


def parse_project(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ExportError(f"Manifesto não encontrado: {path}")
    text = path.read_text(encoding="utf-8")
    project_match = PROJECT_RE.search(text)
    if not project_match:
        raise ExportError(f"PROJECT não encontrado em {path}")
    metadata: dict[str, str] = {}
    in_metadata = False
    in_description = False
    description_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "METADATA":
            in_metadata = True
            continue
        if line == "END METADATA":
            in_metadata = False
            continue
        if line == "DESCRIPTION":
            in_description = True
            continue
        if line == "END DESCRIPTION":
            in_description = False
            continue
        if in_metadata and ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip()
        elif in_description and line:
            description_lines.append(line)
    return {
        "name": project_match.group(1),
        "metadata": metadata,
        "description": "\n".join(description_lines),
        "includes": [
            {"kind": kind, "path": include_path}
            for kind, include_path in PROJECT_INCLUDE_RE.findall(text)
        ],
    }


def parse_annotation_records(
    root: Path,
    project: dict[str, object],
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Lê somente os arquivos de anotação declarados pelo manifesto."""
    sources: dict[str, dict[str, str]] = {}
    items: dict[str, dict[str, str]] = {}
    annotation_paths = sorted(
        {
            str(include["path"])
            for include in project["includes"]
            if include["kind"] == "ANNOTATIONS"
        }
    )
    if not annotation_paths:
        raise ExportError("O manifesto não declara arquivos de ANNOTATIONS.")
    for relative_path in annotation_paths:
        path = root / relative_path
        if not path.is_file():
            raise ExportError(f"Anotação declarada não encontrada: {relative_path}")
        relative_path = path.relative_to(root).as_posix()
        for record in parse_blocks(path):
            record["path"] = relative_path
            if record["kind"] == "SOURCE":
                source_id = record["header"]
                if source_id in sources:
                    raise ExportError(f"SOURCE duplicado: {source_id}")
                sources[source_id] = record
            elif record["kind"] == "ITEM":
                item_id = record.get("identificador_ocorrencia", "")
                if not item_id:
                    raise ExportError(f"ITEM sem identificador_ocorrencia em {relative_path}")
                if item_id in items:
                    raise ExportError(f"ITEM duplicado: {item_id}")
                items[item_id] = record
    if not sources or not items:
        raise ExportError("A exportação exige SOURCEs e ITEMs no projeto.")
    return sources, items


def parse_concepts(root: Path) -> dict[str, dict[str, str]]:
    path = root / "ontologia" / "dominio-eleitoral.syno"
    concepts: dict[str, dict[str, str]] = {}
    for record in parse_blocks(path, "ONTOLOGY"):
        concept_id = record["header"]
        if concept_id in concepts:
            raise ExportError(f"Conceito duplicado: {concept_id}")
        record["path"] = path.relative_to(root).as_posix()
        concepts[concept_id] = record
    if not concepts:
        raise ExportError(f"Nenhum ONTOLOGY encontrado em {path}")
    return concepts


def read_csv(path: Path, required_columns: Iterable[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ExportError(f"CSV não encontrado: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        present = set(reader.fieldnames or [])
        missing = sorted(set(required_columns) - present)
        if missing:
            raise ExportError(f"CSV {path} sem colunas: {', '.join(missing)}")
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def split_codes(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]


def literal_type(field_type: str) -> str:
    if field_type == "DATE":
        return XSD + "date"
    if field_type == "SCALE":
        return XSD + "integer"
    return XSD + "string"


def property_for_field(name: str, field_type: str) -> str:
    if name == "conceitos":
        return syn("hasConcept")
    if name == "conceito_pai":
        return syn("hasParentConcept")
    return syn(camel_case(name))


def add_type(graph: Graph, subject: str, class_iri: str) -> None:
    graph.iri(subject, RDF + "type", class_iri)


def add_text(graph: Graph, subject: str, predicate: str, value: str, language: str) -> None:
    if value:
        graph.literal(subject, predicate, value, language=language)


def media_type_for_path(relative_path: str) -> str:
    """Retorna o tipo de mídia que descreve a entrada canônica."""
    return {
        ".csv": "text/csv",
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".rdf": "application/rdf+xml",
        ".ttl": "text/turtle",
    }.get(Path(relative_path).suffix.lower(), "text/plain")


def add_input_resources(graph: Graph, root: Path, project: dict[str, object], language: str) -> None:
    input_paths = {"projeto.synp", "template.synt", "ontologia/dominio-eleitoral.syno", "ontologia/relacoes-ontologicas.csv", "ontologia/vocabulario-relacoes.csv"}
    input_paths.update(str(include["path"]) for include in project["includes"])
    for relative_path in sorted(input_paths):
        path = root / relative_path
        if not path.is_file():
            raise ExportError(f"Entrada declarada não encontrada: {relative_path}")
        identifier = re.sub(r"[^a-z0-9]+", "_", relative_path.lower()).strip("_")
        input_iri = resource("input", identifier)
        add_type(graph, input_iri, syn("CanonicalInput"))
        graph.literal(input_iri, syn("relativePath"), relative_path, datatype=XSD + "string")
        graph.literal(input_iri, syn("sha256"), hashlib.sha256(path.read_bytes()).hexdigest(), datatype=XSD + "string")
        graph.literal(
            input_iri,
            DCTERMS + "format",
            media_type_for_path(relative_path),
            datatype=XSD + "string",
        )
        graph.iri(ONTOLOGY_IRI, PROV + "wasDerivedFrom", input_iri)


def add_schema(
    graph: Graph,
    template_name: str,
    fields: dict[str, dict[str, object]],
    language: str,
) -> str:
    template_iri = resource("template", template_name)
    add_type(graph, template_iri, syn("SynesisTemplate"))
    add_text(graph, template_iri, RDFS + "label", template_name, language)

    model_classes = {
        "SynesisProject": "Manifesto Synesis do projeto.",
        "SynesisTemplate": "Contrato de campos Synesis.",
        "FieldDefinition": "Definição de campo do template Synesis.",
        "EnumerationValue": "Valor permitido por campo enumerado do Synesis.",
        "Source": "Registro de proveniência Synesis.",
        "Item": "Unidade de evidência ou exemplo Synesis.",
        "OntologyConcept": "Conceito formal da ontologia Synesis.",
        "OntologyRelation": "Relação complementar declarada em CSV.",
        "CanonicalInput": "Arquivo canônico usado na derivação do entregável.",
        "GraphRagProfile": "Políticas derivadas para recuperação aumentada por grafo com revisão humana.",
    }
    for local_name, description in model_classes.items():
        class_iri = syn(local_name)
        add_type(graph, class_iri, OWL + "Class")
        add_text(graph, class_iri, RDFS + "label", local_name, language)
        add_text(graph, class_iri, RDFS + "comment", description, language)

    scope_class = {
        "SOURCE": syn("Source"),
        "ITEM": syn("Item"),
        "ONTOLOGY": syn("OntologyConcept"),
    }
    for name, spec in sorted(fields.items()):
        field_iri = resource("field", name)
        property_iri = property_for_field(name, str(spec["type"]))
        graph.iri(template_iri, syn("definesField"), field_iri)
        add_type(graph, field_iri, syn("FieldDefinition"))
        add_text(graph, field_iri, RDFS + "label", name, language)
        graph.literal(field_iri, syn("fieldName"), name, datatype=XSD + "string")
        graph.literal(field_iri, syn("fieldType"), str(spec["type"]), datatype=XSD + "string")
        graph.literal(field_iri, syn("fieldScope"), str(spec["scope"]), datatype=XSD + "string")
        graph.literal(
            field_iri,
            syn("required"),
            str(spec["requiredness"]) == "required",
            datatype=XSD + "boolean",
        )
        add_text(graph, field_iri, RDFS + "comment", str(spec["description"]), language)
        graph.iri(field_iri, syn("mapsToProperty"), property_iri)
        if spec["format"]:
            graph.literal(field_iri, syn("format"), str(spec["format"]), datatype=XSD + "string")
        if spec["guidelines"]:
            add_text(graph, field_iri, syn("guidelines"), str(spec["guidelines"]), language)

        field_type = str(spec["type"])
        if field_type == "ENUMERATED" or name in {"conceitos", "conceito_pai"}:
            add_type(graph, property_iri, OWL + "ObjectProperty")
            if field_type == "ENUMERATED":
                graph.iri(property_iri, RDFS + "range", syn("EnumerationValue"))
            else:
                graph.iri(property_iri, RDFS + "range", syn("OntologyConcept"))
        else:
            add_type(graph, property_iri, OWL + "DatatypeProperty")
            graph.iri(property_iri, RDFS + "range", literal_type(field_type))
        graph.iri(property_iri, RDFS + "domain", scope_class[str(spec["scope"])])
        add_text(graph, property_iri, RDFS + "comment", str(spec["description"]), language)

        for value in spec["values"]:
            value_id = str(value["id"])
            value_iri = resource("value", f"{name}/{value_id}")
            graph.iri(field_iri, syn("allowsValue"), value_iri)
            add_type(graph, value_iri, syn("EnumerationValue"))
            graph.literal(value_iri, SKOS + "notation", value_id, datatype=XSD + "string")
            add_text(graph, value_iri, RDFS + "label", value_id, language)
            add_text(graph, value_iri, SKOS + "definition", str(value["description"]), language)
            graph.iri(value_iri, syn("definedByField"), field_iri)

    graph.iri(syn("hasSource"), RDFS + "domain", syn("Item"))
    graph.iri(syn("hasSource"), RDFS + "range", syn("Source"))
    add_type(graph, syn("hasSource"), OWL + "ObjectProperty")
    graph.iri(syn("isEvidencedBy"), RDFS + "domain", syn("OntologyRelation"))
    graph.iri(syn("isEvidencedBy"), RDFS + "range", syn("Item"))
    add_type(graph, syn("isEvidencedBy"), OWL + "ObjectProperty")
    graph.iri(syn("hasGraphRagProfile"), RDFS + "domain", OWL + "Ontology")
    graph.iri(syn("hasGraphRagProfile"), RDFS + "range", syn("GraphRagProfile"))
    add_type(graph, syn("hasGraphRagProfile"), OWL + "ObjectProperty")
    for property_name in GRAPH_RAG_ANNOTATION_PROPERTIES:
        property_iri = syn(property_name)
        add_type(graph, property_iri, OWL + "AnnotationProperty")
        add_text(graph, property_iri, RDFS + "label", property_name, language)
    return template_iri


def add_field_value(
    graph: Graph,
    subject: str,
    field_name: str,
    value: str,
    fields: dict[str, dict[str, object]],
    language: str,
) -> None:
    if not value or field_name not in fields:
        return
    spec = fields[field_name]
    field_type = str(spec["type"])
    predicate = property_for_field(field_name, field_type)
    if field_type == "ENUMERATED":
        graph.iri(subject, predicate, resource("value", f"{field_name}/{value}"))
    else:
        datatype = literal_type(field_type)
        graph.literal(subject, predicate, value, datatype=datatype)


def add_sources_and_items(
    graph: Graph,
    sources: dict[str, dict[str, str]],
    items: dict[str, dict[str, str]],
    concepts: dict[str, dict[str, str]],
    fields: dict[str, dict[str, object]],
    language: str,
    project_status: str,
) -> None:
    for source_id, source in sorted(sources.items()):
        source_iri = resource("source", source_id)
        add_type(graph, source_iri, OWL + "NamedIndividual")
        add_type(graph, source_iri, syn("Source"))
        graph.literal(source_iri, DCTERMS + "identifier", source_id, datatype=XSD + "string")
        graph.literal(source_iri, syn("declaredIn"), source["path"], datatype=XSD + "string")
        for name, value in source.items():
            if name in {"kind", "header", "path"}:
                continue
            add_field_value(graph, source_iri, name, value, fields, language)
            if name == "descricao_fonte":
                add_text(graph, source_iri, DCTERMS + "description", value, language)
            elif name == "url" and value.startswith(("http://", "https://")):
                graph.iri(source_iri, RDFS + "seeAlso", value)
            elif name == "identificador_externo":
                graph.literal(source_iri, DCTERMS + "identifier", value, datatype=XSD + "string")
        source_type = source.get("tipo_fonte", "")
        legal_source = source_type in {"legislacao", "jurisprudencia"}
        graph.literal(
            source_iri,
            syn("graph_rag_source_role"),
            "legal_anchor" if legal_source else "context_source",
            datatype=XSD + "string",
        )
        graph.literal(
            source_iri,
            syn("graph_rag_legal_source"),
            legal_source,
            datatype=XSD + "boolean",
        )
        add_text(
            graph,
            source_iri,
            syn("graph_rag_citation_guidance"),
            "Use para ancorar a interpretação jurídica declarada; não deduza crime, "
            "ilicitude, sanção ou veracidade do caso concreto."
            if legal_source
            else "Use como contexto de proveniência e cite o SOURCE junto do ITEM.",
            language,
        )

    for item_id, item in sorted(items.items()):
        source_id = item["header"]
        if source_id not in sources:
            raise ExportError(f"ITEM {item_id} referencia SOURCE inexistente: {source_id}")
        item_iri = resource("item", item_id)
        add_type(graph, item_iri, OWL + "NamedIndividual")
        add_type(graph, item_iri, syn("Item"))
        graph.literal(item_iri, DCTERMS + "identifier", item_id, datatype=XSD + "string")
        graph.literal(item_iri, syn("declaredIn"), item["path"], datatype=XSD + "string")
        graph.iri(item_iri, syn("hasSource"), resource("source", source_id))
        graph.iri(item_iri, DCTERMS + "source", resource("source", source_id))
        for name, value in item.items():
            if name in {"kind", "header", "path"}:
                continue
            if name == "conceitos":
                for concept_id in split_codes(value):
                    if concept_id not in concepts:
                        raise ExportError(f"ITEM {item_id} referencia conceito inexistente: {concept_id}")
                    graph.iri(item_iri, syn("hasConcept"), resource("concept", concept_id))
                continue
            add_field_value(graph, item_iri, name, value, fields, language)
            if name == "conteudo":
                add_text(graph, item_iri, DCTERMS + "description", value, language)
            elif name == "identificador_ocorrencia":
                graph.literal(item_iri, DCTERMS + "identifier", value, datatype=XSD + "string")
        review_status = item.get("status_revisao", "")
        graph.literal(
            item_iri,
            syn("graph_rag_evidence_role"),
            item.get("funcao_item", ""),
            datatype=XSD + "string",
        )
        graph.literal(
            item_iri,
            syn("graph_rag_evidence_review_status"),
            review_status,
            datatype=XSD + "string",
        )
        graph.literal(
            item_iri,
            syn("graph_rag_evidence_reviewed"),
            review_status == "revisado",
            datatype=XSD + "boolean",
        )
        graph.literal(
            item_iri,
            syn("graph_rag_human_review_required"),
            project_status != "aprovado" or review_status not in {"revisado", "aprovado"},
            datatype=XSD + "boolean",
        )
        graph.literal(
            item_iri,
            syn("graph_rag_citation_source_id"),
            source_id,
            datatype=XSD + "string",
        )
        add_text(
            graph,
            item_iri,
            syn("graph_rag_citation_guidance"),
            "Cite este ITEM com seu SOURCE de origem e descreva como ambos apoiam a decisão.",
            language,
        )


def add_concepts(
    graph: Graph,
    concepts: dict[str, dict[str, str]],
    fields: dict[str, dict[str, object]],
    language: str,
    project_status: str,
) -> None:
    for concept_id, concept in sorted(concepts.items()):
        concept_iri = resource("concept", concept_id)
        add_type(graph, concept_iri, OWL + "Class")
        add_type(graph, concept_iri, OWL + "NamedIndividual")
        add_type(graph, concept_iri, SKOS + "Concept")
        add_type(graph, concept_iri, syn("OntologyConcept"))
        graph.literal(concept_iri, SKOS + "notation", concept_id, datatype=XSD + "string")
        graph.iri(concept_iri, SKOS + "inScheme", ONTOLOGY_IRI)
        graph.literal(concept_iri, syn("declaredIn"), concept["path"], datatype=XSD + "string")
        for name, value in concept.items():
            if name in {"kind", "header", "path"}:
                continue
            if name == "conceito_pai":
                if value not in concepts:
                    raise ExportError(f"Conceito {concept_id} referencia pai inexistente: {value}")
                parent_iri = resource("concept", value)
                graph.iri(concept_iri, syn("hasParentConcept"), parent_iri)
                graph.iri(concept_iri, RDFS + "subClassOf", parent_iri)
                graph.iri(concept_iri, SKOS + "broader", parent_iri)
                continue
            add_field_value(graph, concept_iri, name, value, fields, language)
            if name == "rotulo_preferido":
                add_text(graph, concept_iri, RDFS + "label", value, language)
                add_text(graph, concept_iri, SKOS + "prefLabel", value, language)
            elif name == "definicao_operacional":
                add_text(graph, concept_iri, RDFS + "comment", value, language)
                add_text(graph, concept_iri, SKOS + "definition", value, language)
            elif name == "sinonimos":
                for synonym in split_codes(value):
                    add_text(graph, concept_iri, SKOS + "altLabel", synonym, language)
        operational = concept.get("tipo_conceito") in {
            "classificatorio",
            "fronteira_exclusao",
            "enquadramento_transversal",
        }
        graph.literal(
            concept_iri,
            syn("graph_rag_classification_role"),
            "operational_candidate" if operational else "structural_context",
            datatype=XSD + "string",
        )
        graph.literal(
            concept_iri,
            syn("graph_rag_hierarchy_role"),
            concept.get("papel_hierarquico", ""),
            datatype=XSD + "string",
        )
        graph.literal(
            concept_iri,
            syn("graph_rag_structural_context_only"),
            not operational,
            datatype=XSD + "boolean",
        )
        graph.literal(
            concept_iri,
            syn("graph_rag_human_review_required"),
            project_status != "aprovado",
            datatype=XSD + "boolean",
        )
        for signal in split_codes(concept.get("sinais_observaveis", "")):
            add_text(graph, concept_iri, syn("graph_rag_observable_signal"), signal, language)
        add_text(
            graph,
            concept_iri,
            syn("graph_rag_classification_guidance"),
            "Candidato operacional: só selecione quando a definição e o critério de "
            "inclusão forem compatíveis com características observáveis do conteúdo; "
            "confira também o critério de exclusão."
            if operational
            else "Contexto estrutural: use para explicar a posição hierárquica, mas não o "
            "retorne como categoria operacional.",
            language,
        )


def add_relations(
    graph: Graph,
    root: Path,
    concepts: dict[str, dict[str, str]],
    items: dict[str, dict[str, str]],
    language: str,
) -> int:
    vocabulary_rows = read_csv(
        root / "ontologia" / "vocabulario-relacoes.csv",
        {
            "tipo_relacao",
            "rotulo_preferido",
            "direcao",
            "definicao",
            "status_revisao",
            "condicoes_uso",
            "condicoes_nao_uso",
        },
    )
    vocabulary = {row["tipo_relacao"]: row for row in vocabulary_rows}
    relation_rows = read_csv(
        root / "ontologia" / "relacoes-ontologicas.csv",
        {
            "relacao_id",
            "conceito_origem",
            "tipo_relacao",
            "conceito_destino",
            "status_revisao",
            "justificativa",
            "itens_evidencia",
            "notas",
        },
    )

    for relation_type, definition in sorted(vocabulary.items()):
        property_iri = syn(camel_case(relation_type))
        add_type(graph, property_iri, OWL + "ObjectProperty")
        graph.iri(property_iri, RDFS + "domain", syn("OntologyConcept"))
        graph.iri(property_iri, RDFS + "range", syn("OntologyConcept"))
        graph.literal(property_iri, syn("relationTypeCode"), relation_type, datatype=XSD + "string")
        add_text(graph, property_iri, RDFS + "label", definition["rotulo_preferido"], language)
        add_text(graph, property_iri, RDFS + "comment", definition["definicao"], language)
        graph.literal(property_iri, syn("direction"), definition["direcao"], datatype=XSD + "string")
        graph.literal(property_iri, syn("reviewStatus"), definition["status_revisao"], datatype=XSD + "string")
        add_text(graph, property_iri, syn("conditionsOfUse"), definition["condicoes_uso"], language)
        add_text(graph, property_iri, syn("conditionsOfNonUse"), definition["condicoes_nao_uso"], language)

    seen_ids: set[str] = set()
    for row in relation_rows:
        relation_id = row["relacao_id"]
        if relation_id in seen_ids:
            raise ExportError(f"Relação complementar duplicada: {relation_id}")
        seen_ids.add(relation_id)
        origin_id = row["conceito_origem"]
        target_id = row["conceito_destino"]
        relation_type = row["tipo_relacao"]
        if origin_id not in concepts or target_id not in concepts:
            raise ExportError(f"Relação {relation_id} referencia conceito inexistente")
        if relation_type not in vocabulary:
            raise ExportError(f"Relação {relation_id} usa tipo ausente no vocabulário: {relation_type}")
        relation_iri = resource("relation", relation_id)
        relation_property = syn(camel_case(relation_type))
        origin_iri = resource("concept", origin_id)
        target_iri = resource("concept", target_id)
        add_type(graph, relation_iri, OWL + "NamedIndividual")
        add_type(graph, relation_iri, syn("OntologyRelation"))
        graph.literal(relation_iri, syn("relationId"), relation_id, datatype=XSD + "string")
        graph.iri(relation_iri, syn("relationOrigin"), origin_iri)
        graph.iri(relation_iri, syn("relationTarget"), target_iri)
        graph.iri(relation_iri, syn("relationProperty"), relation_property)
        graph.literal(relation_iri, syn("relationTypeCode"), relation_type, datatype=XSD + "string")
        graph.literal(relation_iri, syn("reviewStatus"), row["status_revisao"], datatype=XSD + "string")
        add_text(graph, relation_iri, syn("justification"), row["justificativa"], language)
        add_text(graph, relation_iri, syn("notes"), row["notas"], language)
        for item_id in split_codes(row["itens_evidencia"]):
            if item_id not in items:
                raise ExportError(f"Relação {relation_id} referencia ITEM inexistente: {item_id}")
            graph.iri(relation_iri, syn("isEvidencedBy"), resource("item", item_id))
        if row["status_revisao"] == "aprovado":
            graph.iri(origin_iri, relation_property, target_iri)
    return len(relation_rows)


def add_graph_rag_profile(graph: Graph, project_status: str, language: str) -> None:
    """Materializa a política derivada de uso do grafo por uma LLM."""
    profile_iri = resource("profile", "classification_assistance")
    add_type(graph, profile_iri, OWL + "NamedIndividual")
    add_type(graph, profile_iri, syn("GraphRagProfile"))
    graph.literal(profile_iri, syn("graph_rag_profile_id"), "classification_assistance", datatype=XSD + "string")
    add_text(
        graph,
        profile_iri,
        syn("graph_rag_purpose"),
        "Contexto recuperável para classificação assistida e revisão humana.",
        language,
    )
    graph.literal(profile_iri, syn("graph_rag_project_status"), project_status, datatype=XSD + "string")
    graph.literal(
        profile_iri,
        syn("graph_rag_human_review_required"),
        project_status != "aprovado",
        datatype=XSD + "boolean",
    )
    add_text(
        graph,
        profile_iri,
        syn("graph_rag_selection_policy"),
        "Priorize conceitos com tipo_conceito classificatorio como candidatos; use conceitos estruturais como contexto hierárquico, não como rótulos operacionais.",
        language,
    )
    add_text(
        graph,
        profile_iri,
        syn("graph_rag_evidence_policy"),
        "Cite ITEM e SOURCE; ITEMs pendentes não são precedentes aprovados; fontes jurídicas ancoram a interpretação, mas não determinam crime, ilicitude, sanção ou veracidade.",
        language,
    )
    graph.iri(ONTOLOGY_IRI, syn("hasGraphRagProfile"), profile_iri)


def add_private_entity_layer(graph: Graph, layer: PrivateEntityLayer, language: str) -> dict[str, int]:
    """Adiciona entidades contextuais auxiliares sem vinculá-las diretamente a conceitos."""
    layer_iri = resource("private-layer", "entidades-nomeadas-2026-07-27")
    model_classes = {
        "PrivateEntityLayer": "Camada contextual auxiliar derivada de entidades nomeadas.",
        "NamedEntity": "Entidade nomeada curada e sujeita a revisão.",
        "EntityAlias": "Forma superficial candidata de uma entidade nomeada.",
        "LexicalCue": "Pista lexical para recuperação contextual, não classificação automática.",
        "EntityMention": "Menção contextual auxiliar sem reprodução do texto integral do corpus.",
    }
    for local_name, description in model_classes.items():
        class_iri = syn(local_name)
        add_type(graph, class_iri, OWL + "Class")
        add_text(graph, class_iri, RDFS + "label", local_name, language)
        add_text(graph, class_iri, RDFS + "comment", description, language)

    object_properties = {
        "hasEntityAlias": (syn("NamedEntity"), syn("EntityAlias")),
        "candidateEntity": (syn("EntityMention"), syn("NamedEntity")),
        "canonicalEntity": (syn("EntityMention"), syn("NamedEntity")),
        "hasLexicalCue": (syn("EntityMention"), syn("LexicalCue")),
    }
    for local_name, (domain, range_) in object_properties.items():
        property_iri = syn(local_name)
        add_type(graph, property_iri, OWL + "ObjectProperty")
        graph.iri(property_iri, RDFS + "domain", domain)
        graph.iri(property_iri, RDFS + "range", range_)

    add_type(graph, layer_iri, OWL + "NamedIndividual")
    add_type(graph, layer_iri, syn("PrivateEntityLayer"))
    graph.literal(layer_iri, syn("visibility"), "private", datatype=XSD + "string")
    graph.literal(layer_iri, syn("inputSha256"), layer.input_sha256, datatype=XSD + "string")
    graph.iri(ONTOLOGY_IRI, syn("hasPrivateEntityLayer"), layer_iri)

    for row in layer.entities:
        entity_iri = resource("entity", row["entity_id"])
        add_type(graph, entity_iri, OWL + "NamedIndividual")
        add_type(graph, entity_iri, syn("NamedEntity"))
        graph.literal(entity_iri, DCTERMS + "identifier", row["entity_id"], datatype=XSD + "string")
        add_text(graph, entity_iri, RDFS + "label", row["rotulo_preferido"], language)
        graph.literal(entity_iri, syn("nerType"), row["tipo_ner"], datatype=XSD + "string")
        graph.literal(entity_iri, syn("reviewStatus"), row["status_revisao"], datatype=XSD + "string")
        graph.iri(layer_iri, syn("hasNamedEntity"), entity_iri)

    for row in layer.aliases:
        alias_iri = resource("alias", row["alias_id"])
        entity_iri = resource("entity", row["entity_id"])
        add_type(graph, alias_iri, OWL + "NamedIndividual")
        add_type(graph, alias_iri, syn("EntityAlias"))
        graph.literal(alias_iri, DCTERMS + "identifier", row["alias_id"], datatype=XSD + "string")
        add_text(graph, alias_iri, RDFS + "label", row["forma_superficial"], language)
        graph.literal(alias_iri, syn("reviewStatus"), row["status_revisao"], datatype=XSD + "string")
        graph.iri(entity_iri, syn("hasEntityAlias"), alias_iri)
        graph.iri(alias_iri, syn("candidateEntity"), entity_iri)
        graph.iri(layer_iri, syn("hasEntityAlias"), alias_iri)

    for row in layer.lexical_cues:
        cue_iri = resource("cue", row["cue_id"])
        add_type(graph, cue_iri, OWL + "NamedIndividual")
        add_type(graph, cue_iri, syn("LexicalCue"))
        graph.literal(cue_iri, DCTERMS + "identifier", row["cue_id"], datatype=XSD + "string")
        add_text(graph, cue_iri, RDFS + "label", row["forma_normalizada"], language)
        graph.literal(cue_iri, syn("nerType"), row["tipo_ner"], datatype=XSD + "string")
        graph.literal(cue_iri, syn("reviewStatus"), row["status_revisao"], datatype=XSD + "string")
        graph.literal(cue_iri, syn("contextualRetrievalOnly"), True, datatype=XSD + "boolean")
        graph.iri(layer_iri, syn("hasLexicalCue"), cue_iri)

    for row in layer.mentions:
        mention_iri = resource("mention", row["mention_id"])
        add_type(graph, mention_iri, OWL + "NamedIndividual")
        add_type(graph, mention_iri, syn("EntityMention"))
        graph.literal(mention_iri, DCTERMS + "identifier", row["mention_id"], datatype=XSD + "string")
        graph.literal(mention_iri, syn("tweetId"), row["tweet_id"], datatype=XSD + "string")
        graph.literal(mention_iri, syn("nerType"), row["entity_label_original"], datatype=XSD + "string")
        add_text(graph, mention_iri, syn("surfaceForm"), row["entity_text"], language)
        graph.literal(mention_iri, syn("startOffset"), row["start"], datatype=XSD + "integer")
        graph.literal(mention_iri, syn("endOffset"), row["end"], datatype=XSD + "integer")
        graph.literal(mention_iri, syn("externalClassification"), row["external_classification"], datatype=XSD + "string")
        if row["candidate_entity_id"]:
            graph.iri(mention_iri, syn("candidateEntity"), resource("entity", row["candidate_entity_id"]))
        if row["canonical_entity_id"]:
            graph.iri(mention_iri, syn("canonicalEntity"), resource("entity", row["canonical_entity_id"]))
        if row["cue_id"]:
            graph.iri(mention_iri, syn("hasLexicalCue"), resource("cue", row["cue_id"]))
        graph.iri(layer_iri, syn("hasEntityMention"), mention_iri)

    return {
        "private_entity_count": len(layer.entities),
        "private_alias_count": len(layer.aliases),
        "private_lexical_cue_count": len(layer.lexical_cues),
        "private_mention_count": len(layer.mentions),
    }


def build_graph(
    root: Path,
    *,
    include_private_entities: bool = False,
) -> tuple[Graph, dict[str, int]]:
    root = root.resolve()
    project = parse_project(root / "projeto.synp")
    fields, _ = parse_template(root / "template.synt")
    concepts = parse_concepts(root)
    sources, items = parse_annotation_records(root, project)
    metadata = project["metadata"]
    language = str(metadata.get("language", "pt-BR"))
    graph = Graph()

    add_type(graph, ONTOLOGY_IRI, OWL + "Ontology")
    graph.literal(ONTOLOGY_IRI, OWL + "versionInfo", str(metadata.get("version", "")), datatype=XSD + "string")
    graph.literal(ONTOLOGY_IRI, syn("projectStatus"), str(metadata.get("status", "")), datatype=XSD + "string")
    graph.literal(ONTOLOGY_IRI, DCTERMS + "language", language, datatype=XSD + "language")
    add_text(graph, ONTOLOGY_IRI, DCTERMS + "title", "Ontologia do Domínio Eleitoral", language)
    add_text(graph, ONTOLOGY_IRI, DCTERMS + "description", str(project["description"]), language)
    graph.literal(ONTOLOGY_IRI, syn("namespace"), NAMESPACE, datatype=XSD + "anyURI")

    project_iri = resource("project", str(project["name"]))
    add_type(graph, project_iri, OWL + "NamedIndividual")
    add_type(graph, project_iri, syn("SynesisProject"))
    graph.literal(project_iri, DCTERMS + "identifier", str(project["name"]), datatype=XSD + "string")
    graph.literal(project_iri, syn("projectStatus"), str(metadata.get("status", "")), datatype=XSD + "string")
    graph.literal(project_iri, DCTERMS + "language", language, datatype=XSD + "language")
    add_text(graph, project_iri, DCTERMS + "description", str(project["description"]), language)
    graph.iri(project_iri, syn("exportsOntology"), ONTOLOGY_IRI)

    template_iri = add_schema(graph, "ontologia_dominio_eleitoral", fields, language)
    graph.iri(project_iri, syn("usesTemplate"), template_iri)
    add_input_resources(graph, root, project, language)
    add_concepts(graph, concepts, fields, language, str(metadata.get("status", "")))
    add_sources_and_items(graph, sources, items, concepts, fields, language, str(metadata.get("status", "")))
    relation_count = add_relations(graph, root, concepts, items, language)
    add_graph_rag_profile(graph, str(metadata.get("status", "")), language)
    private_counts = (
        add_private_entity_layer(graph, load_private_entity_layer(root), language)
        if include_private_entities
        else {}
    )
    graph.literal(
        ONTOLOGY_IRI,
        syn("privateEntityLayerIncluded"),
        include_private_entities,
        datatype=XSD + "boolean",
    )

    counts = {
        "concept_count": len(concepts),
        "source_count": len(sources),
        "item_count": len(items),
        "field_count": len(fields),
        "relation_count": relation_count,
    }
    counts.update(private_counts)
    for name, value in counts.items():
        graph.literal(ONTOLOGY_IRI, syn(camel_case(name)), value, datatype=XSD + "integer")
    counts["triple_count"] = len(graph.triples) + 1
    graph.literal(
        ONTOLOGY_IRI,
        syn("tripleCount"),
        counts["triple_count"],
        datatype=XSD + "integer",
    )
    return graph, counts


def object_sort_key(value: Iri | Literal) -> tuple[str, str, str, str]:
    if isinstance(value, Iri):
        return ("0", value.value, "", "")
    return ("1", value.value, value.datatype or "", value.language or "")


def sorted_triples(triples: Iterable[Triple]) -> list[Triple]:
    return sorted(triples, key=lambda triple: (triple.subject, triple.predicate, object_sort_key(triple.object)))


def predicate_sort_key(predicate: str) -> tuple[int, str]:
    return (0 if predicate == RDF + "type" else 1, predicate)


def compact_iri(value: str) -> str:
    for prefix, namespace in PREFIXES.items():
        if value.startswith(namespace):
            local_name = value[len(namespace) :]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", local_name):
                return f"{prefix}:{local_name}"
    return f"<{value}>"


def turtle_literal(value: Literal) -> str:
    rendered = json.dumps(value.value, ensure_ascii=False)
    if value.language:
        return f"{rendered}@{value.language}"
    if value.datatype:
        return f"{rendered}^^{compact_iri(value.datatype)}"
    return rendered


def serialize_turtle(graph: Graph) -> str:
    lines = [f"@prefix {prefix}: <{iri}> ." for prefix, iri in PREFIXES.items()]
    lines.extend(["", "# Gerado por ferramentas/exportar_ontologia_owl_rdf.py. Não editar manualmente.", ""])
    for subject, triples in sorted(graph.by_subject().items()):
        triples = sorted(triples, key=lambda triple: (predicate_sort_key(triple.predicate), object_sort_key(triple.object)))
        lines.append(compact_iri(subject))
        for index, triple in enumerate(triples):
            predicate = "a" if triple.predicate == RDF + "type" else compact_iri(triple.predicate)
            object_text = compact_iri(triple.object.value) if isinstance(triple.object, Iri) else turtle_literal(triple.object)
            end = " ." if index == len(triples) - 1 else " ;"
            lines.append(f"    {predicate} {object_text}{end}")
        lines.append("")
    return "\n".join(lines)


def split_qname(value: str) -> str:
    for namespace in PREFIXES.values():
        if value.startswith(namespace):
            local_name = value[len(namespace) :]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9._-]*", local_name):
                return f"{{{namespace}}}{local_name}"
    raise ExportError(f"IRI não pode ser usado como QName RDF/XML: {value}")


def selected_rdfxml_tag(triples: list[Triple]) -> tuple[str, Triple | None]:
    type_to_tag = {
        OWL + "Ontology": OWL + "Ontology",
        OWL + "Class": OWL + "Class",
        OWL + "ObjectProperty": OWL + "ObjectProperty",
        OWL + "DatatypeProperty": OWL + "DatatypeProperty",
        OWL + "AnnotationProperty": OWL + "AnnotationProperty",
    }
    for triple in triples:
        if triple.predicate == RDF + "type" and isinstance(triple.object, Iri):
            tag = type_to_tag.get(triple.object.value)
            if tag:
                return tag, triple
    return RDF + "Description", None


def serialize_rdfxml(graph: Graph) -> str:
    root = ET.Element(f"{{{RDF}}}RDF")
    for subject, triples in sorted(graph.by_subject().items()):
        ordered = sorted(triples, key=lambda triple: (predicate_sort_key(triple.predicate), object_sort_key(triple.object)))
        tag, consumed_type = selected_rdfxml_tag(ordered)
        node = ET.SubElement(root, split_qname(tag), {f"{{{RDF}}}about": subject})
        for triple in ordered:
            if triple == consumed_type:
                continue
            element = ET.SubElement(node, split_qname(triple.predicate))
            if isinstance(triple.object, Iri):
                element.set(f"{{{RDF}}}resource", triple.object.value)
            else:
                if triple.object.language:
                    element.set("{http://www.w3.org/XML/1998/namespace}lang", triple.object.language)
                elif triple.object.datatype:
                    element.set(f"{{{RDF}}}datatype", triple.object.datatype)
                element.text = triple.object.value
    ET.indent(root, space="  ")
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n" + ET.tostring(root, encoding="unicode") + "\n"


def write_output(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."), help="Raiz do projeto Synesis.")
    parser.add_argument("--owl-output", type=Path, help="Destino do OWL em RDF/XML.")
    parser.add_argument("--rdf-output", type=Path, help="Destino do RDF/XML.")
    parser.add_argument("--turtle-output", type=Path, help="Destino do RDF em Turtle.")
    parser.add_argument(
        "--include-private-entities",
        action="store_true",
        help="Inclui a camada contextual auxiliar curada de entidades nomeadas na saída derivada.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    owl_output = args.owl_output or root / "Entregáveis" / "OWL" / "ontologia-dominio-eleitoral.owl"
    rdf_output = args.rdf_output or root / "Entregáveis" / "RDF" / "ontologia-dominio-eleitoral.rdf"
    turtle_output = args.turtle_output or root / "Entregáveis" / "RDF" / "ontologia-dominio-eleitoral.ttl"
    try:
        graph, counts = build_graph(root, include_private_entities=args.include_private_entities)
        rdfxml = serialize_rdfxml(graph)
        write_output(owl_output, rdfxml)
        write_output(rdf_output, rdfxml)
        write_output(turtle_output, serialize_turtle(graph))
    except ExportError as error:
        print(f"ERRO: {error}", file=sys.stderr)
        return 1
    print(
        "OWL_RDF_EXPORTADO "
        + " ".join(f"{name}={value}" for name, value in sorted(counts.items()))
        + f" owl={owl_output} rdf={rdf_output} turtle={turtle_output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
