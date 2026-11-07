import {verifyBytes, selectEvidence} from './evidence.mjs';
import {PINS} from './integrity.mjs';

const $ = id => document.getElementById(id);
let evidence = null;
function element(tag, value, className) {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
}
function render(result) {
  $('records').replaceChildren();
  $('result-title').textContent = result.status === 'COMPLETE_LISTING' ? 'Seven registered planned outcomes' : result.status === 'VERIFIED_REPLAY' ? 'Verified registered evidence' : 'No supported answer published';
  $('result-status').textContent = `${result.status} · ${result.message}`;
  $('result-status').className = result.records.length ? '' : 'error';
  for (const record of result.records) {
    const li = document.createElement('li');
    li.append(element('p', record.value, 'record-value'));
    if (record.kind === 'outcomes') {
      li.append(element('p', `Registered type: ${record.outcome_type} · Not an observed clinical result`, 'record-meta'));
      li.append(element('p', `Registered time frame: ${record.time_frame || 'Not recorded'}`, 'record-meta'));
    }
    li.append(element('p', record.citations.map(c => `[${c.citation_id}]`).join(' '), 'record-citation'));
    const detail = document.createElement('details');
    detail.append(element('summary', 'Inspect source record and trial association'));
    detail.append(element('p', `NCT: ${record.nct_id} · Evidence: ${record.evidence_id}`));
    for (const cite of record.citations) detail.append(element('p', `${cite.source_table} · source record ${cite.source_record_id} · ${cite.relationship.start_id} → ${cite.relationship.type} → ${cite.relationship.end_id}`));
    detail.append(element('p', record.sentence));
    li.append(detail); $('records').append(li);
  }
}
$('replay-form').addEventListener('submit', event => {
  event.preventDefault();
  if (!evidence) return;
  render(selectEvidence(evidence, $('field').value, $('nct').value.trim()));
});
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 8000);
try {
  const response = await fetch('./evidence.json', {cache: 'no-store', signal: controller.signal});
  if (!response.ok) throw new Error('Missing evidence');
  evidence = await verifyBytes(await response.arrayBuffer());
  $('integrity').textContent = 'Packaged evidence hash and citation bindings verified.';
  $('replay-button').disabled = false;
  $('hashes').textContent = JSON.stringify(PINS, null, 2);
} catch {
  evidence = null;
  $('integrity').textContent = 'Evidence unavailable or integrity check failed. No facts will be shown. Serve this folder over HTTPS or localhost; do not use file://.';
  $('integrity').className = 'error';
  $('result-status').textContent = 'INTEGRITY_ERROR · No answer published. Reload after restoring the verified assets.';
} finally { clearTimeout(timer); }
