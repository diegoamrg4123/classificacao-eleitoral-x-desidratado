#!/usr/bin/env python3
"""Importa exclusivamente o snapshot auditado do recorte público no ArcadeDB.

Não acessa a ontologia privada, o corpus nem o banco de trabalho.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DATABASE_NAME = "synesis_eleitoral_publica"
API_URL = "http://127.0.0.1:2481"
PUBLIC_ROOT = Path(__file__).resolve().parents[2] / "ontologia-publica"
sys.path.insert(0, str(PUBLIC_ROOT))
from validar_publico import validate
VERTEX_TYPES = {
    "export_manifest": "SynesisProject",
    "input_file": "CanonicalInput",
    "template_field": "TemplateField",
    "ontology_concept": "OntologyConcept",
    "source": "Source",
    "item": "Item",
    "relation_type": "RelationType",
    "ontology_relation": "OntologyRelation",
}
SEMANTIC_CONCEPT_PROPERTIES = (
    "concept_id",
    "parent_concept_id",
    "hierarchy_path_json",
    "concept_type",
    "hierarchy_role",
    "preferred_label",
    "graph_rag_role",
    "operational_definition",
    "inclusion_criterion",
    "exclusion_criterion",
    "operational_question",
    "observable_signals_json",
    "classification_guidance",
    "classification_human_review_required",
    "structural_context_only",
)
EDGE_TYPES = (
    "PROJECT_USES_INPUT",
    "PROJECT_DEFINES_FIELD",
    "PROJECT_DEFINES_CONCEPT",
    "PROJECT_REGISTERS_SOURCE",
    "PROJECT_REGISTERS_ITEM",
    "PROJECT_HAS_RELATION_TYPE",
    "PROJECT_DECLARES_RELATION",
    "PARENT_OF",
    "ITEM_FROM_SOURCE",
    "ITEM_CODES_CONCEPT",
    "RELATION_ORIGIN",
    "RELATION_DESTINATION",
    "USES_RELATION_TYPE",
    "SUPPORTED_BY_ITEM",
    "APPROVED_ONTOLOGY_RELATION",
)


class ImportError(RuntimeError):
    """Falha controlada de materialização no ArcadeDB."""


def parse_env(path: Path) -> dict[str, str]:
    """Lê KEY=VALUE simples sem imprimir credenciais."""
    if not path.is_file():
        raise ImportError(f"Arquivo de ambiente ausente: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ImportError(f"Linha inválida em {path.name}")
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    password = values.get("ARCADEDB_ROOT_PASSWORD", "")
    if not password or password == "substitua_por_uma_senha_forte":
        raise ImportError("ARCADEDB_ROOT_PASSWORD não foi configurada em .env")
    return values


def load_records(snapshot: Path) -> list[dict[str, Any]]:
    if not snapshot.is_file():
        raise ImportError(f"Snapshot JSONL não encontrado: {snapshot}")
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(snapshot.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ImportError(f"JSON inválido no snapshot, linha {line_number}: {error.msg}") from error
        if record.get("record_type") not in VERTEX_TYPES:
            raise ImportError(f"Tipo de registro não suportado no snapshot: {record.get('record_type')}")
        if not record.get("id"):
            raise ImportError(f"Registro sem id no snapshot, linha {line_number}")
        records.append(record)
    if not records or records[0].get("record_type") != "export_manifest":
        raise ImportError("O primeiro registro precisa ser o manifest da exportação Synesis")
    return records


class ArcadeClient:
    def __init__(self, *, base_url: str, database: str, password: str) -> None:
        self.endpoint = f"{base_url.rstrip('/')}/api/v1/command/{database}"
        token = base64.b64encode(f"root:{password}".encode("utf-8")).decode("ascii")
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def command(self, statement: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = json.dumps(
            {"language": "sql", "command": statement, "params": params or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(self.endpoint, data=payload, headers=self.headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:500]
            raise ImportError(f"ArcadeDB recusou o comando SQL ({error.code}): {detail}") from error
        except urllib.error.URLError as error:
            raise ImportError(f"Não foi possível conectar ao ArcadeDB: {error.reason}") from error

    def wait_ready(self, timeout_seconds: int) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                self.command("SELECT 1 AS ready")
                return
            except ImportError as error:
                last_error = error
                time.sleep(2)
        raise ImportError(f"ArcadeDB não ficou pronto em {timeout_seconds}s: {last_error}")


def scalar(value: Any) -> str:
    """Converte campos de navegação sem perder o payload JSON completo."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def approved_relation_edge_type(relation_type_id: str) -> str:
    """Converte um ID controlado em tipo de aresta ArcadeDB seguro."""
    if not re.fullmatch(r"[a-z][a-z0-9_]*", relation_type_id):
        raise ImportError(f"ID de tipo relacional inseguro: {relation_type_id}")
    return relation_type_id.upper()


