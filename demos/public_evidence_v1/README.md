# HeartTrialTwin public evidence replay v1

**Saved-evidence replay, not live GraphRAG, generative AI, or prospective prediction.**
This small demonstration runs from public repository source alone. It is separate
from the full Community v6 application and its externally provisioned runtime.

**[Launch Public Demo](https://akwasianing.github.io/HeartTrialTwin/)** — deployed
and verified over public HTTPS on November 7, 2026. See the
[desktop/mobile verification](../../docs/PUBLIC_WEBSITE_VERIFICATION.md).

## Run immediately — Python standard library only

From the repository root, Python 3.10 or later (tested with 3.14.6):

```bash
python3 -I -B demos/public_evidence_v1/replay.py --field sponsor
python3 -I -B demos/public_evidence_v1/replay.py --field intervention
python3 -I -B demos/public_evidence_v1/replay.py --field outcomes
python3 -I -B demos/public_evidence_v1/replay.py --question "What planned outcomes were registered for NCT00206232?" --json
python3 -I -B -m unittest discover -s demos/public_evidence_v1/tests -p 'test_replay.py' -v
```

No pip install, environment file, Neo4j, Ollama, MiniLM, fitted model or private
asset is needed. Expected results: Baylor College of Medicine; Spironolactone;
seven exact source-bound outcome records. The source's spelling (including
"Quality of Life Questionaire") and registered time frames are preserved.

Only three explicit question templates are supported:

- `Who is the registered lead sponsor for NCT00206232?`
- `What intervention is registered for NCT00206232?`
- `What planned outcomes were registered for NCT00206232?`

Use `--field` for the equivalent declared request. Unsupported questions abstain;
another valid NCT ID yields `NOT_FOUND` **within this replay**, not a statement
about the registry. Invalid IDs yield `INVALID_INPUT`. Missing/tampered evidence
yields `INTEGRITY_ERROR`, no answer and process exit code 2. There is no keyword
router pretending to be a general-purpose question-answering model.

## Local browser demonstration

```bash
# Verify the existing package; do not regenerate it to bypass a failed check:
python3 -I -B demos/public_evidence_v1/build_site.py --check
python3 -I -B -m http.server 8521 --bind 127.0.0.1 --directory demos/public_evidence_v1/site
```

Open <http://127.0.0.1:8521/>. Click **Launch Demo**, choose one of the
three views, and click **Replay verified evidence**. Source details expose
original citation IDs, relationship paths, source tables and record IDs. A fourth
request demonstrates abstention for unsupported survival-effectiveness claims.
Do not open `index.html` using `file://`: fetch and cryptographic checks need
localhost or HTTPS. The approved public deployment is available at the URL above.

The static page has no framework, remote scripts, fonts, analytics, API calls,
cookies or persistence. `site/evidence.json` is a deterministic 18,960-byte
projection of the already-published records, not an additional dataset download.
The page uses `textContent` rather than HTML interpretation for evidence, an
explicit content-security policy, bounded fetch, and fail-closed integrity checks.

## Provenance and trust boundaries

Source traces, already present in public main
`b57afc6f0bfd24f3821c19bba9221c2b8ec8d471`:

`full_cohort_graphrag/semantic_v1/demo_v2/validation/HTT-DEMO-v2-SMOKE-v1/`

- `01_sponsor.json`: `e16ff47e33f5b3063706e0bf974eeea43dfdc2843c0dbb74474cd0b077f1f7b5`
- `02_intervention.json`: `02d28e838c7138ed7a7f4224a6d8202f4b38bead92d1848ebdda22974f09a73f`
- `03_outcomes.json`: `c48966909d1eda95481709d8188a67c154b0a7a663fb5e23527599c508c4eeab`
- Existing `manifest.json`: `37cb033b70248493f2df16de163a831a18042f15c5eae5eb8dee663754c92bb0`

The Python path verifies those original bytes and their existing pins, complete
14-path retrieval scope, prepared-evidence SHA-256, exact raw/prepared record
equality, trial ownership, original source IDs, recomputed citation identities,
and original sentence/catalog bindings. All seven outcome records must remain
present. The source graph manifest is
`3ef82624d131b36abc1eb9ad4e89b3439fed9f9600b92262c21bbcbfe6cf8757`.

The browser independently checks its packaged bytes against `integrity.mjs`,
then checks ownership, source IDs, relationship paths and recomputed citation
identities. **It does not fetch/reverify the complete original trace files.**
Those source hashes and pinned GitHub links are supplied for inspection; the
Python build/replay establishes the exact source-to-package mapping. Checksums
are not signatures and do not protect against a malicious change to both trusted
code and its pins. Registry correctness and clinical equivalence are not proven.

Dataset: `HTT-P1-AACT-20260905`; graph:
`HTT-KG-AACT-20260905-FULL2824-v1`; snapshot: September 5, 2026. Registered planned
outcomes are **not observed clinical results**. Snapshot fields may include
amendments; original-registration availability is not asserted. No prediction,
effectiveness inference, or clinical advice is produced.

## Validation and deployment

The original PR #2 [validation](VALIDATION.md) and
[publication allowlist](PUBLICATION_FILES.txt) remain historical records, not
the inventory of later documentation/deployment changes. See the
[current public verification](../../docs/PUBLIC_WEBSITE_VERIFICATION.md) and
[deployment record](DEPLOYMENT.md). Optional maintainer-only browser-core tests
use existing Node.js (no npm packages):

```bash
node --test demos/public_evidence_v1/tests/test_browser.mjs
```

No new registry bulk data, licenses, model weights or private assets are copied.
Only a small projection of already-published registry evidence is packaged, with
attribution and provenance retained. This does not grant rights over unrelated
third-party assets. The previously exposed Neo4j credential remains unconfirmed
rotated; it must be handled privately before live reuse. This replay never reads,
tests or transmits it.
