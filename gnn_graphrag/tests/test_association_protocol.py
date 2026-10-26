"""Offline protocol, label isolation and masking tests using pinned evidence."""

import csv
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from collections import Counter,defaultdict
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from gnn_graphrag.src import prepare_association_protocol as protocol
from gnn_graphrag.src import association_training_data as training


class AssociationProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.output=Path(cls.temp.name)/'protocol'
        cls.audit=protocol.prepare_protocol(cls.output)
        cls.splits=protocol.read_csv(cls.output/'trial_splits.csv')
        cls.partition={r['nct_id']:r['split'] for r in cls.splits}
        cls.positives=protocol.read_csv(cls.output/'positive_associations.csv')
        cls.catalog=protocol.read_jsonl(cls.output/'query_catalog.jsonl')
        cls.overlaps={r['query_id']:r for r in protocol.read_csv(cls.output/'query_overlap_audit.csv')}
        cls.inputs=training.load_training_data(cls.output,audit_only=True)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_source_output_hashes_and_provisional_readiness(self):
        manifest=protocol.validate_saved_protocol(self.output)
        self.assertEqual(manifest['status'],protocol.STATE)
        self.assertFalse(manifest['training_permitted'])
        self.assertEqual(manifest['seed'],20261023)
        self.assertEqual(manifest['target_ratios'],{'train':.7,'validation':.15,'test':.15})
        self.assertGreaterEqual(len(manifest['source_sha256']),30)

    def test_all_trials_once_including_41_without_outcomes(self):
        self.assertEqual(len(self.splits),len(self.partition))
        self.assertEqual(len(self.splits),2824)
        self.assertEqual(sum(r['has_planned_outcomes']=='False' for r in self.splits),41)
        candidates=protocol.read_csv(self.output/'candidate_trials.csv')
        self.assertEqual([r['nct_id'] for r in candidates],sorted(self.partition))
        self.assertEqual([int(r['candidate_index']) for r in candidates],list(range(2824)))

    def test_families_do_not_cross_and_original_review_is_preserved(self):
        groups=defaultdict(set)
        family={r['nct_id']:r['family_id'] for r in self.splits}
        for r in self.splits:groups[r['family_id']].add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
        actual={(r['left_nct_id'],r['right_nct_id']):r for r in protocol.read_csv(self.output/'family_pairs.csv')}
        for old in protocol.read_csv(protocol.FAMILY_RESOLUTION):
            a,b=sorted((old['left_nct_id'],old['right_nct_id']))
            self.assertEqual(actual[(a,b)]['classification'],old['classification'])
            if old['classification']!='REJECTED':self.assertEqual(family[a],family[b])
        self.assertEqual(family['NCT03497871'],family['NCT05651698'])
        self.assertEqual(actual[('NCT03497871','NCT05651698')]['classification'],'UNRESOLVED')
        self.assertEqual(self.audit['family_pair_classifications']['CONFIRMED_RELATED'],5)
        self.assertEqual(self.audit['family_pair_classifications']['REJECTED'],0)

    def test_every_original_association_and_metadata_are_preserved(self):
        self.assertEqual(len(self.positives),19740)
        self.assertEqual(len({r['outcome_id'] for r in self.positives}),19740)
        source={r['node_id']:json.loads(r['properties_json']) for r in protocol.read_csv(protocol.EXTRACTION/'nodes.csv') if r['node_label']=='PlannedOutcome'}
        for r in self.positives:
            p=source[r['outcome_id']]
            for field in ('nct_id','measure','outcome_type','time_frame','source_record_id'):
                self.assertEqual(r[field],p[field])
            self.assertEqual(r['split'],self.partition[r['nct_id']])
            self.assertEqual(r['evidence_id'],f"{r['nct_id']}|HAS_PLANNED_OUTCOME|{r['outcome_id']}")

    def test_truth_partition_is_complete_unique_and_trial_disjoint(self):
        all_records=[]
        for split in protocol.RATIOS:
            truth=protocol.read_jsonl(self.output/'truth'/(split+'.jsonl'))
            for q in truth:
                self.assertEqual(q['split'],split)
                self.assertTrue(all(self.partition[n]==split for n in q['owner_trial_ids']))
                all_records.extend(r['outcome_id'] for r in q['source_associations'])
        self.assertEqual(len(all_records),19740)
        self.assertEqual(set(all_records),{r['outcome_id'] for r in self.positives})
        self.assertEqual(len(all_records),len(set(all_records)))

    def test_query_catalog_all_known_owners_without_clinical_equivalence_merges(self):
        self.assertEqual(len(self.catalog),16290)
        self.assertEqual(sum(len(q['owner_trial_ids'])>1 for q in self.catalog),1049)
        for q in self.catalog:
            self.assertEqual(q['query_id'],protocol.key('Q-',q['query_text']))
            self.assertEqual(q['owner_trial_ids'],sorted({r['nct_id'] for r in q['source_associations']}))
            self.assertTrue(all(protocol.normalize(r['measure'])==q['query_text'] for r in q['source_associations']))
        self.assertNotEqual(protocol.normalize('All-cause mortality'),protocol.normalize('All cause mortality'))

    def test_exact_cross_partition_queries_embargoed_from_both_heldout_sets(self):
        eval_ids={split:{r['query_id'] for r in protocol.read_jsonl(self.output/'evaluation'/(split+'_queries.jsonl'))} for split in ('validation','test')}
        for q in self.catalog:
            if len({self.partition[n] for n in q['owner_trial_ids']})>1:
                self.assertIn('EXACT_QUERY_CROSS_PARTITION',json.loads(self.overlaps[q['query_id']]['exclusion_reasons']))
                self.assertTrue(all(q['query_id'] not in ids for ids in eval_ids.values()))
        self.assertFalse(eval_ids['validation'] & eval_ids['test'])

    def test_near_candidates_are_not_truth_merges_and_cross_overlap_is_embargoed(self):
        candidates=protocol.read_csv(self.output/'near_query_candidates.csv')
        self.assertGreater(len(candidates),0)
        for r in candidates:
            self.assertEqual(r['review_status'],'UNRESOLVED_EXCLUDED_IF_CROSS_PARTITION')
            self.assertNotEqual(r['left_query_id'],r['right_query_id'])
            if r['cross_partition']=='True':
                for qid in (r['left_query_id'],r['right_query_id']):
                    self.assertIn('UNRESOLVED_NEAR_QUERY_CROSS_PARTITION',json.loads(self.overlaps[qid]['exclusion_reasons']))
                    self.assertEqual(self.overlaps[qid]['eligible_for_novel_evaluation'],'False')

    def test_description_audit_is_explicitly_not_a_feature_or_equivalence_label(self):
        rows=protocol.read_csv(self.output/'duplicate_description_audit.csv')
        self.assertEqual(sum(r['kind']=='EXACT_NORMALIZED_DESCRIPTION' for r in rows),221)
        self.assertTrue(all(r['action']=='AUDIT_ONLY_NOT_A_MODEL_INPUT_OR_EQUIVALENCE_LABEL' for r in rows))
        self.assertTrue(any(len(json.loads(r['partitions']))>1 for r in rows))

    def test_all_target_edges_and_reverses_masked_no_provenance_messages(self):
        masks=protocol.read_csv(self.output/'message_edge_mask.csv')
        self.assertEqual(len(masks),100698)
        removed=[r for r in masks if r['retained']=='False']
        self.assertEqual(Counter(r['message_direction'] for r in removed),{'forward':19740,'reverse':19740})
        self.assertTrue(all(r['relationship_type']==protocol.TARGET for r in removed))
        edges=list(self.inputs.message_edges)
        self.assertEqual(len(edges),61218)
        self.assertTrue(all(r['relationship_type'] in training.CONTEXT_RELATIONSHIPS for r in edges))
        self.assertEqual(len({(r['source_node_index'],r['relationship_type'],r['target_node_index']) for r in edges}),61218)

    def test_semantic_training_inputs_exclude_linkage_and_heldout_query_metadata(self):
        self.assertEqual(len(self.inputs.context_nodes),9036)
        for q in self.inputs.queries:
            self.assertEqual(set(q),{'query_id','query_text','positive_trial_ids','ambiguous_trial_ids'})
            self.assertFalse(protocol.extraction.NCT_TOKEN.search(q['query_text']))
            self.assertEqual(q['query_text'],protocol.normalize(q['query_text']))
        for row in self.inputs.context_nodes:
            self.assertEqual(set(row),{'node_index','node_id','node_label','feature_text'})
            self.assertFalse(protocol.extraction.NCT_TOKEN.search(row['feature_text']))
            self.assertNotIn(row['node_label'],('PlannedOutcome','SourceDataset'))

    def test_training_loader_never_reads_heldout_truth_or_global_catalog(self):
        original=Path.open
        accessed=[]
        def guard(path,*args,**kwargs):
            accessed.append(path)
            # macOS /var and /private/var aliases must be compared canonically.
            self.assertTrue(path.resolve().is_relative_to((self.output/'training').resolve()),str(path))
            return original(path,*args,**kwargs)
        with patch.object(Path,'open',guard):
            bundle=training.load_training_data(self.output,audit_only=True)
        self.assertEqual(len(bundle.queries),len(self.inputs.queries))
        self.assertTrue(accessed)

    def test_provisional_protocol_blocks_training_by_default(self):
        with self.assertRaisesRegex(protocol.ProtocolError,'training is blocked'):
            training.load_training_data(self.output)
        self.assertFalse(self.inputs.training_permitted)

    def test_negative_pool_excludes_true_owners_families_and_ambiguous_candidates(self):
        allowed=set(self.inputs.candidate_ids)
        self.assertEqual(allowed,{n for n,s in self.partition.items() if s=='train'})
        for q in self.inputs.queries[:30]:
            negatives=set(training.negative_candidates(self.inputs,q['query_id']))
            self.assertFalse(negatives & set(q['positive_trial_ids']))
            self.assertFalse(negatives & set(q['ambiguous_trial_ids']))
            self.assertTrue(negatives <= allowed)
        with self.assertRaisesRegex(protocol.ProtocolError,'Unknown training query'):
            training.negative_candidates(self.inputs,'missing')

    def test_byte_deterministic_regeneration_and_overwrite_rejection(self):
        second=Path(self.temp.name)/'repeat'
        protocol.prepare_protocol(second)
        a={str(p.relative_to(self.output)):p.read_bytes() for p in self.output.rglob('*') if p.is_file()}
        b={str(p.relative_to(second)):p.read_bytes() for p in second.rglob('*') if p.is_file()}
        self.assertEqual(a,b)
        with self.assertRaisesRegex(protocol.ProtocolError,'never overwrite'):
            protocol.prepare_protocol(self.output)

    def test_source_integrity_failure_rejected_before_any_output(self):
        output=Path(self.temp.name)/'bad_source'
        original=protocol.extraction.sha256
        def wrong(path):
            return '0'*64 if Path(path)==protocol.EXTRACTION/'extraction_manifest.json' else original(path)
        with patch.object(protocol.extraction,'sha256',wrong):
            with self.assertRaisesRegex(protocol.ProtocolError,'Pinned extraction manifest mismatch'):
                protocol.prepare_protocol(output)
        self.assertFalse(output.exists())

    def test_saved_truth_tampering_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied=Path(directory)/'copy';shutil.copytree(self.output,copied)
            with (copied/'truth/test.jsonl').open('a') as handle:handle.write('\n')
            with self.assertRaisesRegex(protocol.ProtocolError,'checksum mismatch: truth/test.jsonl'):
                protocol.validate_saved_protocol(copied)
            # The isolated training API deliberately has no dependency on this truth file.
            self.assertEqual(training.load_training_data(copied,audit_only=True).candidate_ids,self.inputs.candidate_ids)

    def test_training_input_path_injection_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            copied=Path(directory)/'copy';shutil.copytree(self.output,copied)
            path=copied/'training/manifest.json';manifest=json.loads(path.read_text())
            manifest['files_sha256']['../truth/test.jsonl']='0'*64
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(protocol.ProtocolError,'Unexpected training input paths'):
                training.load_training_data(copied,audit_only=True)

    def test_weak_family_endpoints_not_published_for_evaluation(self):
        weak={r['nct_id'] for r in self.splits if r['heldout_review_quarantine']=='True'}
        for split in ('validation','test'):
            for q in protocol.read_jsonl(self.output/'truth'/(split+'.jsonl')):
                if weak & set(q['owner_trial_ids']):
                    self.assertFalse(q['eligible_for_novel_evaluation'])
                    self.assertIn('UNRESOLVED_WEAK_FAMILY_CANDIDATE',q['exclusion_reasons'])


if __name__=='__main__':unittest.main()