def vertex_properties(record: dict[str, Any]) -> dict[str, str]:
    fields = record.get("fields", {})
    project = record.get("project", {})
    graph_rag = record.get("graph_rag", {})
    label = record["id"]
    properties: dict[str, str] = {
        "id": str(record["id"]),
        "record_type": str(record["record_type"]),
        "label": label,
        "payload_json": json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    }
    if record["record_type"] == "export_manifest":
        properties.update(
            {
                "project_name": scalar(project.get("name")),
                "project_status": scalar(project.get("metadata", {}).get("status")),
                "project_version": scalar(project.get("metadata", {}).get("version")),
                "label": scalar(project.get("name")) or label,
            }
        )
    elif record["record_type"] == "input_file":
        properties.update(
            {
                "relative_path": scalar(record.get("relative_path")),
                "sha256": scalar(record.get("sha256")),
                "label": scalar(record.get("relative_path")) or label,
            }
        )
    elif record["record_type"] == "template_field":
        properties.update(
            {
                "field_id": scalar(record.get("field_id")),
                "field_type": scalar(record.get("field_type")),
                "scope": scalar(record.get("scope")),
                "label": scalar(record.get("field_id")) or label,
            }
        )
    elif record["record_type"] == "ontology_concept":
        properties.update(
            {
                "concept_id": scalar(record.get("concept_id")),
                "parent_concept_id": scalar(record.get("parent_concept_id")),
                "hierarchy_path_json": scalar(record.get("hierarchy_path", [])),
                "concept_type": scalar(fields.get("tipo_conceito")),
                "hierarchy_role": scalar(fields.get("papel_hierarquico")),
                "preferred_label": scalar(fields.get("rotulo_preferido")),
                "label": scalar(fields.get("rotulo_preferido") or record.get("concept_id")) or label,
                "graph_rag_role": scalar(graph_rag.get("classification_role")),
                "operational_definition": scalar(fields.get("definicao_operacional")),
                "inclusion_criterion": scalar(fields.get("criterio_inclusao")),
                "exclusion_criterion": scalar(fields.get("criterio_exclusao")),
                "operational_question": scalar(fields.get("pergunta_operacional")),
                "observable_signals_json": scalar(graph_rag.get("observable_signals", [])),
                "classification_guidance": scalar(graph_rag.get("classification_guidance")),
                "classification_human_review_required": json.dumps(
                    graph_rag.get("human_review_required"), ensure_ascii=False
                ),
                "structural_context_only": json.dumps(
                    graph_rag.get("structural_context_only"), ensure_ascii=False
                ),
            }
        )
    elif record["record_type"] == "source":
        properties.update(
            {
                "source_id": scalar(record.get("source_id")),
                "source_type": scalar(fields.get("tipo_fonte")),
                "description": scalar(fields.get("descricao_fonte")),
                "label": scalar(record.get("source_id")) or label,
            }
        )
    elif record["record_type"] == "item":
        properties.update(
            {
                "item_id": scalar(record.get("item_id")),
                "source_id": scalar(record.get("source_id")),
                "item_function": scalar(fields.get("funcao_item")),
                "review_status": scalar(fields.get("status_revisao")),
                "classification_status": scalar(fields.get("status_enquadramento")),
                "label": scalar(record.get("item_id")) or label,
            }
        )
    elif record["record_type"] == "relation_type":
        properties.update(
            {
                "relation_type_id": scalar(record.get("relation_type_id")),
                "review_status": scalar(fields.get("status_revisao")),
                "label": scalar(fields.get("rotulo_preferido") or record.get("relation_type_id")) or label,
            }
        )
    elif record["record_type"] == "ontology_relation":
        properties.update(
            {
                "relation_id": scalar(record.get("relation_id")),
                "relation_type_id": scalar(record.get("relation_type_id")),
                "review_status": scalar(fields.get("status_revisao")),
                "label": scalar(record.get("relation_id")) or label,
            }
        )
    return properties


