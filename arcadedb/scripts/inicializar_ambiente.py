#!/usr/bin/env python3
"""Cria credencial local nova sem mostrar a senha nem substituir arquivo existente."""
import argparse
import os
from pathlib import Path
import secrets
import sys


def initialize(path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write('ARCADEDB_ROOT_PASSWORD=' + secrets.token_hex(24) + '\nARCADEDB_HTTP_PORT=2481\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env')
    args = parser.parse_args()
    try:
        initialize(args.env_file)
    except FileExistsError:
        print('Ambiente já existe; arquivo preservado. Não gere outra senha para um volume já inicializado.', file=sys.stderr)
        raise SystemExit(1)
    except OSError:
        print('Não foi possível criar o ambiente local.', file=sys.stderr)
        raise SystemExit(1)
    print('Ambiente criado com permissão 0600; credencial não exibida.')
