import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ids', ROOT / 'scripts/exportar_ids.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class PublicIds(unittest.TestCase):
    def test_real_lists(self):
        base = (ROOT / 'dados/desidratados/post_ids_base.txt').read_text().splitlines()
        selected = (ROOT / 'dados/desidratados/post_ids_selecionados.txt').read_text().splitlines()
        self.assertEqual(len(base), 1461)
        self.assertEqual(len(set(base)), 1461)
        self.assertEqual(len(selected), 223)
        self.assertTrue(set(selected).issubset(base))
        self.assertTrue(all(x.isascii() and x.isdigit() for x in base))

    def test_literal_and_invalid(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / 'a.csv', Path(tmp) / 'b.csv'
            a.write_text('post_id\n000123\n')
            b.write_text('post_id,row_index,filter_status\n000123,0,selected\n')
            self.assertEqual(m.extract_ids(a, b), (['000123'], ['000123']))
            a.write_text('post_id\n1e10\n')
            with self.assertRaises(ValueError):
                m.extract_ids(a, b)


if __name__ == '__main__':
    unittest.main()
