#!/usr/bin/env python3
"""Exporta apenas IDs literais de CSVs locais, sem conteúdo ou autoria."""
import argparse
import csv
import json
import re
from pathlib import Path


def extract_ids(entrada, triagem):
    with Path(entrada).open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    with Path(triagem).open(encoding='utf-8', newline='') as f:
        filters = list(csv.DictReader(f))
    if len(rows) != len(filters):
        raise ValueError('Contagens divergentes')
    ids, selected = [], []
    for index, (row, filtered) in enumerate(zip(rows, filters)):
        native = row['post_id']
        if not re.fullmatch(r'[0-9]{1,20}', native):
            raise ValueError('ID inválido no índice ' + str(index))
        if native != filtered['post_id'] or int(filtered['row_index']) != index:
            raise ValueError('Identidade desalinhada no índice ' + str(index))
        ids.append(native)
        if filtered['filter_status'] == 'selected':
            selected.append(native)
    if len(ids) != len(set(ids)):
        raise ValueError('IDs duplicados; não deduplicar silenciosamente')
    return ids, selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entrada', required=True)
    parser.add_argument('--triagem', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    ids, selected = extract_ids(args.entrada, args.triagem)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    for name, values in [('post_ids_base.txt', ids), ('post_ids_selecionados.txt', selected)]:
        path = out / name
        if path.exists():
            raise FileExistsError('Saída já existe: ' + name)
        path.write_text(''.join(value + '\n' for value in values), encoding='utf-8')
    print(json.dumps({'base': len(ids), 'selecionados': len(selected), 'api_calls': 0}))


if __name__ == '__main__':
    main()
