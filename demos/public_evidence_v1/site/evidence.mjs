import {PINS} from './integrity.mjs';

export const NCT = 'NCT00206232';
export const DATASET = 'HTT-P1-AACT-20260905';
export const GRAPH = 'HTT-KG-AACT-20260905-FULL2824-v1';
export const SNAPSHOT = '2026-09-05';
const rules = {
  sponsor: ['LEAD_SPONSORED_BY', 'sponsors.txt', 1],
  intervention: ['HAS_INTERVENTION', 'interventions.txt', 1],
  outcomes: ['HAS_PLANNED_OUTCOME', 'design_outcomes.txt', 7],
};
function require(value, reason) { if (!value) throw new Error(reason); }
export async function digest(raw) {
  require(globalThis.crypto?.subtle, 'Integrity checking needs HTTPS or localhost.');
  const value = await crypto.subtle.digest('SHA-256', typeof raw === 'string' ? new TextEncoder().encode(raw) : raw);
  return [...new Uint8Array(value)].map(b => b.toString(16).padStart(2, '0')).join('');
}
export async function validateRecords(data) {
  require(data.schema_version === 'HTT-PUBLIC-EVIDENCE-REPLAY-v1' && data.mode === 'SAVED_EVIDENCE_REPLAY', 'Unexpected evidence schema');
  require(data.nct_id === NCT && data.dataset_version === DATASET && data.graph_version === GRAPH && data.snapshot_date === SNAPSHOT, 'Wrong dataset/trial scope');
  require(data.graph_manifest_sha256 === PINS.graph_manifest_sha256 && data.source_manifest_sha256 === PINS.source_manifest_sha256 && data.source_commit === PINS.source_commit, 'Provenance mismatch');
  require(JSON.stringify(Object.entries(data.source_trace_sha256).sort()) === JSON.stringify(Object.entries(PINS.source_trace_sha256).sort()), 'Original trace pins mismatch');
  require(Object.keys(data.records).sort().join() === Object.keys(rules).sort().join(), 'Unexpected record categories');
  const seen = new Set();
  for (const [kind, [type, table, count]] of Object.entries(rules)) {
    const records = data.records[kind];
    require(Array.isArray(records) && records.length === count, 'Incomplete record set');
    for (const record of records) {
      const rel = record.relationship;
      require(record.kind === kind && record.nct_id === NCT && record.evidence_id === `${NCT}|${type}|${record.node_id}`, 'Wrong record association');
      require(!seen.has(record.evidence_id), 'Duplicate evidence'); seen.add(record.evidence_id);
      require(typeof record.value === 'string' && record.value.length > 0 && record.value.length <= 5000, 'Missing source value');
      require(rel.start_id === NCT && rel.end_id === record.node_id && rel.type === type && rel.properties.dataset_version === DATASET && rel.properties.source_table === table, 'Wrong relationship');
      require(Array.isArray(record.citations) && record.citations.length > 0, 'Missing citations');
      for (const cite of record.citations) {
        const expected = 'cite:' + (await digest(JSON.stringify([GRAPH, NCT, table, cite.source_record_id, record.evidence_id]))).slice(0, 24);
        const ids = (rel.properties.source_record_ids ?? rel.properties.source_record_id ?? '').split(';');
        require(cite.citation_id === expected && cite.nct_id === NCT && cite.evidence_id === record.evidence_id && cite.source_table === table && ids.includes(cite.source_record_id), 'Citation/source binding mismatch');
        require(cite.dataset_version === DATASET && cite.graph_version === GRAPH && cite.snapshot_date === SNAPSHOT && cite.manifest_sha256 === PINS.graph_manifest_sha256, 'Citation provenance mismatch');
        require(JSON.stringify(cite.relationship) === JSON.stringify(rel), 'Citation relationship mismatch');
        require(typeof record.sentence === 'string' && record.sentence.includes(`[${cite.citation_id}]`), 'Missing original citation sentence');
      }
      if (kind === 'outcomes') require(typeof record.outcome_type === 'string' && typeof record.time_frame === 'string', 'Missing registered outcome fields');
    }
  }
  return data;
}
export async function verifyBytes(raw) {
  require(raw.byteLength > 0 && raw.byteLength <= 100000, 'Missing/oversized evidence package');
  require(await digest(raw) === PINS.payload_sha256, 'Evidence package hash mismatch. No facts will be shown.');
  return validateRecords(JSON.parse(new TextDecoder().decode(raw)));
}
export function selectEvidence(data, field, nct) {
  if (!/^NCT\d{8}$/.test(nct)) return {status: 'INVALID_INPUT', message: 'Enter an NCT identifier in the form NCT00206232.', records: []};
  if (nct !== NCT) return {status: 'NOT_FOUND', message: 'This saved replay contains only NCT00206232. Other trials are outside its scope, not necessarily absent from the registry.', records: []};
  if (!Object.hasOwn(rules, field)) return {status: 'ABSTAIN', message: 'Observed clinical effects and survival benefits are not available in these registered records. No clinical-effectiveness answer can be supported.', records: []};
  return {status: field === 'outcomes' ? 'COMPLETE_LISTING' : 'VERIFIED_REPLAY', message: field === 'outcomes' ? 'Complete saved listing: seven distinct registered measures.' : 'Verified registered evidence from the saved trace.', records: data.records[field]};
}
