"""External authorization and independently checked, role-limited V2 inputs.

Never calls the original loader with audit_only=True to train. Its default
training block and all pinned artifacts remain unchanged.
"""
from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from . import prepare_association_protocol_v2 as protocol

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = protocol.DEFAULT_OUTPUT
RUN = ROOT / 'gnn_graphrag/experiments/HTT-GNN-ASSOC-RUN-v1'
FEATURES = ROOT / 'gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1'
PROTOCOL_SHA = 'b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b'
AUTH_SHA = '2bea5b0305bc7e1f77e45fd04ac2759198b24a8be85b446121abc22a11167235'
CONFIG_SHA = 'e6e74d1b9e822810ecf1aa4f210610137397f897220c39a0f0216fc99185bf12'
LABELS = ('Trial', 'ConditionTerm', 'Intervention', 'Sponsor', 'PlannedOutcome', 'SourceDataset')
RELATIONS = frozenset({'HAS_SUBMITTED_CONDITION','HAS_BROWSE_CONDITION','HAS_INTERVENTION','LEAD_SPONSORED_BY'})
TRAIN_FILES = frozenset({'queries.jsonl','candidates.csv','families.csv','context_nodes.jsonl','message_edges.csv'})


class IntegrityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise IntegrityError(message)


def sha(path):
    return protocol.extraction.sha256(Path(path))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def object_sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def authorize(permission):
    for name, digest in [('authorization.json', AUTH_SHA), ('experiment_config.json', CONFIG_SHA)]:
        path = RUN / name
        require(not path.is_symlink() and sha(path) == digest, 'Authorization/configuration integrity mismatch')
    auth = json.loads((RUN / 'authorization.json').read_text())
    require(auth['protocol_sha256'] == PROTOCOL_SHA and permission in auth['permissions'], 'Operation not externally authorized')
    freeze = ROOT / 'gnn_graphrag/reviews/STEP_66C_3U_V2_FREEZE_APPROVAL.md'
    require(sha(freeze) == '64827422f70635ca40f4c0267374445808278e283736bd26a441046cd452f378', 'Freeze approval changed')
    return json.loads((RUN / 'experiment_config.json').read_text())


def manifest():
    path = PROTOCOL / 'split_manifest.json'
    require(not PROTOCOL.is_symlink() and not path.is_symlink() and sha(path) == PROTOCOL_SHA, 'Pinned protocol manifest mismatch')
    value = json.loads(path.read_text())
    require(value['schema_version'] == protocol.VERSION and value['status'] == protocol.STATE and value['training_permitted'] is False,
            'Unexpected frozen internal state')
    for name, digest in value['code_sha256'].items():
        require(sha(Path(protocol.__file__).with_name(name)) == digest, 'Original protocol code changed')
    return value


