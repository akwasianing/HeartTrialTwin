# Scenario initialization — bounded diagnostic, no scientific change

**Disposition: earlier failure not reproduced; original cause remains unknown.**

Phase 3's initial 24-method run had 23 passes and a KeyError when the scenario
test expected `historical_profiles['count']`. The underlying worker response was
not saved, so that observation cannot now be attributed conclusively to missing
assets, a timeout, model deserialization, dependency imports or test ordering.
Its direct profile diagnostic subsequently took 42.871 s and a focused scenario
test passed. These remain historical observations, not erased by this phase.

## What was tested now

The new isolated source export received exactly the 144 missing assets through
the checksum-verified private archive. Both separate fresh Phase 3 environments
passed `pip check`; preflight passed with no missing assets or version errors.
No developer site-packages or project source paths were borrowed. Dependencies
were not reinstalled just to reproduce a successful installation.

`run_handoff.py` executed the existing 24 methods **once**, with scenario first.
A test-harness wrapper recorded only safe result fields, elapsed time, process
exit and stderr byte count. Production client/worker, models, test files,
preprocessing, input restrictions and 60-second timeout stayed byte-identical.

| New-process operation | Client wall time | Worker internal time | Result |
| --- | ---: | ---: | --- |
| Load historical development profiles | 4.338884 s | 3.939730 s | 257 profiles; process exit 0; stderr 0 bytes |
| NCT03015402 26 → 39 scenario replay | 2.408367 s | 2.047464 s | Four saved models; zero fits; no source writes; BLOCKED_UNCHANGED |

All **24/24** existing methods passed in **47.752541 s**, no failures/errors/skips.
The scenario method was not warmed by another scenario test in that process.
Operating-system disk/library caches were not cleared, so this is **not** a
physical cold-boot or independently replicated timing measurement.

## Interpretation and limits

- A mandatory test-order dependency was not reproduced: scenario worked first.
- Missing-asset and version problems are not present in this provisioned run.
  This does not establish what bytes or resource state caused the earlier error.
- Model/profile initialization and replay work in the tested fresh package set.
  No model fitting, forecast validation, altered scores or timeout increase occurred.
- Slower cold imports, filesystem caching or contention remain plausible, not
  verified explanations. One successful run does not establish a failure rate.
- Keep the existing fail-closed error messages and inspect safe worker codes
  if the issue recurs. Do not silently retry, warm-up as a hidden repair, suppress
  a failing test or call the root cause resolved.

The initial sandbox server failure was a **separate confirmed socket permission
issue**, not a scenario failure. After explicit localhost permission, startup
and HTTP health succeeded and the server stopped; see [SERVER_SMOKE.json](SERVER_SMOKE.json).

Detailed structural events: [EXECUTION_RESULTS.json](EXECUTION_RESULTS.json).
