import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {verifyBytes, validateRecords, selectEvidence} from '../site/evidence.mjs';
const raw = await fs.readFile(new URL('../site/evidence.json', import.meta.url));
const data = JSON.parse(raw);
test('browser package hash and all original citation identities', async () => assert.equal((await verifyBytes(raw)).nct_id, 'NCT00206232'));
test('complete seven outcomes, sponsor and intervention', () => {
  assert.equal(selectEvidence(data, 'outcomes', data.nct_id).records.length, 7);
  assert.equal(selectEvidence(data, 'sponsor', data.nct_id).records[0].value, 'Baylor College of Medicine');
  assert.equal(selectEvidence(data, 'intervention', data.nct_id).records[0].value, 'Spironolactone');
});
test('byte tampering and invalid JSON fail closed', async () => {
  await assert.rejects(verifyBytes(Buffer.from('{}')), /hash mismatch/);
  const edited = structuredClone(data); edited.records.sponsor[0].value = '<img src=x onerror=alert(1)>';
  await assert.rejects(verifyBytes(Buffer.from(JSON.stringify(edited))), /hash mismatch/);
});
test('cross-trial association, invented citation, omitted and duplicated records rejected', async () => {
  for (const change of ['owner','citation','missing','duplicate']) {
    const edited = structuredClone(data);
    if (change === 'owner') edited.records.outcomes[0].relationship.start_id = 'NCT99999999';
    if (change === 'citation') edited.records.outcomes[0].citations[0].citation_id = 'cite:invented';
    if (change === 'missing') edited.records.outcomes.pop();
    if (change === 'duplicate') edited.records.outcomes[1] = edited.records.outcomes[0];
    await assert.rejects(validateRecords(edited));
  }
});
test('wrong provenance rejected', async () => {
  const edited = structuredClone(data); edited.snapshot_date = '2027-01-01';
  await assert.rejects(validateRecords(edited));
});
test('unsupported request and unknown/invalid IDs never return facts', () => {
  assert.equal(selectEvidence(data,'unsupported',data.nct_id).status,'ABSTAIN');
  assert.equal(selectEvidence(data,'outcomes','NCT99999999').status,'NOT_FOUND');
  assert.equal(selectEvidence(data,'sponsor','<script>').status,'INVALID_INPUT');
  assert.deepEqual(selectEvidence(data,'invented',data.nct_id).records,[]);
});
test('browser renderer never interprets evidence as HTML or executes it', async () => {
  const js = await fs.readFile(new URL('../site/app.mjs',import.meta.url),'utf8');
  for (const unsafe of ['innerHTML','outerHTML','insertAdjacentHTML','eval(','new Function','document.write']) assert.equal(js.includes(unsafe),false,unsafe);
  assert.ok(js.includes('textContent'));
});
test('site has no remote script/style dependencies and deployment paths are relative', async () => {
  const html = await fs.readFile(new URL('../site/index.html',import.meta.url),'utf8');
  assert.equal(/(?:src|href)="https?:\/\/[^\"]+\.(?:js|css)/.test(html),false);
  assert.ok(html.includes("script-src 'self'"));
  assert.ok(html.includes('Saved-evidence replay'));
});