def bound_bytes(name, m):
    """Internal primitive. Public entry points supply constant allowlists."""
    require(name in m['files_sha256'] and not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe input path')
    path = PROTOCOL / name
    require(all(not p.is_symlink() for p in (path, *path.parents) if p == PROTOCOL or PROTOCOL in p.parents), 'Input symlink prohibited')
    require(path.resolve().is_relative_to(PROTOCOL.resolve()) and sha(path) == m['files_sha256'][name], 'Input checksum mismatch: ' + name)
    return path.read_bytes()


def rows(name, m):
    import csv
    import io
    data = bound_bytes(name, m).decode('utf-8')
    if name.endswith('.jsonl'):
        return [json.loads(line) for line in data.splitlines() if line.strip()]
    if name.endswith('.csv'):
        return list(csv.DictReader(io.StringIO(data)))
    return json.loads(data)


def check_context(nodes, edges):
    require(len(nodes) == 9036, 'Context node count mismatch')
    by_index = {}
    seen_ids = set()
    for i, row in enumerate(nodes):
        require(set(row) == {'node_index','node_id','node_label','feature_text'}, 'Unexpected context fields')
        require(int(row['node_index']) == i and row['node_label'] in LABELS[:4], 'Unsafe context ordering/label')
        text = row['feature_text']
        require(isinstance(text, str) and text.strip() and not re.fullmatch(r'Node type: \w+', text), 'Empty context text')
        require(not re.search(r'\bNCT\d{8}\b|source_record_id|\[cite:|planned_outcome:', text, re.I), 'Identifier/linkage in feature text')
        require(row['node_id'] not in seen_ids, 'Duplicate context ID')
        seen_ids.add(row['node_id'])
        by_index[str(i)] = row
    counts = {label:sum(r['node_label'] == label for r in nodes) for label in LABELS[:4]}
    require(counts == {'Trial':2824,'ConditionTerm':1743,'Intervention':3417,'Sponsor':1052}, 'Context label counts mismatch')
    require([LABELS.index(r['node_label']) for r in nodes] == sorted(LABELS.index(r['node_label']) for r in nodes), 'Context label order mismatch')
    seen = set()
    for edge in edges:
        require(set(edge) == set(protocol.extraction.MESSAGE_FIELDS), 'Unexpected edge fields')
        s,t = edge['source_node_index'],edge['target_node_index']
        rel = edge['relationship_type']
        require(rel in RELATIONS and s in by_index and t in by_index, 'Target/provenance/invalid edge')
        require(edge['source_node_label'] == by_index[s]['node_label'] and edge['target_node_label'] == by_index[t]['node_label'], 'Edge endpoint label mismatch')
        require(edge['message_direction'] in {'forward','reverse'}, 'Invalid computational direction')
        key = (s,rel,t)
        require(key not in seen, 'Duplicate typed message edge')
        seen.add(key)
    require(len(edges) == 61218 and all((t,r,s) in seen for s,r,t in seen), 'Context/reverse edge mismatch')


def feature_inputs():
    authorize('context_train_features')
    m = manifest()
    train_manifest = rows('training/manifest.json', m)
    require(train_manifest['training_permitted'] is False and set(train_manifest['files_sha256']) == TRAIN_FILES, 'Training-view identity mismatch')
    nodes = rows('training/context_nodes.jsonl', m)
    edges = rows('training/message_edges.csv', m)
    check_context(nodes, edges)
    queries = rows('training/queries.jsonl', m)
    ids = []
    for q in queries:
        require(set(q) == {'query_id','query_text','positive_trial_ids','ambiguous_trial_ids'}, 'Unexpected training query fields')
        text = q['query_text']
        require(text and text == protocol.normalize(text) and not protocol.extraction.NCT_TOKEN.search(text) and q['query_id'] == protocol.key('Q-', text), 'Invalid measure-only query')
        ids.append(q['query_id'])
    require(len(queries) == 11712 and ids == sorted(set(ids)), 'Training query order/count mismatch')
    candidates = rows('candidate_trials.csv', m)
    require([r['nct_id'] for r in candidates] == sorted(r['node_id'] for r in nodes[:2824])
            and [int(r['candidate_index']) for r in candidates] == list(range(2824)), 'Candidate universe mismatch')
    # Never return training association truth to the encoder.
    projected = [{'query_id':q['query_id'],'query_text':q['query_text']} for q in queries]
    return nodes, projected, edges, candidates


def training_inputs():
    """Independent gated equivalent of all original training-view safeguards."""
    authorize('training')
    m = manifest()
    tm = rows('training/manifest.json', m)
    require(tm.get('schema_version') == protocol.VERSION+'-TRAIN-INPUTS' and tm.get('status') == protocol.STATE
            and tm.get('training_permitted') is False and set(tm['files_sha256']) == TRAIN_FILES, 'Unexpected training-view state')
    for name, digest in tm['files_sha256'].items():
        require(digest == m['files_sha256']['training/'+name], 'Training-view hash conflict')
        bound_bytes('training/'+name,m)
    candidates = rows('training/candidates.csv',m)
    require(all(set(r) == {'nct_id'} for r in candidates), 'Unexpected training candidates')
    ids = tuple(r['nct_id'] for r in candidates)
    require(len(ids) == 1976 and ids == tuple(sorted(set(ids))) and all(re.fullmatch(r'NCT\d{8}',n) for n in ids), 'Invalid training IDs')
    families = rows('training/families.csv',m)
    require(len(families) == len(ids) and {r['nct_id'] for r in families} == set(ids)
            and all(set(r) == {'nct_id','family_id'} for r in families), 'Invalid training families')
    queries = rows('training/queries.jsonl',m)
    seen = set()
    allowed = set(ids)
    for q in queries:
        require(set(q) == {'query_id','query_text','positive_trial_ids','ambiguous_trial_ids'}, 'Unsafe training query')
        require(q['query_text'] and q['query_text'] == protocol.normalize(q['query_text'])
                and not protocol.extraction.NCT_TOKEN.search(q['query_text']) and q['query_id'] == protocol.key('Q-',q['query_text'])
                and q['query_id'] not in seen, 'Invalid training query identity')
        seen.add(q['query_id'])
        for field in ('positive_trial_ids','ambiguous_trial_ids'):
            require(q[field] == sorted(set(q[field])) and set(q[field]) <= allowed, 'Nontraining/duplicate labels')
        require(bool(q['positive_trial_ids']), 'Missing training positive')
    require(len(queries) == 11712, 'Training query count mismatch')
    nodes,edges = rows('training/context_nodes.jsonl',m),rows('training/message_edges.csv',m)
    check_context(nodes,edges)
    return {'queries':queries,'candidate_ids':ids,'families':families,'nodes':nodes,'edges':edges,
            'external_authorization_sha256':AUTH_SHA,'frozen_training_permitted':False}


def selected_checkpoint():
    path = RUN/'training/selection.json'
    require(path.is_file() and not path.is_symlink(), 'Test locked: checkpoint has not been selected')
    value = json.loads(path.read_text())
    require(value['protocol_sha256'] == PROTOCOL_SHA and value['config_sha256'] == CONFIG_SHA
            and value['authorization_sha256'] == AUTH_SHA and sha(RUN/'training/selected_model.pt') == value['checkpoint_sha256'], 'Selected checkpoint binding mismatch')
    return value


def evaluation_inputs(split, *, truth=False):
    require(split in {'validation','test'}, 'Unknown evaluation split')
    authorize('validation_evaluation' if truth and split == 'validation' else
              'validation_features' if split == 'validation' else
              'test_evaluation_after_selection' if truth else 'test_features_after_selection')
    if split == 'test':
        selected_checkpoint()
    m = manifest()
    queries = rows('evaluation/'+split+'_queries.jsonl',m)
    require(len(queries) == {'validation':2068,'test':2219}[split], 'Evaluation count mismatch')
    ids = [q['query_id'] for q in queries]
    require(ids == sorted(set(ids)) and all(set(q) == {'query_id','query_text'} and q['query_text'] == protocol.normalize(q['query_text'])
            and not protocol.extraction.NCT_TOKEN.search(q['query_text']) and q['query_id'] == protocol.key('Q-',q['query_text']) for q in queries), 'Unsafe evaluation projection')
    if not truth:
        return queries
    records = rows('truth/'+split+'.jsonl',m)
    eligible = {q['query_id']:q for q in records if q['eligible_for_novel_evaluation']}
    require(set(ids) == set(eligible) and all(not eligible[q]['exclusion_reasons'] for q in ids), 'Embargo/evaluation disagreement')
    return [eligible[q] for q in ids], rows('trial_splits.csv',m)


def save_json(path, value):
    with Path(path).open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)+'\n')


