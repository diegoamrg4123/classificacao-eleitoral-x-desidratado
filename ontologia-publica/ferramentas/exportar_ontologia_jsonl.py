#!/usr/bin/env python3
"""Exporta a descrição formal Synesis para um pacote JSONL detalhado.

A saída é somente leitura e derivada das fontes canônicas. Cada linha é um
registro JSON independente, com tipo, identificador e proveniência explícitos.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from camada_contextual_auxiliar import PrivateEntityLayer, load_private_entity_layer
from exportar_ontologia_owl_rdf import (
    ExportError,
    parse_annotation_records,
    parse_concepts,
    parse_project,
    parse_template,
    read_csv,
    split_codes,
)


SCHEMA_VERSION = "1.1"
EXPORTER_PATH = "ferramentas/exportar_ontologia_jsonl.py"
RELATION_VOCABULARY_COLUMNS = {
    "tipo_relacao",
    "rotulo_preferido",
    "direcao",
    "definicao",
    "status_revisao",
    "condicoes_uso",
    "condicoes_nao_uso",
}
RELATION_COLUMNS = {
    "relacao_id",
    "conceito_origem",
    "tipo_relacao",
    "conceito_destino",
    "status_revisao",
    "justificativa",
    "itens_evidencia",
    "notas",
}
CONTROL_RECORD_FIELDS = {"kind", "header", "path"}


def canonical_input_paths(project: dict[str, Any]) -> list[str]:
    """Lista todas as entradas formais usadas pelo exportador."""
    paths = {
        "projeto.synp",
        "template.synt",
        "ontologia/dominio-eleitoral.syno",
        "ontologia/relacoes-ontologicas.csv",
        "ontologia/vocabulario-relacoes.csv",
    }
    paths.update(str(include["path"]) for include in project["includes"])
    return sorted(paths)


def provenance(relative_path: str, *, role: str) -> dict[str, str]:
    return {
        "canonical_role": role,
        "source_file": relative_path,
    }


def hierarchy_path(
    concept_id: str,
    concepts: dict[str, dict[str, str]],
) -> list[str]:
    """Retorna o caminho da raiz ao conceito, rejeitando ciclos."""
    path = [concept_id]
    seen = {concept_id}
    current_id = concept_id
    while parent_id := concepts[current_id].get("conceito_pai", ""):
        if parent_id not in concepts:
            raise ExportError(f"Conceito {current_id} referencia pai inexistente: {parent_id}")
        if parent_id in seen:
            raise ExportError(f"Ciclo detectado na hierarquia ontológica: {concept_id}")
        path.append(parent_id)
        seen.add(parent_id)
        current_id = parent_id
    return list(reversed(path))


def record_fields(record: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in sorted(record.items())
        if key not in CONTROL_RECORD_FIELDS
    }


def graph_rag_profile(project_status: str) -> dict[str, Any]:
    """Retorna políticas derivadas para consumo seguro por GraphRAG."""
    return {
        "profile_id": "classification_assistance",
        "purpose": "contexto recuperável para classificação assistida e revisão humana",
        "project_status": project_status,
        "human_review_required": project_status != "aprovado",
        "selection_policy": {
            "operational_concept_types": [
                "classificatorio",
                "fronteira_exclusao",
                "enquadramento_transversal",
            ],
            "structural_concept_type": "estrutural",
            "structural_concepts_are_context_only": True,
            "structural_context_must_not_be_returned_as_operational_category": True,
        },
        "evidence_policy": {
            "cite_item_and_source": True,
            "pending_items_are_not_approved_precedent": True,
            "legal_sources_anchor_interpretation_only": True,
        },
    }


def concept_graph_rag_projection(
    concept: dict[str, str],
    project_status: str,
) -> dict[str, Any]:
    operational = concept.get("tipo_conceito") in {
        "classificatorio",
        "fronteira_exclusao",
        "enquadramento_transversal",
    }
    signals = split_codes(concept.get("sinais_observaveis", ""))
    if operational:
        guidance = (
            "Candidato operacional: só selecione quando a definição e o critério de "
            "inclusão forem compatíveis com características observáveis do conteúdo; "
            "confira também o critério de exclusão."
        )
    else:
        guidance = (
            "Contexto estrutural: use para explicar a posição hierárquica, mas não o "
            "retorne como categoria operacional."
        )
    return {
        "classification_role": "operational_candidate" if operational else "structural_context",
        "hierarchy_role": concept.get("papel_hierarquico", ""),
        "structural_context_only": not operational,
        "human_review_required": project_status != "aprovado",
        "observable_signals": signals,
        "classification_guidance": guidance,
    }


def source_graph_rag_projection(source: dict[str, str]) -> dict[str, Any]:
    source_type = source.get("tipo_fonte", "")
    legal_source = source_type in {"legislacao", "jurisprudencia"}
    return {
        "source_role": "legal_anchor" if legal_source else "context_source",
        "legal_source": legal_source,
        "citation_guidance": (
            "Use para ancorar a interpretação jurídica declarada; não deduza crime, "
            "ilicitude, sanção ou veracidade do caso concreto."
            if legal_source
            else "Use como contexto de proveniência e cite o SOURCE junto do ITEM."
        ),
    }


def item_graph_rag_projection(
    item: dict[str, str],
    source_id: str,
    project_status: str,
) -> dict[str, Any]:
    review_status = item.get("status_revisao", "")
    return {
        "evidence_role": item.get("funcao_item", ""),
        "evidence_review_status": review_status,
        "evidence_reviewed": review_status == "revisado",
        "human_review_required": project_status != "aprovado" or review_status not in {"revisado", "aprovado"},
        "citation_source_id": source_id,
        "citation_guidance": "Cite este ITEM com seu SOURCE de origem e descreva como ambos apoiam a decisão.",
    }


def input_file_records(root: Path, project: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for relative_path in canonical_input_paths(project):
        path = root / relative_path
        if not path.is_file():
            raise ExportError(f"Entrada declarada não encontrada: {relative_path}")
        payload = path.read_bytes()
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "input_file",
                "id": f"input_file:{relative_path}",
                "relative_path": relative_path,
                "extension": path.suffix.lower(),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "provenance": provenance(relative_path, role="canonical_input"),
            }
        )
    return records


def template_field_records(fields: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for field_id, specification in sorted(fields.items()):
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "template_field",
                "id": f"template_field:{field_id}",
                "field_id": field_id,
                "field_type": specification["type"],
                "scope": specification["scope"],
                "requiredness": specification["requiredness"],
                "description": specification["description"],
                "format": specification["format"],
                "guidelines": specification["guidelines"],
                "allowed_values": specification["values"],
                "provenance": provenance("template.synt", role="template_field_definition"),
            }
        )
    return records


def concept_records(
    concepts: dict[str, dict[str, str]],
    project_status: str,
) -> list[dict[str, Any]]:
    children: dict[str, list[str]] = {concept_id: [] for concept_id in concepts}
    for concept_id, concept in concepts.items():
        parent_id = concept.get("conceito_pai", "")
        if parent_id:
            if parent_id not in children:
                raise ExportError(f"Conceito {concept_id} referencia pai inexistente: {parent_id}")
            children[parent_id].append(concept_id)

    records = []
    for concept_id, concept in sorted(concepts.items()):
        parent_id = concept.get("conceito_pai") or None
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "ontology_concept",
                "id": f"ontology_concept:{concept_id}",
                "concept_id": concept_id,
                "fields": record_fields(concept),
                "parent_concept_id": parent_id,
                "child_concept_ids": sorted(children[concept_id]),
                "hierarchy_path": hierarchy_path(concept_id, concepts),
                "graph_rag": concept_graph_rag_projection(concept, project_status),
                "provenance": provenance(concept["path"], role="ontology_declaration"),
            }
        )
    return records


def source_records(sources: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "source",
            "id": f"source:{source_id}",
            "source_id": source_id,
            "fields": record_fields(source),
            "graph_rag": source_graph_rag_projection(source),
            "provenance": provenance(source["path"], role="source_declaration"),
        }
        for source_id, source in sorted(sources.items())
    ]


def item_records(
    items: dict[str, dict[str, str]],
    sources: dict[str, dict[str, str]],
    concepts: dict[str, dict[str, str]],
    project_status: str,
) -> list[dict[str, Any]]:
    records = []
    for item_id, item in sorted(items.items()):
        source_id = item["header"]
        if source_id not in sources:
            raise ExportError(f"ITEM {item_id} referencia SOURCE inexistente: {source_id}")
        concept_ids = split_codes(item.get("conceitos", ""))
        unknown_concepts = sorted(set(concept_ids) - set(concepts))
        if unknown_concepts:
            raise ExportError(
                f"ITEM {item_id} referencia conceitos inexistentes: {', '.join(unknown_concepts)}"
            )
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "item",
                "id": f"item:{item_id}",
                "item_id": item_id,
                "source_id": source_id,
                "concept_ids": concept_ids,
                "fields": record_fields(item),
                "graph_rag": item_graph_rag_projection(item, source_id, project_status),
                "provenance": provenance(item["path"], role="item_declaration"),
            }
        )
    return records


def relation_records(
    root: Path,
    concepts: dict[str, dict[str, str]],
    items: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    vocabulary_rows = read_csv(
        root / "ontologia" / "vocabulario-relacoes.csv",
        RELATION_VOCABULARY_COLUMNS,
    )
    vocabulary = {row["tipo_relacao"]: row for row in vocabulary_rows}
    if len(vocabulary) != len(vocabulary_rows):
        raise ExportError("Há tipos de relação duplicados no vocabulário relacional.")

    relation_rows = read_csv(
        root / "ontologia" / "relacoes-ontologicas.csv",
        RELATION_COLUMNS,
    )
    relation_type_records = [
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "relation_type",
            "id": f"relation_type:{relation_type}",
            "relation_type_id": relation_type,
            "fields": dict(sorted(row.items())),
            "provenance": provenance(
                "ontologia/vocabulario-relacoes.csv",
                role="relation_vocabulary",
            ),
        }
        for relation_type, row in sorted(vocabulary.items())
    ]

    records = []
    seen_ids: set[str] = set()
    for row in sorted(relation_rows, key=lambda value: value["relacao_id"]):
        relation_id = row["relacao_id"]
        if relation_id in seen_ids:
            raise ExportError(f"Relação complementar duplicada: {relation_id}")
        seen_ids.add(relation_id)
        source_concept_id = row["conceito_origem"]
        target_concept_id = row["conceito_destino"]
        relation_type_id = row["tipo_relacao"]
        if source_concept_id not in concepts or target_concept_id not in concepts:
            raise ExportError(f"Relação {relation_id} referencia conceito inexistente.")
        if relation_type_id not in vocabulary:
            raise ExportError(
                f"Relação {relation_id} usa tipo ausente no vocabulário: {relation_type_id}"
            )
        evidence_item_ids = split_codes(row["itens_evidencia"])
        unknown_items = sorted(set(evidence_item_ids) - set(items))
        if unknown_items:
            raise ExportError(
                f"Relação {relation_id} referencia ITEMs inexistentes: {', '.join(unknown_items)}"
            )
        records.append(
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "ontology_relation",
                "id": f"ontology_relation:{relation_id}",
                "relation_id": relation_id,
                "source_concept_id": source_concept_id,
                "target_concept_id": target_concept_id,
                "relation_type_id": relation_type_id,
                "evidence_item_ids": evidence_item_ids,
                "fields": dict(sorted(row.items())),
                "relation_type": dict(sorted(vocabulary[relation_type_id].items())),
                "provenance": provenance(
                    "ontologia/relacoes-ontologicas.csv",
                    role="complementary_relation_declaration",
                ),
            }
        )
    return relation_type_records, records


def private_layer_records(layer: PrivateEntityLayer) -> dict[str, list[dict[str, Any]]]:
    """Converte a camada contextual auxiliar em registros explícitos e não classificatórios."""
    private_provenance = {
        "canonical_role": "private_derived_entity_layer",
        "source_file": "artefatos/produtos/entidades-nomeadas/metadados-extracao-2026-07-27.json",
        "input_sha256": layer.input_sha256,
    }
    return {
        "private_layer_manifest": [
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "private_layer_manifest",
                "id": "private_layer_manifest:entidades_nomeadas_2026_07_27",
                "visibility": "private",
                "metadata": layer.metadata,
                "provenance": private_provenance,
            }
        ],
        "private_entity": [
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "private_entity",
                "id": f"private_entity:{row['entity_id']}",
                "entity_id": row["entity_id"],
                "preferred_label": row["rotulo_preferido"],
                "ner_type": row["tipo_ner"],
                "review_status": row["status_revisao"],
                "provenance": private_provenance,
            }
            for row in layer.entities
        ],
        "private_entity_alias": [
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "private_entity_alias",
                "id": f"private_entity_alias:{row['alias_id']}",
                "alias_id": row["alias_id"],
                "candidate_entity_id": row["entity_id"],
                "surface_form": row["forma_superficial"],
                "review_status": row["status_revisao"],
                "provenance": private_provenance,
            }
            for row in layer.aliases
        ],
        "private_lexical_cue": [
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "private_lexical_cue",
                "id": f"private_lexical_cue:{row['cue_id']}",
                "cue_id": row["cue_id"],
                "normalized_form": row["forma_normalizada"],
                "ner_type": row["tipo_ner"],
                "review_status": row["status_revisao"],
                "usage": "contextual_retrieval_only",
                "provenance": private_provenance,
            }
            for row in layer.lexical_cues
        ],
        "private_entity_mention": [
            {
                "schema_version": SCHEMA_VERSION,
                "record_type": "private_entity_mention",
                "id": f"private_entity_mention:{row['mention_id']}",
                "mention_id": row["mention_id"],
                "tweet_id": row["tweet_id"],
                "ner_type": row["entity_label_original"],
                "surface_form": row["entity_text"],
                "start": int(row["start"]),
                "end": int(row["end"]),
                "external_classification": row["external_classification"],
                "candidate_entity_id": row["candidate_entity_id"] or None,
                "canonical_entity_id": row["canonical_entity_id"] or None,
                "cue_id": row["cue_id"] or None,
                "provenance": private_provenance,
            }
            for row in layer.mentions
        ],
    }


def validate_records(records: list[dict[str, Any]]) -> None:
    identifiers = [str(record["id"]) for record in records]
    duplicates = sorted(identifier for identifier in set(identifiers) if identifiers.count(identifier) > 1)
    if duplicates:
        raise ExportError(f"IDs JSONL duplicados: {', '.join(duplicates)}")
    for record in records:
        missing = [key for key in ("schema_version", "record_type", "id", "provenance") if key not in record]
        if missing:
            raise ExportError(f"Registro JSONL incompleto {record.get('id', '<sem id>')}: {missing}")
        if record["schema_version"] != SCHEMA_VERSION:
            raise ExportError(f"Versão de schema inconsistente em {record['id']}")


def build_records(
    root: Path,
    *,
    include_private_entities: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    root = root.resolve()
    project = parse_project(root / "projeto.synp")
    fields, _ = parse_template(root / "template.synt")
    concepts = parse_concepts(root)
    sources, items = parse_annotation_records(root, project)
    project_status = str(project["metadata"].get("status", ""))
    relation_type_rows, relations = relation_records(root, concepts, items)

    groups = {
        "input_file": input_file_records(root, project),
        "template_field": template_field_records(fields),
        "ontology_concept": concept_records(concepts, project_status),
        "source": source_records(sources),
        "item": item_records(items, sources, concepts, project_status),
        "relation_type": relation_type_rows,
        "ontology_relation": relations,
    }
    if include_private_entities:
        groups.update(private_layer_records(load_private_entity_layer(root)))
    record_counts = {record_type: len(records) for record_type, records in groups.items()}
    record_counts["export_manifest"] = 1
    record_counts["total"] = sum(record_counts.values())
    metadata = dict(sorted(dict(project["metadata"]).items()))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "record_type": "export_manifest",
        "id": f"export_manifest:{project['name']}",
        "format": "jsonl",
        "exporter": EXPORTER_PATH,
        "project": {
            "name": project["name"],
            "metadata": metadata,
            "description": project["description"],
            "includes": project["includes"],
        },
        "private_entity_layer_included": include_private_entities,
        "graph_rag": graph_rag_profile(project_status),
        "record_counts": record_counts,
        "provenance": {
            "canonical_role": "derived_export_manifest",
            "source_file": "projeto.synp",
            "canonical_input_ids": [
                f"input_file:{relative_path}" for relative_path in canonical_input_paths(project)
            ],
        },
    }
    records = [manifest]
    for record_type in (
        "input_file",
        "template_field",
        "ontology_concept",
        "source",
        "item",
        "relation_type",
        "ontology_relation",
        "private_layer_manifest",
        "private_entity",
        "private_entity_alias",
        "private_lexical_cue",
        "private_entity_mention",
    ):
        records.extend(groups.get(record_type, []))
    validate_records(records)
    return records, record_counts


def serialize_jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exporta o projeto Synesis para JSONL detalhado e determinístico."
    )
    parser.add_argument("--root", type=Path, default=Path("."), help="Raiz do subprojeto Synesis.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Entregáveis/JSONL/ontologia-dominio-eleitoral.jsonl"),
        help="Arquivo JSONL derivado.",
    )
    parser.add_argument(
        "--include-private-entities",
        action="store_true",
        help="Inclui a camada contextual auxiliar curada de entidades nomeadas na saída derivada.",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output

    try:
        records, counts = build_records(root, include_private_entities=args.include_private_entities)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_jsonl(records), encoding="utf-8", newline="\n")
    except (ExportError, OSError, ValueError) as error:
        print(f"ERRO_JSONL_EXPORTACAO: {error}", file=sys.stderr)
        return 1

    print(
        "JSONL_EXPORTADO "
        + " ".join(
            f"{key}={value}"
            for key, value in sorted(counts.items())
        )
        + f" output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
