# Public evidence replay — validation record (November 6, 2026)

## First completion milestone: source-only CLI

- Base public main: `b57afc6f0bfd24f3821c19bba9221c2b8ec8d471`.
- A shallow HTTPS clone of the public repository was created in
  `/private/tmp/htt-public-demo.y82TWk/checkout`.
- Only the new `demos/public_evidence_v1/` source was overlaid; no private runtime
  assets or existing development environments were copied.
- A fresh Python **3.14.6** environment was created with `--without-pip`.
  Tests and CLI ran with `-I -B`, without package installation.
- **11/11 Python tests passed**, 0 failures (clean environment: 0.437 seconds).
  Sponsor/intervention replay worked; outcome replay returned COMPLETE_LISTING,
  seven records and zero model attempts. This is a same-machine clean public-source
  test, not a different-OS deployment claim.

Exact commands (from repository root):

```bash
git clone --depth 1 --branch main https://github.com/akwasianing/HeartTrialTwin.git /private/tmp/htt-public-demo.y82TWk/checkout
mkdir -p /private/tmp/htt-public-demo.y82TWk/checkout/demos
cp -R demos/public_evidence_v1 /private/tmp/htt-public-demo.y82TWk/checkout/demos/
python3 -m venv --without-pip /private/tmp/htt-public-demo.y82TWk/stdlib-env
/private/tmp/htt-public-demo.y82TWk/stdlib-env/bin/python -I -B -m unittest discover -s /private/tmp/htt-public-demo.y82TWk/checkout/demos/public_evidence_v1/tests -p 'test_replay.py' -v
/private/tmp/htt-public-demo.y82TWk/stdlib-env/bin/python -I -B /private/tmp/htt-public-demo.y82TWk/checkout/demos/public_evidence_v1/replay.py --field intervention
/private/tmp/htt-public-demo.y82TWk/stdlib-env/bin/python -I -B /private/tmp/htt-public-demo.y82TWk/checkout/demos/public_evidence_v1/replay.py --field outcomes --json
```

The overlay is stated explicitly because the new branch was not yet published at
this milestone. No unpublished clinical evidence was copied into the clone.

## Static package and browser core

```bash
python3 -I -B demos/public_evidence_v1/build_site.py
python3 -I -B demos/public_evidence_v1/build_site.py --check
node --test demos/public_evidence_v1/tests/test_browser.mjs
python3 -I -B -m http.server 8521 --bind 127.0.0.1 --directory demos/public_evidence_v1/site
curl --fail --silent --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8521/
```

The evidence package is 18,960 bytes; SHA-256
`1eda3e31cd5315f6aab145c8cd3d9548416127b9c0a473309532e40eb517f6f3`.
**8/8 JavaScript tests passed**, 0 failures. Cases cover payload integrity,
source/citation bindings, duplicate/omitted records, cross-trial association,
unsupported effectiveness, invalid IDs, safe text rendering and no remote script
dependencies. There is no npm installation. HTTP startup check returned **200**.
Sandbox loopback restrictions required approved execution outside the sandbox
for the preview server and its HTTP check; there was no application defect.

## Actual browser interactions

The local page was exercised through a real browser, not a conceptual mockup:

| Case | Observed result |
| --- | --- |
| Package initialization | Packaged hash and citation bindings verified; replay enabled |
| All registered outcomes | COMPLETE_LISTING; seven records, original types/time frames/citations |
| Sponsor | Baylor College of Medicine; original citation |
| Intervention | Spironolactone; original citation |
| Survival-effectiveness safety example | ABSTAIN; zero records |
| NCT99999999 | NOT_FOUND within this replay; zero records |
| Script-like invalid identifier | INVALID_INPUT; zero records; no markup executed |
| Expanded outcome source | design_outcomes.txt record 1426532164 and correct trial → HAS_PLANNED_OUTCOME path |

See `validation/browser_checks.json` and the authentic browser screenshot.
No live Neo4j/Ollama service, fitted model, private credential or new registry
retrieval was used. Missing/tampered evidence was exercised in automated tests;
no production research file was edited to simulate corruption.

## Security and scientific boundary

All source evidence was previously published; original bytes and checksum
manifest are read-only. The package excludes arbitrary trial fields, private
configuration, model weights, runtime archives and unrelated local files.
No script accepts Cypher, arbitrary filesystem paths or unrestricted questions.
Dynamic evidence is rendered as text, not HTML. Hashes are integrity checks,
not independent proof of clinical truth or credential safety.

The previously exposed Neo4j credential remains unconfirmed rotated/revoked and
must be handled privately before live reuse. It was not read, copied, tested or
used here. This demo needs no Neo4j account.

Frozen results, Community v6, posters, QR, and the original default branch are
not modified. No deployment or automatic merge is included. Repository-only
static replay is functional; general live GraphRAG and clinical forecasting are
not offered by this small demo.
