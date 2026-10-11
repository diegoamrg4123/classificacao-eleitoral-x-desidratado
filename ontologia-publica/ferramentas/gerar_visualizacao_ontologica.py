#!/usr/bin/env python3
"""Gera uma visualização HTML derivada da ontologia e de suas relações aprovadas.

A saída é uma projeção local e reproduzível. Ela lê diretamente os arquivos
canônicos do projeto, sem depender do modelo de arestas do Synesis Graph e sem
alterar template, ontologia, SOURCEs, ITEMs ou relações.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


BLOCK_RE = re.compile(r"(?ms)^\s*(ONTOLOGY|SOURCE|ITEM)\s+([^\n]+)\n(.*?)^\s*END\s+\1\s*$")
FIELD_RE = re.compile(r"^\s+([a-z_][a-z0-9_]*):\s*(.*)$")
PROJECT_RE = re.compile(r"(?m)^PROJECT\s+([^\s]+)")

ONTOLOGY_FIELDS = {
    "tipo_conceito": "Tipo de conceito",
    "papel_hierarquico": "Papel hierárquico",
    "definicao_operacional": "Definição operacional",
    "criterio_inclusao": "Critério de inclusão",
    "criterio_exclusao": "Critério de exclusão",
    "rotulo_preferido": "Rótulo preferido",
    "sinonimos": "Sinônimos",
    "pergunta_operacional": "Pergunta operacional",
    "alvo_tipico": "Alvo típico",
    "mecanismo_de_dano": "Mecanismo de dano",
    "sinais_observaveis": "Sinais observáveis",
    "ordem_escala": "Ordem na escala",
    "notas": "Notas",
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

VOCABULARY_COLUMNS = {
    "tipo_relacao",
    "rotulo_preferido",
    "direcao",
    "definicao",
    "status_revisao",
    "condicoes_uso",
    "condicoes_nao_uso",
}


class VisualizationError(ValueError):
    """Erro de integridade que impede gerar uma projeção confiável."""


def parse_blocks(path: Path, expected_kind: str | None = None) -> list[dict[str, str]]:
    """Lê blocos Synesis simples, preservando a ordem de seus campos."""
    if not path.is_file():
        raise VisualizationError(f"Arquivo Synesis não encontrado: {path}")

    blocks: list[dict[str, str]] = []
    text = path.read_text(encoding="utf-8")
    for kind, name, body in BLOCK_RE.findall(text):
        if expected_kind and kind != expected_kind:
            continue
        block = {
            "kind": kind,
            "id": name.strip().lstrip("@"),
            "path": path.as_posix(),
        }
        for line in body.splitlines():
            match = FIELD_RE.match(line)
            if match:
                block[match.group(1)] = match.group(2).strip()
        blocks.append(block)
    return blocks


def read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    """Lê um CSV e garante o contrato mínimo usado pelo renderizador."""
    if not path.is_file():
        raise VisualizationError(f"CSV não encontrado: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        missing = sorted(required_columns - fields)
        if missing:
            raise VisualizationError(
                f"CSV {path} não contém as colunas obrigatórias: {', '.join(missing)}"
            )
        return [
            {key: (value or "").strip() for key, value in row.items() if key is not None}
            for row in reader
        ]


def read_project_metadata(path: Path) -> dict[str, str]:
    """Extrai nome e metadados leves do manifesto sem interpretar a DSL inteira."""
    if not path.is_file():
        raise VisualizationError(f"Manifesto não encontrado: {path}")
    text = path.read_text(encoding="utf-8")
    project_match = PROJECT_RE.search(text)
    metadata: dict[str, str] = {"name": project_match.group(1) if project_match else path.parent.name}
    in_metadata = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "METADATA":
            in_metadata = True
            continue
        if stripped == "END METADATA":
            in_metadata = False
            continue
        if in_metadata and ":" in stripped:
            key, value = stripped.split(":", 1)
            metadata[key.strip()] = value.strip()
    return metadata


def load_concepts(root: Path) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[str]]:
    """Carrega conceitos e deriva a árvore somente de `conceito_pai`."""
    path = root / "ontologia" / "dominio-eleitoral.syno"
    records = parse_blocks(path, "ONTOLOGY")
    concepts: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    for record in records:
        concept_id = record["id"]
        if not concept_id:
            raise VisualizationError(f"Conceito sem ID em {path}")
        if concept_id in by_id:
            raise VisualizationError(f"ID de conceito duplicado: {concept_id}")
        fields = {
            key: value
            for key, value in record.items()
            if key not in {"kind", "id", "path"} and value
        }
        concept = {
            "id": concept_id,
            "label": fields.get("rotulo_preferido", concept_id),
            "parent_id": fields.get("conceito_pai", ""),
            "fields": fields,
        }
        concepts.append(concept)
        by_id[concept_id] = concept

    if not concepts:
        raise VisualizationError(f"Nenhum bloco ONTOLOGY foi encontrado em {path}")

    children: dict[str, list[str]] = {concept["id"]: [] for concept in concepts}
    roots: list[str] = []
    for concept in concepts:
        parent_id = concept["parent_id"]
        if parent_id:
            if parent_id not in by_id:
                raise VisualizationError(
                    f"Conceito {concept['id']} referencia pai inexistente: {parent_id}"
                )
            children[parent_id].append(concept["id"])
        else:
            roots.append(concept["id"])

    if not roots:
        raise VisualizationError("A ontologia não possui conceito raiz.")

    state: dict[str, int] = {}

    def visit(concept_id: str) -> None:
        state[concept_id] = 1
        parent_id = by_id[concept_id]["parent_id"]
        if parent_id:
            parent_state = state.get(parent_id, 0)
            if parent_state == 1:
                raise VisualizationError(f"Ciclo detectado na hierarquia envolvendo: {concept_id}")
            if parent_state == 0:
                visit(parent_id)
        state[concept_id] = 2

    for concept in concepts:
        if state.get(concept["id"], 0) == 0:
            visit(concept["id"])

    return concepts, children, roots


def load_evidence(root: Path) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Lê SOURCEs e ITEMs apenas para exibir a trilha declarada no CSV relacional."""
    sources: dict[str, dict[str, str]] = {}
    items: dict[str, dict[str, str]] = {}

    for path in sorted(root.rglob("*.syn")):
        for block in parse_blocks(path):
            if block["kind"] == "SOURCE":
                source_id = block["id"]
                if source_id in sources:
                    raise VisualizationError(f"SOURCE duplicado: {source_id}")
                sources[source_id] = block
            elif block["kind"] == "ITEM":
                occurrence_id = block.get("identificador_ocorrencia", "")
                if not occurrence_id:
                    continue
                if occurrence_id in items:
                    raise VisualizationError(f"ITEM com identificador duplicado: {occurrence_id}")
                items[occurrence_id] = block

    return sources, items


