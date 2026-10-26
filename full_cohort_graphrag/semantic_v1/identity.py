"""Immutable serving identity; no training/truth imports or runtime dependencies."""
from pathlib import Path
import hashlib
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'HTT-MINILM-GRAPHRAG-v1'
DATASET = 'HTT-P1-AACT-20260905'
GRAPH = 'HTT-KG-AACT-20260905-FULL2824-v1'
SNAPSHOT = '2026-09-05'
FEATURES = ROOT/'gnn_graphrag/feature_artifacts/HTT-GNN-ASSOC-FEATURES-v1'
PROTOCOL = ROOT/'gnn_graphrag/protocols/HTT-GNN-ASSOC-PROTOCOL-v2'
FEATURE_SHA = 'e2f167b01b2e83aef1f11ef6e4dba673d741246927a43f30936888beecf99a17'
PROTOCOL_SHA = 'b13d662390b687b62a08cc1fb81bd3413f2c9d1fbb3b6ec86438b1a6854cd95b'
MODEL = 'sentence-transformers/all-MiniLM-L6-v2'
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
SNAPSHOT_SHA = 'fa4e0ce8c98e7af6762dcc8d1930113fab9c487f5c59ba80c5e9d3e098b0f8b2'
DIMENSION = 384
TRIAL_COUNT = 2824
MAX_K = 20


class SemanticError(ValueError):
    """Safe public errors, never raw driver/worker exception contents."""


def require(value, message):
    if not value:
        raise SemanticError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def check_k(value, maximum=MAX_K):
    require(type(value) is int and 1 <= value <= maximum, 'Invalid top_k bound')


def check_text(value):
    require(isinstance(value, str) and value.strip() and len(value) <= 2000
            and not any(ord(c) < 32 for c in value), 'Invalid or oversized question text')


def normalize_query(value):
    check_text(value)
    return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())
