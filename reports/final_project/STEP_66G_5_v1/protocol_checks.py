"""Existing frozen-fixture regression methods; never regenerate or mutate splits.

Same invocation policy as STEP_66C_3U_V2_FREEZE_APPROVAL.md. Truth is inspected
only by integrity checks, not by a model or model-selection procedure.
"""
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
EXCLUDED = {
    'test_byte_deterministic_regeneration_and_overwrite_rejection',
    'test_source_integrity_failure_rejected_before_any_output',
    'test_saved_truth_tampering_detected',
    'test_training_input_path_injection_is_rejected',
}


def suite():
    result = unittest.TestSuite()
    for name in ('test_association_protocol', 'test_association_protocol_v2'):
        module = importlib.import_module('gnn_graphrag.tests.' + name)
        def saved_setup(cls, module=module):
            cls.output = module.protocol.DEFAULT_OUTPUT
            cls.audit = module.protocol.validate_saved_protocol(cls.output)['actual_counts']
            cls.splits = module.protocol.read_csv(cls.output / 'trial_splits.csv')
            cls.partition = {r['nct_id']: r['split'] for r in cls.splits}
            cls.positives = module.protocol.read_csv(cls.output / 'positive_associations.csv')
            cls.catalog = module.protocol.read_jsonl(cls.output / 'query_catalog.jsonl')
            cls.overlaps = {r['query_id']: r for r in module.protocol.read_csv(cls.output / 'query_overlap_audit.csv')}
            cls.inputs = module.training.load_training_data(cls.output, audit_only=True)
        case = module.AssociationProtocolTests
        case.setUpClass = classmethod(saved_setup)
        case.tearDownClass = classmethod(lambda cls: None)
        names = unittest.defaultTestLoader.getTestCaseNames(case)
        assert EXCLUDED <= set(names)
        result.addTests(case(n) for n in names if n not in EXCLUDED)
    return result


if __name__ == '__main__':
    runner = unittest.TextTestRunner(verbosity=2)
    if len(sys.argv) == 2:
        with Path(sys.argv[1]).open('x') as handle:
            outcome = unittest.TextTestRunner(stream=handle, verbosity=2).run(suite())
    else:
        outcome = runner.run(suite())
    assert outcome.testsRun == 31 and outcome.wasSuccessful() and not outcome.skipped
    print('31 existing saved-fixture protocol tests passed; eight mutation/regeneration methods were not selected.')
