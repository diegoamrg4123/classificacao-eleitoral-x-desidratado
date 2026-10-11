"""Contrato do importador público; sem conexões nos testes offline."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PublicDatabase(unittest.TestCase):
    def test_environment_generates_private_secret_without_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            env = Path(directory) / '.env'
            command = [sys.executable, str(ROOT / 'arcadedb/scripts/inicializar_ambiente.py'), '--env-file', str(env)]
            first = subprocess.run(command, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            initial = env.read_text()
            secret = initial.splitlines()[0].split('=', 1)[1]
            self.assertGreaterEqual(len(secret), 32)
            self.assertNotIn(secret, first.stdout + first.stderr)
            self.assertEqual(os.stat(env).st_mode & 0o777, 0o600)
            second = subprocess.run(command, text=True, capture_output=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(env.read_text(), initial)

    def test_importer_is_bound_to_public_snapshot(self):
        path = ROOT / 'arcadedb/scripts/importar_synesis.py'
        self.assertTrue(path.is_file(), 'Importador público ainda ausente')
        spec = importlib.util.spec_from_file_location('public_importer', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.DATABASE_NAME, 'synesis_eleitoral_publica')
        self.assertEqual(module.API_URL, 'http://127.0.0.1:2481')
        self.assertEqual(module.PUBLIC_ROOT, ROOT / 'ontologia-publica')
        records = module.load_records(module.PUBLIC_ROOT / 'exportacoes/ontologia.jsonl')
        self.assertEqual(len(records), 161)
        self.assertEqual(len({r['id'] for r in records}), len(records))


if __name__ == '__main__':
    unittest.main()
