"""Dependency-light checks for modality heuristics and preview alignment."""
import importlib.util
import pathlib
import unittest
import ast

BASE=pathlib.Path(__file__).resolve().parents[1]/'app'
spec=importlib.util.spec_from_file_location('local_modality',BASE/'modality.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ModalityTests(unittest.TestCase):
 def test_expression_matrix_and_sample_headers(self):
  profile={'tables':[{'name':'GEO_matrix','role':'tabular','fields':[{'name':'gene_id'},{'name':'GSM1234'},{'name':'GSM5678'}]}]}
  result=mod.modality_summary(profile,'GSE000_matrix.tsv')
  self.assertIn('expression',result['categories'])
  self.assertTrue(result['tables'][0]['expression_matrix_candidate'])
  self.assertEqual(len(result['tables'][0]['sample_column_candidates']),2)
 def test_clinical_and_identifiers(self):
  p={'tables':[{'name':'clinical','role':'clinical','fields':[{'name':'patient_id'},{'name':'diagnosis'},{'name':'age_at_diagnosis'},{'name':'vital_status'}]}]}
  v=mod.modality_summary(p,'patients.csv')
  self.assertIn('clinical',v['categories']);self.assertIn('identifiers',v['categories'])
 def test_imaging_metadata_not_pixels(self):
  p={'tables':[{'name':'radiology_file','role':'file metadata','fields':[{'name':'modality'},{'name':'series_instance_uid'},{'name':'pixel_spacing'}]}]}
  v=mod.modality_summary(p,'series.tsv')
  self.assertIn('imaging_metadata',v['categories']);self.assertNotIn('imaging_file',v['categories'])
 def test_raw_dicom_not_decoded(self):
  v=mod.modality_summary(None,'scan.dcm')
  self.assertIn('imaging_file',v['categories'])
  self.assertEqual(v['classification'],'file_extension_only')
 def test_no_filename_based_expression_claim(self):
  v=mod.modality_summary(None,'expression.csv')
  self.assertNotIn('expression',v['categories'])
 def test_preview_missingness_unsampled_columns(self):
  # Extract pure helper without importing the DB module to test even offline.
  tree=ast.parse((BASE/'analytics.py').read_text())
  func=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='fields')
  ns={}
  exec(compile(ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[])),'fields','exec'),ns)
  p={'tables':[{'name':'x','fields':[{'name':'a'},{'name':'b'},{'name':'c'}],
                'preview':[['a','b'],['5',''],['7','1']]}]}
  vals=ns['fields'](p)
  self.assertEqual(vals['x.b']['sample_missing_pct'],50.0)
  self.assertIsNone(vals['x.c']['sample_missing_pct'])
  self.assertEqual(vals['x.c']['sample_status'],'not_sampled')

if __name__=='__main__':unittest.main()
