# HeartTrialTwin Neo4j GraphRAG — Phase 1 retrieval

This prototype runs three fixed, parameterized, read-only Cypher workflows over
the verified 26-node, 65-relationship HeartTrialTwin graph. Phase 2 passes only
the user question and retrieved graph evidence to local Ollama by default.
OpenAI remains an optional provider. No Cypher is generated from user text.

## Setup

```bash
python3 -m venv .venv-graphrag
.venv-graphrag/bin/pip install -r graphrag/requirements.txt
cp graphrag/.env.example graphrag/.env
```

Set the four local values in `graphrag/.env`. The file is excluded by the root
`.gitignore`. Process environment variables take precedence. For continuity,
the script can also read the already configured, ignored
`artifacts/knowledge_graph/.env` without copying or displaying credentials.

The default provider uses Ollama at `http://localhost:11434` with
`qwen2.5:1.5b`; it requires no API key. Install and start Ollama, then make sure
the model is local:

```bash
ollama pull qwen2.5:1.5b
ollama serve
```

To use OpenAI instead, set `GRAPHRAG_LLM_PROVIDER=openai`, add
`OPENAI_API_KEY` privately, and optionally set `OPENAI_MODEL` (default:
`gpt-6-luna`). Never paste API keys into source, terminal commands,
screenshots, or result files.

Run all three workflows and save a uniquely named evidence trace:

```bash
.venv-graphrag/bin/python graphrag/src/retrieve.py --question all --save
```

Run a single workflow:

```bash
.venv-graphrag/bin/python graphrag/src/retrieve.py --question 1 --nct-id NCT00206232
```

Run grounded generation for one question or all three:

```bash
.venv-graphrag/bin/python graphrag/src/generate_answer.py --question 1
.venv-graphrag/bin/python graphrag/src/generate_answer.py --question 2
.venv-graphrag/bin/python graphrag/src/generate_answer.py --question 3
.venv-graphrag/bin/python graphrag/src/generate_answer.py --question all
```

Select the optional OpenAI provider explicitly:

```bash
.venv-graphrag/bin/python graphrag/src/generate_answer.py --provider openai --question 1
```

Each successful run writes a uniquely named trace containing the raw KG
evidence, generated answer, grounding checks, model configuration, timestamps,
token usage, and latency. Credentials are never included.

Run tests (tests use a fake read-only driver and do not require Aura access):

```bash
.venv-graphrag/bin/python -m unittest discover -s graphrag/tests -p 'test_*.py' -v
```

## Scientific safeguards

- Planned outcomes are labeled **registered planned outcomes, not clinical results**.
- Evidence comes from the pinned September 5, 2026 snapshot and may contain
  later amendments; it is not asserted to be the original registration record.
- The workflows do not add external medical facts, predictions, or clinical
  interpretations.
- All database calls use Neo4j read routing and fixed query templates.
- Generated answers are blocked if they cite unsupported NCT IDs or source
  record identifiers, omit provenance, or omit the planned-outcome safeguard.
- The 1.5B local model receives a compact evidence view that retains NCT IDs,
  source-record identifiers, relationship provenance, dataset version, and
  snapshot date. The full raw Neo4j evidence remains in the saved trace.