def bundle_manifest(directory, metadata):
    directory = Path(directory)
    hashes = {p.name:sha(p) for p in sorted(directory.iterdir()) if p.is_file()}
    value = {**metadata,'files_sha256':hashes,'protocol_sha256':PROTOCOL_SHA,'authorization_sha256':AUTH_SHA,'config_sha256':CONFIG_SHA}
    save_json(directory/'manifest.json',value)
    with (directory/'SHA256SUMS').open('x') as handle:
        for name in sorted([*hashes,'manifest.json']):
            handle.write(sha(directory/name)+'  '+name+'\n')
    return value


def verify_bundle(directory):
    directory = Path(directory)
    require(not directory.is_symlink(), 'Bundle symlink prohibited')
    m = json.loads((directory/'manifest.json').read_text())
    require(m['protocol_sha256'] == PROTOCOL_SHA and m['authorization_sha256'] == AUTH_SHA and m['config_sha256'] == CONFIG_SHA, 'Bundle identity mismatch')
    for name,digest in m['files_sha256'].items():
        require(Path(name).name == name and not (directory/name).is_symlink() and sha(directory/name) == digest, 'Bundle checksum mismatch: '+name)
    checks = {name:digest for digest,name in (line.split('  ') for line in (directory/'SHA256SUMS').read_text().splitlines())}
    require(checks == {**m['files_sha256'],'manifest.json':sha(directory/'manifest.json')}, 'Bundle checksum list mismatch')
    return m


@contextlib.contextmanager
def atomic_directory(destination):
    """Same-filesystem staging + exclusive publication; failures stay staged."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    lock = destination.parent/('.'+destination.name+'.lock')
    require(not lock.is_symlink(), 'Lock symlink prohibited')
    with lock.open('a+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        require(not destination.exists(), 'Never overwrite existing output: '+str(destination))
        stage = Path(tempfile.mkdtemp(prefix='.'+destination.name+'.incomplete-',dir=destination.parent))
        yield stage
        verify_bundle(stage)
        libc = ctypes.CDLL(None,use_errno=True)
        if hasattr(libc,'renamex_np'):
            result = libc.renamex_np(os.fsencode(stage),os.fsencode(destination),4)  # macOS RENAME_EXCL
        elif hasattr(libc,'renameat2'):
            result = libc.renameat2(-100,os.fsencode(stage),-100,os.fsencode(destination),1)
        else:
            raise IntegrityError('Atomic no-clobber rename unavailable; staged output retained')
        if result:
            raise OSError(ctypes.get_errno(),'Atomic exclusive publication failed; staging retained')