def create_schema(client: ArcadeClient, records: list[dict[str, Any]]) -> None:
    for vertex_type in sorted(set(VERTEX_TYPES.values())):
        client.command(f"CREATE VERTEX TYPE {vertex_type} IF NOT EXISTS")
        client.command(f"CREATE PROPERTY {vertex_type}.id IF NOT EXISTS STRING")
        client.command(f"CREATE INDEX IF NOT EXISTS ON {vertex_type} (id) UNIQUE")
    for edge_type in EDGE_TYPES:
        client.command(f"CREATE EDGE TYPE {edge_type} IF NOT EXISTS")
    for record in records:
        if (
            record["record_type"] == "ontology_relation"
            and record.get("fields", {}).get("status_revisao") == "aprovado"
        ):
            client.command(
                f"CREATE EDGE TYPE {approved_relation_edge_type(str(record['relation_type_id']))} IF NOT EXISTS"
            )


def upsert_vertex(client: ArcadeClient, vertex_type: str, properties: dict[str, str]) -> None:
    assignments = ", ".join(f"{key} = :{key}" for key in properties)
    client.command(
        f"UPDATE {vertex_type} SET {assignments} UPSERT WHERE id = :id",
        properties,
    )


def create_edge(
    client: ArcadeClient,
    *,
    edge_type: str,
    from_type: str,
    from_id: str,
    to_type: str,
    to_id: str,
    edge_key: str,
) -> None:
    client.command(
        f"CREATE EDGE {edge_type} FROM (SELECT FROM {from_type} WHERE id = :from_id) "
        f"TO (SELECT FROM {to_type} WHERE id = :to_id) IF NOT EXISTS SET edge_key = :edge_key",
        {"from_id": from_id, "to_id": to_id, "edge_key": edge_key},
    )


