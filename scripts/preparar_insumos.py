#!/usr/bin/env python3
"""Prepara cópia local dos insumos legitimamente obtidos; sem rede ou inferência."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "entrada": ("entrada", "x__x_posts.csv"),
    "triagem": ("triagem", "triagem.csv"),
    "rag": ("rag", "contexto-rag.jsonl"),
}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(source, destination=ROOT):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if not source.is_dir():
        raise ValueError("Diretório de insumos não encontrado")
    dest_dir = destination / "dados" / "privados"
    copied = []
    for key, (subdir, filename) in FILES.items():
        candidate = source / subdir / filename
        if not candidate.is_file():
            candidate = source / filename
        if not candidate.is_file():
            raise ValueError("Insumo obrigatório ausente: " + filename)
        target = dest_dir / subdir / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate, target)
        copied.append({"path": target.relative_to(destination).as_posix(), "sha256": sha256(target)})
    (destination / "proveniencia.json").write_text(json.dumps(copied, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Execute somente validações locais sobre o material fornecido; nenhum texto é exibido.
    sys.path.insert(0, str(ROOT / "scripts"))
    import reclassificar
    rows, selected, packets, _ = reclassificar.load_inputs(destination)
    return {"input_records": len(rows), "selected_records": len(selected), "rag_packets": len(packets), "api_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Pasta privada com entrada/, triagem/ e rag/ ou os três arquivos na raiz")
    args = parser.parse_args()
    try:
        print(json.dumps({"preparation": "ok", **prepare(args.source)}, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(2, "Preparação interrompida: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