def load_supplementary_relations(
    root: Path, concepts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Lê relações aprovadas e mantém sua justificativa e evidências intactas."""
    concept_ids = {concept["id"] for concept in concepts}
    vocabulary_rows = read_csv(
        root / "ontologia" / "vocabulario-relacoes.csv", VOCABULARY_COLUMNS
    )
    vocabulary = {
        row["tipo_relacao"]: row for row in vocabulary_rows if row.get("tipo_relacao")
    }
    relation_rows = read_csv(
        root / "ontologia" / "relacoes-ontologicas.csv", RELATION_COLUMNS
    )
    sources, items = load_evidence(root)

    relations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in relation_rows:
        relation_id = row["relacao_id"]
        origin_id = row["conceito_origem"]
        target_id = row["conceito_destino"]
        relation_type = row["tipo_relacao"]

        if not relation_id:
            raise VisualizationError("Relação complementar sem relacao_id.")
        if relation_id in seen_ids:
            raise VisualizationError(f"relacao_id duplicado: {relation_id}")
        seen_ids.add(relation_id)
        if origin_id not in concept_ids or target_id not in concept_ids:
            raise VisualizationError(
                f"Relação {relation_id} referencia conceito inexistente: {origin_id} -> {target_id}"
            )
        if relation_type not in vocabulary:
            raise VisualizationError(
                f"Relação {relation_id} usa tipo ausente do vocabulário: {relation_type}"
            )

        evidence: list[dict[str, str]] = []
        raw_evidence_ids = [
            value.strip() for value in row["itens_evidencia"].split(";") if value.strip()
        ]
        for evidence_id in raw_evidence_ids:
            if evidence_id not in items:
                raise VisualizationError(
                    f"Relação {relation_id} referencia ITEM inexistente: {evidence_id}"
                )
            item = items[evidence_id]
            source_id = item["id"]
            if source_id not in sources:
                raise VisualizationError(
                    f"ITEM {evidence_id} referencia SOURCE inexistente: {source_id}"
                )
            source = sources[source_id]
            evidence.append(
                {
                    "id": evidence_id,
                    "content": item.get("conteudo", ""),
                    "function": item.get("funcao_item", ""),
                    "item_status": item.get("status_revisao", ""),
                    "source_id": source_id,
                    "source_label": source.get("descricao_fonte", source_id),
                    "source_url": source.get("url", ""),
                }
            )

        schema = vocabulary[relation_type]
        relations.append(
            {
                "id": relation_id,
                "source_id": origin_id,
                "target_id": target_id,
                "relation_type": relation_type,
                "relation_label": schema.get("rotulo_preferido", relation_type),
                "direction": schema.get("direcao", ""),
                "definition": schema.get("definicao", ""),
                "vocabulary_status": schema.get("status_revisao", ""),
                "status": row.get("status_revisao", ""),
                "justification": row.get("justificativa", ""),
                "conditions_of_use": schema.get("condicoes_uso", ""),
                "conditions_of_non_use": schema.get("condicoes_nao_uso", ""),
                "notes": row.get("notas", ""),
                "evidence": evidence,
            }
        )

    return relations


def position_tree(
    concepts: list[dict[str, Any]], children: dict[str, list[str]], roots: list[str]
) -> dict[str, int]:
    """Atribui posições determinísticas, preservando a ordem do arquivo `.syno`."""
    by_id = {concept["id"]: concept for concept in concepts}
    leaf_index = 0
    max_depth = 0

    def place(concept_id: str, depth: int) -> float:
        nonlocal leaf_index, max_depth
        max_depth = max(max_depth, depth)
        child_ids = children[concept_id]
        if not child_ids:
            x = 130 + leaf_index * 230
            leaf_index += 1
        else:
            child_positions = [place(child_id, depth + 1) for child_id in child_ids]
            x = sum(child_positions) / len(child_positions)
        by_id[concept_id]["position"] = {"x": round(x, 2), "y": 110 + depth * 200, "depth": depth}
        return x

    for root_id in roots:
        place(root_id, 0)
    max_x = max(concept["position"]["x"] for concept in concepts)
    return {
        "width": max(1200, int(max_x + 130)),
        "height": max(620, 250 + max_depth * 200),
        "max_depth": max_depth,
    }


def build_payload(root: Path) -> dict[str, Any]:
    """Monta o contrato completo da visualização derivada."""
    root = root.resolve()
    metadata = read_project_metadata(root / "projeto.synp")
    concepts, children, roots = load_concepts(root)
    relations = load_supplementary_relations(root, concepts)
    layout = position_tree(concepts, children, roots)
    by_id = {concept["id"]: concept for concept in concepts}

    hierarchy_edges = []
    for concept in concepts:
        parent_id = concept["parent_id"]
        if parent_id:
            hierarchy_edges.append(
                {
                    "id": f"hierarquia::{parent_id}::{concept['id']}",
                    "source_id": parent_id,
                    "target_id": concept["id"],
                    "derived_from": "conceito_pai",
                    "direction": "pai_para_filho",
                }
            )

    for concept in concepts:
        concept["children"] = children[concept["id"]]
        concept["parent_label"] = (
            by_id[concept["parent_id"]]["label"] if concept["parent_id"] else ""
        )

    return {
        "schema_version": "1.0.0",
        "project": metadata,
        "provenance": {
            "generator": "ferramentas/gerar_visualizacao_ontologica.py",
            "inputs": [
                "projeto.synp",
                "ontologia/dominio-eleitoral.syno",
                "ontologia/relacoes-ontologicas.csv",
                "ontologia/vocabulario-relacoes.csv",
                "fontes/**/*.syn",
                "itens/**/*.syn",
            ],
            "hierarchy_rule": "Cada aresta hierárquica é derivada mecanicamente do campo conceito_pai, do pai para o filho.",
            "supplementary_rule": "Relações complementares são lidas somente do CSV de relações e do vocabulário aprovado.",
        },
        "layout": layout,
        "roots": roots,
        "concept_count": len(concepts),
        "hierarchy_edge_count": len(hierarchy_edges),
        "supplementary_relation_count": len(relations),
        "nodes": concepts,
        "hierarchy_edges": hierarchy_edges,
        "supplementary_relations": relations,
    }


def render_html(payload: dict[str, Any]) -> str:
    """Entrega um arquivo HTML autônomo, sem dependências externas ou rede."""
    project = payload["project"]
    title = "Mapa ontológico derivado: " + project.get("name", "Synesis")
    payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    payload_json = payload_json.replace("</", "<\\/")

    template = r'''<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { color-scheme: light; --ink:#17212b; --muted:#65717c; --line:#d9e0e6; --panel:#ffffff; --bg:#f6f8fa; --hierarchy:#7b8794; --relation:#6d28d9; --structural:#1f4b70; --classificatory:#2f6b53; --boundary:#b65b27; }
* { box-sizing: border-box; }
html, body { height:100%; margin:0; font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }
button, input { font:inherit; }
button { cursor:pointer; }
header { display:flex; gap:18px; align-items:flex-start; justify-content:space-between; padding:16px 20px 12px; border-bottom:1px solid var(--line); background:var(--panel); }
h1 { margin:0; font-size:18px; line-height:1.25; }
.subtitle { margin:5px 0 0; color:var(--muted); font-size:13px; }
.badge { border:1px solid var(--line); border-radius:999px; padding:5px 9px; color:var(--muted); font-size:12px; white-space:nowrap; }
.app { display:grid; grid-template-columns:minmax(0, 1fr) 380px; height:calc(100vh - 83px); min-height:620px; }
.graph-area { min-width:0; position:relative; background:radial-gradient(circle at 1px 1px, #dbe3ea 1px, transparent 0); background-size:22px 22px; }
.toolbar { position:absolute; z-index:3; top:14px; left:14px; display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:8px; border:1px solid var(--line); border-radius:10px; background:rgba(255,255,255,.96); box-shadow:0 4px 18px rgba(20,30,40,.10); }
.toolbar input[type="search"] { width:220px; padding:7px 9px; border:1px solid #cbd5df; border-radius:6px; }
.toolbar label { display:flex; align-items:center; gap:4px; font-size:12px; color:#45525e; white-space:nowrap; }
.toolbar button { padding:6px 9px; border:1px solid #cbd5df; border-radius:6px; color:#273542; background:#fff; }
.toolbar button:hover { background:#eff4f7; }
#graph { display:block; width:100%; height:100%; touch-action:none; user-select:none; }
.hierarchy-edge { stroke:var(--hierarchy); stroke-width:1.8; opacity:.78; }
.relation-edge { fill:none; stroke:var(--relation); stroke-width:3.6; stroke-dasharray:9 6; opacity:.92; cursor:pointer; }
.relation-label { fill:#5b21b6; font-size:13px; font-weight:700; text-anchor:middle; paint-order:stroke; stroke:#fff; stroke-width:5px; stroke-linejoin:round; cursor:pointer; }
.node { cursor:pointer; outline:none; }
.node circle { stroke-width:2.5; transition:stroke-width .12s, filter .12s; }
.node:hover circle, .node.selected circle { stroke:#101820; stroke-width:4.5; filter:drop-shadow(0 3px 3px rgba(0,0,0,.22)); }
.node.dimmed { opacity:.16; }
.node-label { font-size:14px; font-weight:650; fill:#17212b; text-anchor:middle; pointer-events:none; paint-order:stroke; stroke:#fff; stroke-width:5px; stroke-linejoin:round; }
.legend { position:absolute; z-index:2; left:14px; bottom:14px; width:255px; padding:10px 12px; border:1px solid var(--line); border-radius:10px; background:rgba(255,255,255,.96); font-size:12px; box-shadow:0 4px 18px rgba(20,30,40,.08); }
.legend strong { display:block; margin-bottom:6px; }
.legend-row { display:flex; align-items:center; gap:7px; margin:5px 0; color:#485562; }
.swatch { width:12px; height:12px; border-radius:50%; flex:none; }
.legend-line { width:26px; border-top:2px solid var(--hierarchy); }
.legend-line.relation { border-top:3px dashed var(--relation); }
.sidebar { overflow:auto; padding:16px; border-left:1px solid var(--line); background:var(--panel); }
.sidebar h2 { margin:0 0 6px; font-size:17px; }
.sidebar h3 { margin:18px 0 7px; font-size:13px; text-transform:uppercase; letter-spacing:.04em; color:#56636e; }
.sidebar p { margin:7px 0; font-size:13px; line-height:1.46; }
.detail-note { color:var(--muted); }
.stat-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:8px; margin:14px 0; }
.stat { padding:9px; border:1px solid var(--line); border-radius:8px; background:#fbfcfd; }
.stat b { display:block; font-size:19px; color:#233445; }
.stat span { display:block; margin-top:2px; font-size:11px; color:var(--muted); }
.field-list { margin:0; }
.field-list div { padding:9px 0; border-top:1px solid #edf0f2; }
.field-list dt { font-size:11px; color:#6b7680; font-weight:750; letter-spacing:.04em; text-transform:uppercase; }
.field-list dd { margin:3px 0 0; font-size:13px; line-height:1.45; }
.pill { display:inline-block; margin:3px 4px 0 0; padding:4px 6px; border:1px solid #d8dee5; border-radius:999px; background:#f8fafb; color:#31404d; font-size:12px; }
.detail-button { display:block; width:100%; margin:6px 0; padding:8px; text-align:left; color:#273542; border:1px solid #d8dee5; border-radius:7px; background:#fff; }
.detail-button:hover { border-color:#8aa2b6; background:#f6fafc; }
.detail-button.relation { border-color:#c9b6f1; color:#5123a6; background:#fbf9ff; }
.evidence { padding:9px; margin:7px 0; border:1px solid #e3e7eb; border-radius:7px; background:#fbfcfd; }
.evidence strong { display:block; font-size:12px; }
.evidence span { display:block; margin-top:4px; color:#56636e; font-size:12px; line-height:1.4; }
.warning { padding:9px; border-left:3px solid #b65b27; background:#fff8f3; color:#6f3718; font-size:12px; line-height:1.45; }
.empty { color:var(--muted); font-size:13px; }
@media (max-width: 980px) { .app { grid-template-columns:1fr; height:auto; min-height:0; } .graph-area { height:72vh; min-height:560px; } .sidebar { border-left:0; border-top:1px solid var(--line); } header { align-items:flex-start; flex-direction:column; gap:8px; } }
</style>
</head>
<body>
<header>
  <div><h1>__TITLE__</h1><p class="subtitle">Projeção derivada dos arquivos canônicos do Synesis, sem dependências externas.</p></div>
  <div class="badge" id="project-status"></div>
</header>
<main class="app">
  <section class="graph-area" aria-label="Mapa ontológico interativo">
    <div class="toolbar">
      <input id="search" type="search" placeholder="Buscar conceito ou rótulo" aria-label="Buscar conceito ou rótulo">
      <label><input id="toggle-hierarchy" type="checkbox" checked> Hierarquia</label>
      <label><input id="toggle-relations" type="checkbox" checked> Relações</label>
      <button id="zoom-in" type="button" title="Ampliar">+</button>
      <button id="zoom-out" type="button" title="Reduzir">−</button>
      <button id="fit" type="button">Ajustar</button>
    </div>
    <svg id="graph" role="img" aria-label="Árvore de conceitos e relações complementares"></svg>
    <div class="legend">
      <strong>Legenda</strong>
      <div class="legend-row"><span class="legend-line"></span> hierarquia, derivada de <code>conceito_pai</code></div>
      <div class="legend-row"><span class="legend-line relation"></span> relação complementar aprovada</div>
      <div class="legend-row"><span class="swatch" style="background:var(--structural)"></span> estrutural</div>
      <div class="legend-row"><span class="swatch" style="background:var(--classificatory)"></span> classificatório</div>
      <div class="legend-row"><span class="swatch" style="background:var(--boundary)"></span> fronteira de exclusão</div>
    </div>
  </section>
  <aside class="sidebar" id="details" aria-live="polite"></aside>
</main>
<script>
const payload = __PAYLOAD_JSON__;
const fieldLabels = {
  tipo_conceito: "Tipo de conceito", papel_hierarquico: "Papel hierárquico",
  definicao_operacional: "Definição operacional", criterio_inclusao: "Critério de inclusão",
  criterio_exclusao: "Critério de exclusão", rotulo_preferido: "Rótulo preferido",
  sinonimos: "Sinônimos", pergunta_operacional: "Pergunta operacional",
  alvo_tipico: "Alvo típico", mecanismo_de_dano: "Mecanismo de dano",
  sinais_observaveis: "Sinais observáveis", ordem_escala: "Ordem na escala", notas: "Notas"
};
const colors = { estrutural: "#1f4b70", classificatorio: "#2f6b53", fronteira_de_exclusao: "#b65b27" };
const svgNs = "http://www.w3.org/2000/svg";
const svg = document.getElementById("graph");
const details = document.getElementById("details");
const search = document.getElementById("search");
const nodeById = new Map(payload.nodes.map(node => [node.id, node]));
const relationById = new Map(payload.supplementary_relations.map(relation => [relation.id, relation]));
let selectedNodeId = payload.roots[0] || "";
let selectedRelationId = "";
let nodeElements = new Map();
let view = { x: 0, y: 0, width: payload.layout.width, height: payload.layout.height };
let drag = null;

function esc(value) {
  return String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}
function make(tag, attrs = {}, text = "") {
  const element = document.createElementNS(svgNs, tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
  if (text) element.textContent = text;
  return element;
}
function nodeColor(node) { return colors[node.fields.tipo_conceito] || "#667085"; }
function wrapLabel(label, limit = 20) {
  const words = String(label).split(/\s+/); const lines = []; let current = "";
  for (const word of words) {
    const candidate = current ? current + " " + word : word;
    if (candidate.length > limit && current) { lines.push(current); current = word; } else current = candidate;
  }
  if (current) lines.push(current);
  return lines.slice(0, 3);
}
function setView() { svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.width} ${view.height}`); }
function fit() { view = { x: 0, y: 0, width: payload.layout.width, height: payload.layout.height }; setView(); }
function zoom(factor) {
  const cx = view.x + view.width / 2, cy = view.y + view.height / 2;
  const minWidth = 360, minHeight = 260;
  const width = Math.max(minWidth, Math.min(payload.layout.width, view.width * factor));
  const height = Math.max(minHeight, Math.min(payload.layout.height, view.height * factor));
  view = { x: Math.max(0, Math.min(payload.layout.width - width, cx - width / 2)), y: Math.max(0, Math.min(payload.layout.height - height, cy - height / 2)), width, height };
  setView();
}
function setSelectedNode(id) { selectedNodeId = id; selectedRelationId = ""; updateSelection(); renderDetails(); }
function setSelectedRelation(id) { selectedRelationId = id; selectedNodeId = ""; updateSelection(); renderDetails(); }
function updateSelection() {
  for (const [id, group] of nodeElements.entries()) group.classList.toggle("selected", id === selectedNodeId);
}
function supplementaryPath(source, target, index) {
  const sx = source.position.x, sy = source.position.y, tx = target.position.x, ty = target.position.y;
  const mx = (sx + tx) / 2, my = (sy + ty) / 2;
  const distance = Math.hypot(tx - sx, ty - sy) || 1;
  const offset = 95 + index * 28;
  const cx = mx - ((ty - sy) / distance) * offset;
  const cy = my + ((tx - sx) / distance) * offset;
  return { d: `M ${sx} ${sy} Q ${cx} ${cy} ${tx} ${ty}`, x: (sx + 2 * cx + tx) / 4, y: (sy + 2 * cy + ty) / 4 };
}
function renderGraph() {
  svg.replaceChildren(); nodeElements = new Map();
  const defs = make("defs");
  const hierarchyMarker = make("marker", { id:"arrow-hierarchy", viewBox:"0 0 10 10", refX:"8", refY:"5", markerWidth:"5", markerHeight:"5", orient:"auto-start-reverse" });
  hierarchyMarker.append(make("path", { d:"M 0 0 L 10 5 L 0 10 z", fill:"#7b8794" }));
  const relationMarker = make("marker", { id:"arrow-relation", viewBox:"0 0 10 10", refX:"8", refY:"5", markerWidth:"6", markerHeight:"6", orient:"auto-start-reverse" });
  relationMarker.append(make("path", { d:"M 0 0 L 10 5 L 0 10 z", fill:"#6d28d9" }));
  defs.append(hierarchyMarker, relationMarker); svg.append(defs);
  const edgeLayer = make("g", { "aria-label":"Arestas" });
  if (document.getElementById("toggle-hierarchy").checked) {
    for (const edge of payload.hierarchy_edges) {
      const source = nodeById.get(edge.source_id), target = nodeById.get(edge.target_id);
      edgeLayer.append(make("line", { class:"hierarchy-edge", x1:source.position.x, y1:source.position.y + 33, x2:target.position.x, y2:target.position.y - 33, "marker-end":"url(#arrow-hierarchy)" }));
    }
  }
  if (document.getElementById("toggle-relations").checked) {
    payload.supplementary_relations.forEach((relation, index) => {
      const pathData = supplementaryPath(nodeById.get(relation.source_id), nodeById.get(relation.target_id), index);
      const path = make("path", { class:"relation-edge", d:pathData.d, "marker-end":"url(#arrow-relation)", tabindex:"0", role:"button", "aria-label":relation.relation_label });
      path.addEventListener("click", () => setSelectedRelation(relation.id));
      path.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedRelation(relation.id); } });
      const label = make("text", { class:"relation-label", x:pathData.x, y:pathData.y - 7, tabindex:"0", role:"button", "aria-label":relation.relation_label }, relation.relation_label);
      label.addEventListener("click", () => setSelectedRelation(relation.id));
      label.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedRelation(relation.id); } });
      edgeLayer.append(path, label);
    });
  }
  svg.append(edgeLayer);
  const nodeLayer = make("g", { "aria-label":"Conceitos" });
  for (const node of payload.nodes) {
    const group = make("g", { class:"node", tabindex:"0", role:"button", "aria-label":node.label, transform:`translate(${node.position.x} ${node.position.y})` });
    group.append(make("title", {}, `${node.label} (${node.id})`));
    group.append(make("circle", { r:32, fill:nodeColor(node), stroke:nodeColor(node) }));
    const lines = wrapLabel(node.label);
    const label = make("text", { class:"node-label", y:48 - ((lines.length - 1) * 8) });
    lines.forEach((line, index) => label.append(make("tspan", { x:0, dy:index === 0 ? 0 : 16 }, line)));
    group.append(label);
    group.addEventListener("click", () => setSelectedNode(node.id));
    group.addEventListener("keydown", event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedNode(node.id); } });
    nodeElements.set(node.id, group); nodeLayer.append(group);
  }
  svg.append(nodeLayer); updateSearch(); updateSelection();
}
function updateSearch() {
  const term = search.value.trim().toLocaleLowerCase("pt-BR");
  for (const [id, group] of nodeElements.entries()) {
    const node = nodeById.get(id);
    const haystack = `${node.id} ${node.label} ${Object.values(node.fields).join(" ")}`.toLocaleLowerCase("pt-BR");
    group.classList.toggle("dimmed", Boolean(term) && !haystack.includes(term));
  }
}
function nodeButton(id, text) { return `<button class="detail-button" data-node="${esc(id)}">${esc(text)}</button>`; }
function relationButton(id, text) { return `<button class="detail-button relation" data-relation="${esc(id)}">${esc(text)}</button>`; }
function bindDetailActions() {
  details.querySelectorAll("[data-node]").forEach(button => button.addEventListener("click", () => setSelectedNode(button.dataset.node)));
  details.querySelectorAll("[data-relation]").forEach(button => button.addEventListener("click", () => setSelectedRelation(button.dataset.relation)));
}
function renderDetails() {
  if (selectedRelationId) { renderRelationDetails(relationById.get(selectedRelationId)); return; }
  const node = nodeById.get(selectedNodeId);
  if (!node) { renderOverview(); return; }
  const related = payload.supplementary_relations.filter(relation => relation.source_id === node.id || relation.target_id === node.id);
  const order = ["tipo_conceito", "papel_hierarquico", "definicao_operacional", "criterio_inclusao", "criterio_exclusao", "pergunta_operacional", "alvo_tipico", "mecanismo_de_dano", "sinais_observaveis", "ordem_escala", "sinonimos", "notas"];
  const fields = order.filter(key => node.fields[key]).map(key => `<div><dt>${esc(fieldLabels[key] || key)}</dt><dd>${esc(node.fields[key])}</dd></div>`).join("");
  const parent = node.parent_id ? nodeButton(node.parent_id, `Pai: ${node.parent_label} (${node.parent_id})`) : `<p class="empty">Este é um conceito raiz.</p>`;
  const children = node.children.length ? node.children.map(childId => { const child = nodeById.get(childId); return nodeButton(childId, `${child.label} (${child.id})`); }).join("") : `<p class="empty">Sem subconceitos diretos.</p>`;
  const relations = related.length ? related.map(relation => {
    const isSource = relation.source_id === node.id;
    const other = nodeById.get(isSource ? relation.target_id : relation.source_id);
    const direction = isSource ? "origem" : "destino";
    return relationButton(relation.id, `${relation.relation_label}: ${direction} em relação a ${other.label}`);
  }).join("") : `<p class="empty">Não há relação complementar registrada para este conceito.</p>`;
  details.innerHTML = `<h2>${esc(node.label)}</h2><p class="detail-note"><code>${esc(node.id)}</code></p><div class="field-list"><div><dt>Posição na árvore</dt><dd>nível ${node.position.depth + 1}</dd></div>${fields}</div><h3>Hierarquia</h3>${parent}<h3>Subconceitos diretos</h3>${children}<h3>Relações complementares</h3>${relations}`;
  bindDetailActions();
}
function renderRelationDetails(relation) {
  if (!relation) { renderOverview(); return; }
  const source = nodeById.get(relation.source_id), target = nodeById.get(relation.target_id);
  const evidence = relation.evidence.length ? relation.evidence.map(item => `<div class="evidence"><strong>${esc(item.id)} · ${esc(item.item_status || "sem status")}</strong><span>${esc(item.content)}</span><span>Fonte: ${esc(item.source_label)} (${esc(item.source_id)})</span></div>`).join("") : `<p class="empty">Nenhum ITEM de evidência foi declarado.</p>`;
  details.innerHTML = `<h2>${esc(relation.relation_label)}</h2><p class="detail-note"><code>${esc(relation.relation_type)}</code> · status da relação: <strong>${esc(relation.status || "não informado")}</strong></p>${nodeButton(source.id, `Origem: ${source.label} (${source.id})`)}${nodeButton(target.id, `Destino: ${target.label} (${target.id})`)}<div class="field-list"><div><dt>Direção declarada</dt><dd>${esc(relation.direction)}</dd></div><div><dt>Definição do vocabulário</dt><dd>${esc(relation.definition)}</dd></div><div><dt>Justificativa da aresta</dt><dd>${esc(relation.justification)}</dd></div><div><dt>Condições de uso</dt><dd>${esc(relation.conditions_of_use)}</dd></div><div><dt>Condições de não uso</dt><dd>${esc(relation.conditions_of_non_use)}</dd></div><div><dt>Notas</dt><dd>${esc(relation.notes)}</dd></div></div><h3>ITEMs de evidência</h3>${evidence}<p class="warning">Esta relação é complementar à hierarquia. Ela não transforma a origem em subclasse do destino e não substitui revisão humana.</p>`;
  bindDetailActions();
}
function renderOverview() {
  const status = payload.project.status || "não informado";
  details.innerHTML = `<h2>Mapa ontológico derivado</h2><p class="detail-note">Clique em um conceito ou em uma relação complementar para ver definição, critérios, hierarquia, justificativa e evidências.</p><div class="stat-grid"><div class="stat"><b>${payload.concept_count}</b><span>conceitos</span></div><div class="stat"><b>${payload.hierarchy_edge_count}</b><span>arestas hierárquicas</span></div><div class="stat"><b>${payload.supplementary_relation_count}</b><span>relações complementares</span></div></div><h3>Fonte de verdade</h3><p>A hierarquia vem de <code>ontologia/dominio-eleitoral.syno</code>, pelo campo <code>conceito_pai</code>. As relações não hierárquicas vêm dos CSVs de vocabulário e arestas aprovadas.</p><h3>Estado</h3><p><span class="pill">${esc(status)}</span><span class="pill">modo de validação: rascunho</span></p><p class="warning">Este mapa é um entregável derivado. Ele não cria conceitos, relações, critérios nem estados de revisão.</p>`;
}

document.getElementById("project-status").textContent = `status: ${payload.project.status || "não informado"}`;
document.getElementById("toggle-hierarchy").addEventListener("change", renderGraph);
document.getElementById("toggle-relations").addEventListener("change", renderGraph);
document.getElementById("zoom-in").addEventListener("click", () => zoom(.72));
document.getElementById("zoom-out").addEventListener("click", () => zoom(1.38));
document.getElementById("fit").addEventListener("click", fit);
search.addEventListener("input", updateSearch);
svg.addEventListener("wheel", event => { event.preventDefault(); const factor = event.deltaY < 0 ? .82 : 1.22; zoom(factor); }, { passive:false });
svg.addEventListener("pointerdown", event => { drag = { x:event.clientX, y:event.clientY, viewX:view.x, viewY:view.y }; svg.setPointerCapture(event.pointerId); });
svg.addEventListener("pointermove", event => { if (!drag) return; const bounds = svg.getBoundingClientRect(); view.x = Math.max(0, Math.min(payload.layout.width - view.width, drag.viewX - ((event.clientX - drag.x) * view.width / bounds.width))); view.y = Math.max(0, Math.min(payload.layout.height - view.height, drag.viewY - ((event.clientY - drag.y) * view.height / bounds.height))); setView(); });
svg.addEventListener("pointerup", () => { drag = null; });
renderGraph(); fit(); renderOverview();
</script>
</body>
</html>
'''
    return template.replace("__TITLE__", html.escape(title)).replace("__PAYLOAD_JSON__", payload_json)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Entregáveis/HTML/mapa-ontologico-dominio-eleitoral.html"),
    )
    args = parser.parse_args()

    root = args.root.resolve()
    payload = build_payload(root)
    output = args.output if args.output.is_absolute() else root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(payload), encoding="utf-8")

    print("Visualização ontológica derivada gerada.")
    print(f"Conceitos: {payload['concept_count']}")
    print(f"Arestas hierárquicas: {payload['hierarchy_edge_count']}")
    print(f"Relações complementares: {payload['supplementary_relation_count']}")
    print(f"HTML: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