def add_edges(client: ArcadeClient, records: list[dict[str, Any]]) -> int:
    by_id = {str(record["id"]): record for record in records}
    manifest = records[0]
    project_id = str(manifest["id"])
    edge_count = 0

    def edge(edge_type: str, from_record: dict[str, Any], to_record: dict[str, Any], suffix: str) -> None:
        nonlocal edge_count
        create_edge(
            client,
            edge_type=edge_type,
            from_type=VERTEX_TYPES[str(from_record["record_type"])],
            from_id=str(from_record["id"]),
            to_type=VERTEX_TYPES[str(to_record["record_type"])],
            to_id=str(to_record["id"]),
            edge_key=f"{edge_type}:{suffix}",
        )
        edge_count += 1

    for record in records[1:]:
        record_type = str(record["record_type"])
        project_edge_type = {
            "input_file": "PROJECT_USES_INPUT",
            "template_field": "PROJECT_DEFINES_FIELD",
            "ontology_concept": "PROJECT_DEFINES_CONCEPT",
            "source": "PROJECT_REGISTERS_SOURCE",
            "item": "PROJECT_REGISTERS_ITEM",
            "relation_type": "PROJECT_HAS_RELATION_TYPE",
            "ontology_relation": "PROJECT_DECLARES_RELATION",
        }[record_type]
        edge(project_edge_type, manifest, record, str(record["id"]))

    for record in records:
        if record["record_type"] == "ontology_concept" and record.get("parent_concept_id"):
            parent_id = f"ontology_concept:{record['parent_concept_id']}"
            parent = by_id.get(parent_id)
            if parent is None:
                raise ImportError(f"Pai ausente no snapshot: {parent_id}")
            edge("PARENT_OF", parent, record, str(record["id"]))
        elif record["record_type"] == "item":
            source = by_id.get(f"source:{record['source_id']}")
            if source is None:
                raise ImportError(f"SOURCE ausente no snapshot: {record['source_id']}")
            edge("ITEM_FROM_SOURCE", record, source, str(record["id"]))
            for concept_id in record.get("concept_ids", []):
                concept = by_id.get(f"ontology_concept:{concept_id}")
                if concept is None:
                    raise ImportError(f"Conceito ausente no snapshot: {concept_id}")
                edge("ITEM_CODES_CONCEPT", record, concept, f"{record['id']}:{concept_id}")
        elif record["record_type"] == "ontology_relation":
            origin = by_id.get(f"ontology_concept:{record['source_concept_id']}")
            target = by_id.get(f"ontology_concept:{record['target_concept_id']}")
            relation_type = by_id.get(f"relation_type:{record['relation_type_id']}")
            if not all((origin, target, relation_type)):
                raise ImportError(f"Referência ausente na relação: {record['relation_id']}")
            edge("RELATION_ORIGIN", record, origin, str(record["id"]))
            edge("RELATION_DESTINATION", record, target, str(record["id"]))
            edge("USES_RELATION_TYPE", record, relation_type, str(record["id"]))
            for item_id in record.get("evidence_item_ids", []):
                item = by_id.get(f"item:{item_id}")
                if item is None:
                    raise ImportError(f"ITEM de evidência ausente no snapshot: {item_id}")
                edge("SUPPORTED_BY_ITEM", record, item, f"{record['id']}:{item_id}")
            if record.get("fields", {}).get("status_revisao") == "aprovado":
                edge("APPROVED_ONTOLOGY_RELATION", origin, target, str(record["relation_id"]))
                edge(
                    approved_relation_edge_type(str(record["relation_type_id"])),
                    origin,
                    target,
                    str(record["relation_id"]),
                )
    return edge_count


def main(argv: list[str] | None = None) -> int:
    local_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=local_root / ".env")
    parser.add_argument("--url", default=API_URL)
    parser.add_argument("--database", default=DATABASE_NAME)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)

    try:
        validate(PUBLIC_ROOT)
        snapshot = PUBLIC_ROOT / "exportacoes" / "ontologia.jsonl"
        environment = parse_env(args.env_file.resolve())
        records = load_records(snapshot)
        client = ArcadeClient(base_url=args.url, database=args.database, password=environment["ARCADEDB_ROOT_PASSWORD"])
        client.wait_ready(args.timeout)
        create_schema(client, records)
        for record in records:
            upsert_vertex(client, VERTEX_TYPES[str(record["record_type"])], vertex_properties(record))
        edge_count = add_edges(client, records)
        digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    except (ImportError, OSError, ValueError) as error:
        print(f"ERRO_IMPORTACAO_ARCADEDB: {error}", file=sys.stderr)
        return 1

    counts: dict[str, int] = {}
    for record in records:
        counts[str(record["record_type"])] = counts.get(str(record["record_type"]), 0) + 1
    formatted_counts = " ".join(f"{key}={value}" for key, value in sorted(counts.items()))
    print(f"IMPORTACAO_ARCADEDB_OK registros={len(records)} arestas_processadas={edge_count} sha256_snapshot={digest}")
    print(f"CONTAGENS {formatted_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
