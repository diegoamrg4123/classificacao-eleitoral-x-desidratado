"""Verificações offline do recorte público, sem acessar a origem restrita."""
import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'ontologia-publica'


class PublicOntology(unittest.TestCase):
    def test_changed_input_is_rejected(self):
        spec = importlib.util.spec_from_file_location('public_validation', ROOT / 'validar_publico.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'recorte'
            shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__'))
            path = target / 'itens/evidencias-publicas.syn'
            path.write_text(path.read_text() + '\nITEM @fonte_nao_autorizada\n    contexto: fixture sintética privada\nEND ITEM\n')
            with self.assertRaisesRegex(ValueError, 'Entrada modificada'):
                module.validate(target)

    def test_changed_export_is_rejected(self):
        spec = importlib.util.spec_from_file_location('public_validation', ROOT / 'validar_publico.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'recorte'
            shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__'))
            path = target / 'exportacoes/ontologia.jsonl'
            path.write_text(path.read_text() + '{"record_type":"private_entity"}\n')
            with self.assertRaisesRegex(ValueError, 'Exportação desatualizada'):
                module.validate(target)

    def test_private_layer_cannot_be_exported(self):
        for name in ('exportar_ontologia_jsonl.py', 'exportar_ontologia_owl_rdf.py'):
            with tempfile.TemporaryDirectory() as directory:
                command = [sys.executable, str(ROOT / 'ferramentas' / name), '--root', str(ROOT), '--include-private-entities']
                if 'jsonl' in name:
                    command += ['--output', str(Path(directory) / 'forbidden.jsonl')]
                else:
                    command += ['--owl-output', str(Path(directory) / 'forbidden.owl')]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Camada contextual privada indisponível', result.stdout + result.stderr)
                self.assertFalse(list(Path(directory).iterdir()))

    def test_public_project_is_self_contained_and_exports_consistently(self):
        self.assertTrue((ROOT / 'projeto.synp').is_file(), 'Projeto público ainda ausente')
        result = subprocess.run([sys.executable, str(ROOT / 'validar_publico.py')],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [json.loads(line) for line in (ROOT / 'exportacoes/ontologia.jsonl').read_text().splitlines()]
        self.assertFalse(rows[0]['private_entity_layer_included'])
        self.assertTrue(rows[0]['graph_rag']['human_review_required'])
        scope = json.loads((ROOT / 'escopo-publico.json').read_text())
        self.assertEqual({r['source_id'] for r in rows if r['record_type'] == 'source'}, set(scope['source_ids']))
        self.assertEqual({r['item_id'] for r in rows if r['record_type'] == 'item'}, set(scope['item_ids']))
        self.assertEqual(sum(r['record_type'] == 'ontology_concept' for r in rows), scope['concept_count'])


if __name__ == '__main__':
    unittest.main()
