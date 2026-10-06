import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preparar_insumos.py"
SPEC = importlib.util.spec_from_file_location("preparar_insumos", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class PreparationPrivacy(unittest.TestCase):
    def test_hash_of_synthetic_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.csv"
            path.write_text("id,text\n001,synthetic\n", encoding="utf-8")
            self.assertEqual(len(M.sha256(path)), 64)

    def test_missing_sources_fail_without_touching_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "authorized"; source.mkdir()
            destination = Path(tmp) / "destination"; destination.mkdir()
            with self.assertRaises(ValueError):
                M.prepare(source, destination)
            self.assertFalse((destination / "dados").exists())
            self.assertFalse((destination / "proveniencia.json").exists())

    def test_synthetic_preparation_preserves_native_id_and_aligns(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); source = base / "source"; dest = base / "dest"
            for name in ("entrada", "triagem", "rag"):
                (source / name).mkdir(parents=True)
            dest.mkdir()
            text = "texto sintético reservado para teste"
            native_id = "000012345678901234"
            digest = hashlib.sha256(text.encode()).hexdigest()
            version = "x:post:" + native_id + ":" + digest[:16]
            with (source / "entrada" / "x__x_posts.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["id", "post_id", "texto_principal"]); w.writeheader()
                w.writerow({"id":"0007", "post_id":native_id, "texto_principal":text})
            fields = ["row_index", "source_record_id", "post_id", "text_sha256", "content_version_id", "filter_status"]
            with (source / "triagem" / "triagem.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
                w.writerow({"row_index":"0", "source_record_id":"x__x_posts:0007", "post_id":native_id,
                            "text_sha256":digest, "content_version_id":version, "filter_status":"selected"})
            packet = {"content_version_id":version, "candidate_concept_ids":[], "evidence":{}}
            (source / "rag" / "contexto-rag.jsonl").write_text(json.dumps(packet) + "\n", encoding="utf-8")
            counts = M.prepare(source, dest)
            self.assertEqual(counts, {"input_records":1, "selected_records":1, "rag_packets":1, "api_calls":0})
            rows, selected, _, _ = __import__("sys").modules["reclassificar"].load_inputs(dest)
            self.assertEqual(rows[0]["post_id"], native_id)
            self.assertEqual(rows[0]["source_record_id"], "x__x_posts:0007")

    def test_file_allowlist_is_narrow(self):
        self.assertEqual(set(M.FILES), {"entrada", "triagem", "rag"})
        self.assertEqual({filename for _, filename in M.FILES.values()},
                         {"x__x_posts.csv", "triagem.csv", "contexto-rag.jsonl"})


if __name__ == "__main__":
    unittest.main()
