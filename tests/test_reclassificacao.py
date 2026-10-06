import unittest
import importlib.util
import tempfile
import os
import json
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('runner', ROOT / 'scripts/reclassificar.py')
M = importlib.util.module_from_spec(SPEC)
if (ROOT / 'scripts/reclassificar.py').exists():
    SPEC.loader.exec_module(M)


def valid():
    return {'scope_decision':'in_scope','decision_status':'classified_provisional','concept_ids':['injuria_eleitoral'],'primary_concept_id':'injuria_eleitoral','supercategory_ids':['discurso_de_odio_eleitoral'],'claims':[{'concept_id':'injuria_eleitoral','quote':'ofensa','criterion_used':'critério','evidence_item_ids':['item1'],'justification':'justificativa'}],'excluded_candidates':[],'missing_evidence':[],'context_limitations':[],'human_review_required':True}

PACKET={'candidate_concept_ids':['injuria_eleitoral'],'evidence':{'injuria_eleitoral':[{'item_id':'item1'}]}}


class Contract(unittest.TestCase):
    def check(self,value):
        self.assertTrue(hasattr(M,'validate_decision'),'Validador da nova execução ainda não implementado')
        return M.validate_decision(value,'uma ofensa',PACKET)

    def test_valid(self):self.assertEqual(self.check(valid()),[])
    def test_contradiction(self):
        v=valid();v['scope_decision']='out_of_scope';self.assertTrue(self.check(v))
    def test_empty_classification(self):
        v=valid();v['concept_ids']=[];v['primary_concept_id']='';self.assertTrue(self.check(v))
    def test_primary_membership(self):
        v=valid();v['primary_concept_id']='outra';self.assertTrue(self.check(v))
    def test_literal_quote(self):
        v=valid();v['claims'][0]['quote']='invenção';self.assertTrue(self.check(v))
    def test_unknown_evidence(self):
        v=valid();v['claims'][0]['evidence_item_ids']=['inventado'];self.assertTrue(self.check(v))
    def test_missing_fields(self):
        v=valid();del v['missing_evidence'];self.assertTrue(self.check(v))
    def test_empty_claims(self):
        v=valid();v['claims']=[];self.assertTrue(self.check(v))
    def test_nonclassified_has_no_assignments(self):
        v=valid();v['decision_status']='no_matching_category';self.assertTrue(self.check(v))
    def test_no_matching_valid(self):
        v=valid();v.update(decision_status='no_matching_category',concept_ids=[],primary_concept_id='',claims=[]);self.assertEqual(self.check(v),[])
    def test_strict_nan(self):
        self.assertTrue(hasattr(M,'strict_json'))
        with self.assertRaises(ValueError):M.strict_json('{"x":NaN}')
    def test_non_object(self):
        self.assertTrue(hasattr(M,'strict_json'))
        with self.assertRaises(ValueError):M.strict_json('[]')
    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):M.strict_json('{"x":1,"x":2}')
    def test_missing_key(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            with patch.dict(os.environ,{},clear=True):
                with self.assertRaises(RuntimeError):M.read_credentials(Path(directory))
    def test_api_payload_and_no_provider_fallback(self):
        seen=[]
        def response(payload):
            seen.append(payload)
            return {'model':M.MODEL,'choices':[{'finish_reason':'stop','message':{'content':json.dumps(valid())}}],'usage':{'prompt_tokens':2,'completion_tokens':1,'total_tokens':3}}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            result=M.classify({'source_record_id':'test:1','text_analysis':'uma ofensa'},PACKET,'teste','fixture-key-not-real',Path(directory),requester=response)
        self.assertEqual(result['decision_status'],'classified_provisional')
        self.assertEqual(seen[0]['model'],M.MODEL)
        self.assertFalse(seen[0]['provider']['allow_fallbacks'])
        self.assertEqual(result['attempts'][0]['usage']['total_tokens'],3)
    def test_reject_other_model(self):
        def response(payload):return {'model':'outro','usage':{}}
        with tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR')) as directory:
            with patch.object(M.time,'sleep'):
                result=M.classify({'source_record_id':'test:1','text_analysis':'uma ofensa'},PACKET,'teste','fixture-key-not-real',Path(directory),requester=response)
        self.assertEqual(result['decision_status'],'parse_error')
        self.assertEqual(len(result['attempts']),3)
    def test_preflight_inputs_are_absent_from_public_copy(self):
        self.assertFalse((ROOT / "dados/privados/entrada/x__x_posts.csv").exists())
        self.assertFalse((ROOT / "dados/privados/triagem/triagem.csv").exists())
        self.assertFalse((ROOT / "dados/privados/rag/contexto-rag.jsonl").exists())

if __name__=='__main__':unittest.main()
