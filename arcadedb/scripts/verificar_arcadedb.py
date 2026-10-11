#!/usr/bin/env python3
"""Confere contagens e todos os payloads do banco contra o recorte público."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

LOCAL_ROOT = Path(__file__).resolve().parent.parent
IMPORTER = Path(__file__).resolve().parent / "importar_synesis.py"
SPEC = importlib.util.spec_from_file_location("importar_synesis", IMPORTER)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Não foi possível carregar o importador local")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def total(response: dict[str, Any]) -> int:
    rows = response.get("result")
    if not isinstance(rows, list) or len(rows) != 1 or "total" not in rows[0]:
        raise MODULE.ImportError("Resposta de contagem inesperada do ArcadeDB")
    return int(rows[0]["total"])


def count(client: Any, type_name: str) -> int:
    return total(client.command(f"SELECT count(*) AS total FROM {type_name}"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=LOCAL_ROOT / ".env")

    parser.add_argument("--url", default=MODULE.API_URL)
    parser.add_argument("--database", default=MODULE.DATABASE_NAME)
    args = parser.parse_args(argv)

    try:
        environment = MODULE.parse_env(args.env_file.resolve())
        MODULE.validate(MODULE.PUBLIC_ROOT)
        records = MODULE.load_records(MODULE.PUBLIC_ROOT / "exportacoes" / "ontologia.jsonl")
        client = MODULE.ArcadeClient(
            base_url=args.url,
            database=args.database,
            password=environment["ARCADEDB_ROOT_PASSWORD"],
        )
        client.wait_ready(30)
        expected_vertices: dict[str, int] = {}
        for record in records:
            vertex_type = MODULE.VERTEX_TYPES[str(record["record_type"])]
            expected_vertices[vertex_type] = expected_vertices.get(vertex_type, 0) + 1
        for vertex_type, expected in sorted(expected_vertices.items()):
            actual = count(client, vertex_type)
            if actual != expected:
                raise MODULE.ImportError(f"{vertex_type}: esperado {expected}, encontrado {actual}")
        for record in records:
            properties = MODULE.vertex_properties(record)
            rows = client.command(
                f"SELECT payload_json FROM {MODULE.VERTEX_TYPES[record['record_type']]} WHERE id = :id",
                {"id": record["id"]},
            ).get("result", [])
            if rows != [{"payload_json": properties["payload_json"]}]:
                raise MODULE.ImportError("Payload público ausente, duplicado ou divergente: " + record["id"])
        for record in records:
            if record["record_type"] != "ontology_concept":
                continue
            expected_properties = MODULE.vertex_properties(record)
            response = client.command(
                "SELECT FROM OntologyConcept WHERE id = :id",
                {"id": expected_properties["id"]},
            )
            projected = response.get("result")
            if not isinstance(projected, list) or len(projected) != 1:
                raise MODULE.ImportError(
                    f"Conceito projetado ausente ou duplicado: {expected_properties['id']}"
                )
            for property_name in MODULE.SEMANTIC_CONCEPT_PROPERTIES:
                if projected[0].get(property_name) != expected_properties[property_name]:
                    raise MODULE.ImportError(
                        f"{expected_properties['id']}: propriedade {property_name} divergiu"
                    )

        expected_edges = {
            "PARENT_OF": sum(1 for record in records if record.get("parent_concept_id")),
            "ITEM_FROM_SOURCE": sum(1 for record in records if record["record_type"] == "item"),
            "ITEM_CODES_CONCEPT": sum(
                len(record.get("concept_ids", [])) for record in records if record["record_type"] == "item"
            ),
            "RELATION_ORIGIN": sum(1 for record in records if record["record_type"] == "ontology_relation"),
            "RELATION_DESTINATION": sum(1 for record in records if record["record_type"] == "ontology_relation"),
            "USES_RELATION_TYPE": sum(1 for record in records if record["record_type"] == "ontology_relation"),
            "SUPPORTED_BY_ITEM": sum(
                len(record.get("evidence_item_ids", []))
                for record in records
                if record["record_type"] == "ontology_relation"
            ),
            "APPROVED_ONTOLOGY_RELATION": sum(
                1
                for record in records
                if record["record_type"] == "ontology_relation"
                and record.get("fields", {}).get("status_revisao") == "aprovado"
            ),
        }
        project_edge_types = {
            "input_file": "PROJECT_USES_INPUT",
            "template_field": "PROJECT_DEFINES_FIELD",
            "ontology_concept": "PROJECT_DEFINES_CONCEPT",
            "source": "PROJECT_REGISTERS_SOURCE",
            "item": "PROJECT_REGISTERS_ITEM",
            "relation_type": "PROJECT_HAS_RELATION_TYPE",
            "ontology_relation": "PROJECT_DECLARES_RELATION",
        }
        for record in records[1:]:
            edge_type = project_edge_types[str(record["record_type"])]
            expected_edges[edge_type] = expected_edges.get(edge_type, 0) + 1
        for edge_type, expected in sorted(expected_edges.items()):
            actual = count(client, edge_type)
            if actual != expected:
                raise MODULE.ImportError(f"{edge_type}: esperado {expected}, encontrado {actual}")
        expected_semantic_edges: dict[str, int] = {}
        for record in records:
            if (
                record["record_type"] == "ontology_relation"
                and record.get("fields", {}).get("status_revisao") == "aprovado"
            ):
                edge_type = MODULE.approved_relation_edge_type(str(record["relation_type_id"]))
                expected_semantic_edges[edge_type] = expected_semantic_edges.get(edge_type, 0) + 1
        for edge_type, expected in sorted(expected_semantic_edges.items()):
            actual = count(client, edge_type)
            if actual != expected:
                raise MODULE.ImportError(f"{edge_type}: esperado {expected}, encontrado {actual}")

        calunia = client.command(
            "SELECT concept_id, label FROM OntologyConcept WHERE concept_id = 'calunia_eleitoral'"
        ).get("result", [])
        if calunia != [{"concept_id": "calunia_eleitoral", "label": "Calúnia Eleitoral"}]:
            raise MODULE.ImportError("Consulta de referência para calunia_eleitoral divergiu")
    except (MODULE.ImportError, OSError, ValueError) as error:
        print(f"ERRO_VERIFICACAO_ARCADEDB: {error}", file=sys.stderr)
        return 1

    print(
        "VERIFICACAO_ARCADEDB_OK "
        f"vertices={sum(expected_vertices.values())} "
        f"edges={sum(expected_edges.values()) + sum(expected_semantic_edges.values())} "
        f"concepts={expected_vertices['OntologyConcept']} "
        f"sources={expected_vertices['Source']} "
        f"items={expected_vertices['Item']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
