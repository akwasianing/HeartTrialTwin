#!/usr/bin/env python3
"""Deterministic, offline association protocol. No encoders or training imports."""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import itertools
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

try:
    from . import extract_full_cohort as extraction
except ImportError:
    import extract_full_cohort as extraction

ROOT = Path(__file__).resolve().parents[2]
VERSION = "HTT-GNN-ASSOC-PROTOCOL-v2"
EXTRACTION = ROOT / "gnn_graphrag/data/HTT-GNN-FULL2824-EXTRACT-v1"
EXTRACTION_SHA256 = "3fe45287cc12f4d752545c90c9d63a375370b69d070be47cb04b79398da6b6a3"
DEFAULT_OUTPUT = ROOT / "gnn_graphrag/protocols" / VERSION
FAMILY_RESOLUTION = ROOT / "full_system_feasibility/related_study_resolution.csv"
FAMILY_METADATA = ROOT / "full_system_feasibility/related_study_metadata.jsonl"
SEED = 20261023
RATIOS = {"train": .70, "validation": .15, "test": .15}
STATE = "PROVISIONAL_FAMILY_AUDIT_REVIEW_REQUIRED"
TARGET = "HAS_PLANNED_OUTCOME"
GENERIC_TITLE_WORDS = frozenset("the and with for from into study trial patients patient heart failure chronic acute effect effects evaluation treatment in to of a an on".split())
GENERIC_INTERVENTIONS = frozenset({"placebo", "usual care", "standard care", "no intervention", "control"})


class ProtocolError(ValueError):
    """No fallback or silent repair is authorized."""


def require(condition, message):
    if not condition:
        raise ProtocolError(message)


def normalize(text):
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def punctuation_key(text):
    # Screening only: this must never redefine positive clinical associations.
    return re.sub(r"[^\w]+", " ", normalize(text)).strip()


def key(prefix, value):
    return prefix + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for value in values:
            handle.write(extraction.canonical(value) + "\n")


def source_inputs(directory=EXTRACTION):
    directory = Path(directory)
    manifest_path = directory / "extraction_manifest.json"
    require(extraction.sha256(manifest_path) == EXTRACTION_SHA256, "Pinned extraction manifest mismatch")
    manifest = json.loads(manifest_path.read_text())
    require(manifest["source"]["manifest_sha256"] == extraction.MANIFEST_SHA256, "Source manifest identity mismatch")
    hashes = {str(manifest_path.relative_to(ROOT)): EXTRACTION_SHA256}
    for name, item in manifest["outputs"].items():
        path = directory / name
        require(path.is_file() and extraction.sha256(path) == item["sha256"], "Extraction output checksum mismatch: " + name)
        hashes[str(path.relative_to(ROOT))] = item["sha256"]
    for line in (directory / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ")
        require(name in {*manifest["outputs"], "extraction_manifest.json"}, "Unexpected extraction checksum entry")
        require(extraction.sha256(directory / name) == digest, "Extraction checksum-list mismatch")
    hashes[str((directory / "SHA256SUMS").relative_to(ROOT))] = extraction.sha256(directory / "SHA256SUMS")
    source_manifest = extraction.DEFAULT_SOURCE / "full_cohort_manifest.json"
    require(extraction.sha256(source_manifest) == extraction.MANIFEST_SHA256, "Pinned full-cohort source manifest mismatch")
    hashes[str(source_manifest.relative_to(ROOT))] = extraction.MANIFEST_SHA256
    source = json.loads(source_manifest.read_text())
    for name, digest in source["files_sha256"].items():
        path = extraction.DEFAULT_SOURCE / name
        require(extraction.sha256(path) == digest, "Pinned source checksum mismatch: " + name)
        hashes[str(path.relative_to(ROOT))] = digest
    frozen = ROOT / source["membership"]["frozen_source"]
    require(extraction.sha256(frozen) == source["membership"]["frozen_source_sha256"], "Original membership checksum mismatch")
    hashes[str(frozen.relative_to(ROOT))] = source["membership"]["frozen_source_sha256"]
    nodes = read_csv(directory / "nodes.csv")
    relationships = read_csv(directory / "relationships.csv")
    require(len(nodes) == 28777 and len(relationships) == 79125, "Extraction count mismatch")
    indexed = {row["node_index"]: row for row in nodes}
    require(len(indexed) == len(nodes), "Duplicate extraction indices")
    for row in nodes:
        require(hashlib.sha256(row["feature_text"].encode()).hexdigest() == row["feature_text_sha256"], "Feature-text checksum mismatch")
        require(not extraction.NCT_TOKEN.search(row["feature_text"]), "NCT identifier in semantic text")
    props = {row["node_id"]: json.loads(row["properties_json"]) for row in nodes}
    trials = {row["node_id"]: props[row["node_id"]] for row in nodes if row["node_label"] == "Trial"}
    outcomes = {row["node_id"]: props[row["node_id"]] for row in nodes if row["node_label"] == "PlannedOutcome"}
    associations = []
    for row in relationships:
        if row["relationship_type"] != TARGET:
            continue
        oid, nct = row["target_node_id"], row["source_node_id"]
        p, rel = outcomes[oid], json.loads(row["properties_json"])
        require(nct in trials and p["nct_id"] == nct and rel["source_record_id"] == p["source_record_id"], "Outcome source binding mismatch")
        require(bool(normalize(p["measure"])), "Blank query measure")
        associations.append({"outcome_id": oid, "nct_id": nct, "evidence_id": f"{nct}|{TARGET}|{oid}",
            "source_record_id": p["source_record_id"], "source_table": "design_outcomes.txt",
            "relationship_index": row["relationship_index"], "measure": p["measure"],
            "outcome_type": p["outcome_type"], "time_frame": p["time_frame"]})
    require(len(associations) == len({r["outcome_id"] for r in associations}) == 19740, "Positive association count mismatch")
    for path in (FAMILY_RESOLUTION, FAMILY_METADATA):
        hashes[str(path.relative_to(ROOT))] = extraction.sha256(path)
    metadata = read_jsonl(FAMILY_METADATA)
    for row in metadata:
        value = {k: v for k, v in row.items() if k != "selected_metadata_sha256"}
        digest = hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        require(digest == row["selected_metadata_sha256"] and row["nct_id"] == row["nct_id_from_source"], "Prior family metadata integrity mismatch")
    return manifest, nodes, relationships, trials, outcomes, associations, hashes


def screen_families(trials, relationships, nodes):
    """Full-cohort screening, not proof of exhaustive clinical-family identity."""
    properties = {r["node_id"]: json.loads(r["properties_json"]) for r in nodes}
    sponsors, interventions = defaultdict(set), defaultdict(set)
    for rel in relationships:
        nct = rel["source_node_id"]
        if rel["relationship_type"] == "LEAD_SPONSORED_BY":
            sponsors[nct].add(rel["target_node_id"])
        elif rel["relationship_type"] == "HAS_INTERVENTION":
            if normalize(properties[rel["target_node_id"]]["name"]) not in GENERIC_INTERVENTIONS:
                interventions[nct].add(rel["target_node_id"])
    titles = {n: punctuation_key(p["brief_title"]) for n, p in trials.items()}
    candidates, exact, postings = {}, defaultdict(list), defaultdict(list)
    for nct, title in sorted(titles.items()):
        exact[title].append(nct)
        for word in sorted(set(title.split()) - GENERIC_TITLE_WORDS):
            if len(word) >= 4:
                postings[word].append(nct)
    pairs = set()
    for title, members in exact.items():
        if title:
            pairs.update(itertools.combinations(members, 2))
    # All trials are screened; blocking is bounded and explicitly not exhaustive.
    for members in postings.values():
        if 2 <= len(members) <= 80:
            pairs.update(itertools.combinations(members, 2))
    for left, right in sorted(pairs):
        a, b = titles[left], titles[right]
        if not a or not b or min(len(a), len(b)) / max(len(a), len(b)) < .8:
            continue
        matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
        if a != b and matcher.quick_ratio() < .90:
            continue
        similarity = 1.0 if a == b else matcher.ratio()
        if similarity < .90:
            continue
        support = bool(sponsors[left] & sponsors[right] or interventions[left] & interventions[right])
        strong = (a == b and len(a) >= 30 and len(a.split()) >= 5) or (similarity >= .95 and support)
        candidates[(left, right)] = {"left_nct_id": left, "right_nct_id": right,
            "classification": "UNRESOLVED", "strength": "STRONG" if strong else "WEAK",
            "rule": "exact_normalized_title" if a == b else "blocked_near_title",
            "title_similarity": f"{similarity:.8f}", "entity_support": support,
            "review_source": "AUTOMATED_NOT_HUMAN_REVIEWED", "evidence": "Textual candidate only; shared entities do not prove family identity."}
    for row in read_csv(FAMILY_RESOLUTION):
        left, right = sorted((row["left_nct_id"], row["right_nct_id"]))
        require(left in trials and right in trials, "Prior family pair outside cohort")
        status = row["classification"]
        require(status in {"CONFIRMED_RELATED", "UNRESOLVED", "REJECTED"}, "Unknown family classification")
        candidates[(left, right)] = {"left_nct_id": left, "right_nct_id": right,
            "classification": status, "strength": "STRONG" if status != "REJECTED" else "REJECTED",
            "rule": "prior_identifier_review", "title_similarity": f"{difflib.SequenceMatcher(None,titles[left],titles[right],autojunk=False).ratio():.8f}",
            "entity_support": bool(sponsors[left] & sponsors[right] or interventions[left] & interventions[right]),
            "review_source": "related_study_resolution.csv", "evidence": row["evidence"]}
    parent = {n: n for n in trials}
    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n
    for (left, right), row in sorted(candidates.items()):
        if row["classification"] != "REJECTED" and row["strength"] == "STRONG":
            a, b = sorted((find(left), find(right)))
            parent[b] = a
    members = defaultdict(list)
    for nct in sorted(trials):
        members[find(nct)].append(nct)
    family = {n: key("FAM-", "|".join(group)) for group in members.values() for n in group}
    quarantine = {family[n] for row in candidates.values() if row["classification"] == "UNRESOLVED"
                  and row["strength"] == "WEAK" for n in (row["left_nct_id"], row["right_nct_id"])}
    classifications = defaultdict(set)
    for row in candidates.values():
        if row["classification"] != "REJECTED" and row["strength"] == "STRONG":
            classifications[family[row["left_nct_id"]]].add(row["classification"])
    result = []
    for nct in sorted(trials):
        kinds = classifications[family[nct]]
        status = ("MIXED" if len(kinds) > 1 else "CONFIRMED_ONLY" if kinds == {"CONFIRMED_RELATED"}
                  else "UNRESOLVED_GROUP" if kinds else "SINGLETON")
        result.append({"nct_id": nct, "family_id": family[nct], "family_status": status,
                       "heldout_review_quarantine": family[nct] in quarantine})
    return list(candidates.values()), result


def allocate(family_rows, positive_counts, seed=SEED):
    groups = defaultdict(list)
    for row in family_rows:
        groups[row["family_id"]].append(row["nct_id"])
    vectors = {g: (len(members), sum(positive_counts[n] > 0 for n in members),
                   sum(positive_counts[n] for n in members)) for g, members in groups.items()}
    totals = tuple(sum(v[i] for v in vectors.values()) for i in range(3))
    current = {s: [0, 0, 0] for s in RATIOS}
    assignment = {}
    order = sorted(
    groups,
    key=lambda g: hashlib.sha256(
        f"{seed}|{g}".encode("utf-8")
    ).hexdigest()
)
    for group in order:
        def cost(selected):
            return sum(((current[s][i] + (vectors[group][i] if s == selected else 0)
                         - totals[i]*RATIOS[s]) / max(1, totals[i]*RATIOS[s]))**2
                       for s in RATIOS for i in range(3))
        chosen = min(RATIOS, key=lambda s: (cost(s), list(RATIOS).index(s)))
        for nct in groups[group]:
            assignment[nct] = chosen
        current[chosen] = [a+b for a,b in zip(current[chosen], vectors[group])]
    return assignment


def near_text_pairs(texts, max_characters):
    """Bounded lexical screen only. Never merges truth or claims equivalence."""
    result = {}
    punctuation = defaultdict(list)
    for text in sorted(texts):
        punctuation[punctuation_key(text)].append(text)
    for value, members in punctuation.items():
        if value:
            for a, b in itertools.combinations(members, 2):
                result[(a,b)] = ("PUNCTUATION_CANDIDATE", 1.0)
    ordered = sorted(t for t in texts if 30 <= len(t) <= max_characters)
    for a, b in zip(ordered, ordered[1:]):
        if min(len(a),len(b))/max(len(a),len(b)) < .9:
            continue
        matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
        if matcher.quick_ratio() >= .95:
            score = matcher.ratio()
            if score >= .95:
                result.setdefault((a,b), ("ADJACENT_LEXICAL_CANDIDATE", score))
    return [(a,b,kind,score) for (a,b),(kind,score) in sorted(result.items())]


def prepare_protocol(output_dir=DEFAULT_OUTPUT):
    output = Path(output_dir)
    require(not output.exists(), "Output directory exists; never overwrite a protocol")
    manifest, nodes, relationships, trials, outcomes, associations, source_hashes = source_inputs()
    pairs, families = screen_families(trials, relationships, nodes)
    counts = Counter(r["nct_id"] for r in associations)
    splits = allocate(families, counts)
    family_by_nct = {r["nct_id"]: r for r in families}
    groups = defaultdict(list)
    for row in associations:
        row.update(split=splits[row["nct_id"]], query_id=key("Q-", normalize(row["measure"])))
        groups[normalize(row["measure"])].append(row)
    queries = {}
    for text, rows in sorted(groups.items()):
        qid = key("Q-", text)
        require(qid not in queries, "Query hash collision")
        queries[qid] = {"query_id": qid, "query_text": text,
            "owner_trial_ids": sorted({r["nct_id"] for r in rows}),
            "source_associations": sorted(rows, key=lambda r:r["outcome_id"])}
    require(len(queries) == 16290, "Normalized query count differs from audit")
    query_by_text = {q["query_text"]: q for q in queries.values()}
    near = defaultdict(set)
    near_records = []
    for a,b,kind,score in near_text_pairs(query_by_text,800):
        left,right=query_by_text[a],query_by_text[b]
        near[left["query_id"]].add(right["query_id"])
        near[right["query_id"]].add(left["query_id"])
        near_records.append({"left_query_id":left["query_id"],"right_query_id":right["query_id"],
            "rule":kind,"similarity":f"{score:.8f}","review_status":"UNRESOLVED_EXCLUDED_IF_CROSS_PARTITION",
            "cross_partition":len({splits[n] for n in left["owner_trial_ids"]+right["owner_trial_ids"]})>1})
    query_splits = {qid:{splits[n] for n in q["owner_trial_ids"]} for qid,q in queries.items()}
    reasons = {}
    for qid,q in queries.items():
        errors=[]
        if len(query_splits[qid])>1:errors.append("EXACT_QUERY_CROSS_PARTITION")
        if any(len(query_splits[qid]|query_splits[other])>1 for other in near[qid]):
            errors.append("UNRESOLVED_NEAR_QUERY_CROSS_PARTITION")
        if any(family_by_nct[n]["heldout_review_quarantine"] for n in q["owner_trial_ids"]):
            errors.append("UNRESOLVED_WEAK_FAMILY_CANDIDATE")
        reasons[qid]=errors

    descriptions = defaultdict(list)
    for oid,p in sorted(outcomes.items()):
        if normalize(p["description"]):descriptions[normalize(p["description"])].append((oid,p["nct_id"]))
    description_rows=[]
    for text,rows in sorted(descriptions.items()):
        if len({n for _,n in rows})>1:
            description_rows.append({"kind":"EXACT_NORMALIZED_DESCRIPTION", "left_text_sha256":key("",text),
                "right_text_sha256":key("",text),"outcome_ids":extraction.canonical(sorted(o for o,_ in rows)),
                "trial_ids":extraction.canonical(sorted({n for _,n in rows})),
                "partitions":extraction.canonical(sorted({splits[n] for _,n in rows})),
                "similarity":"1.00000000","action":"AUDIT_ONLY_NOT_A_MODEL_INPUT_OR_EQUIVALENCE_LABEL"})
    for a,b,kind,score in near_text_pairs(descriptions,2000):
        rows=descriptions[a]+descriptions[b]
        if len({n for _,n in rows})>1:
            description_rows.append({"kind":kind,"left_text_sha256":key("",a),"right_text_sha256":key("",b),
                "outcome_ids":extraction.canonical(sorted(o for o,_ in rows)),
                "trial_ids":extraction.canonical(sorted({n for _,n in rows})),
                "partitions":extraction.canonical(sorted({splits[n] for _,n in rows})),
                "similarity":f"{score:.8f}","action":"AUDIT_ONLY_NOT_A_MODEL_INPUT_OR_EQUIVALENCE_LABEL"})

    output.mkdir(parents=True,exist_ok=False)
    pair_fields=("left_nct_id","right_nct_id","classification","strength","rule","title_similarity","entity_support","review_source","evidence")
    write_csv(output/"family_pairs.csv",pair_fields,sorted(pairs,key=lambda r:(r['left_nct_id'],r['right_nct_id'])))
    write_csv(output/"family_groups.csv",("nct_id","family_id","family_status","heldout_review_quarantine"),families)
    trial_rows=[{**r,"split":splits[r["nct_id"]],"positive_associations":counts[r["nct_id"]],
        "has_planned_outcomes":bool(counts[r["nct_id"]])} for r in families]
    write_csv(output/"trial_splits.csv",("nct_id","family_id","family_status","heldout_review_quarantine","split","positive_associations","has_planned_outcomes"),trial_rows)
    write_csv(output/"positive_associations.csv",tuple(associations[0]),sorted(associations,key=lambda r:r['outcome_id']))
    write_jsonl(output/"query_catalog.jsonl",[queries[q] for q in sorted(queries)])
    overlap_rows=[{"query_id":qid,"partitions":extraction.canonical(sorted(query_splits[qid])),
        "owner_count":len(q["owner_trial_ids"]),"near_query_ids":extraction.canonical(sorted(near[qid])),
        "exclusion_reasons":extraction.canonical(reasons[qid]),"eligible_for_novel_evaluation":not reasons[qid] and query_splits[qid]!={"train"}}
        for qid,q in sorted(queries.items())]
    write_csv(output/"query_overlap_audit.csv",tuple(overlap_rows[0]),overlap_rows)
    write_csv(output/"near_query_candidates.csv",("left_query_id","right_query_id","rule","similarity","review_status","cross_partition"),near_records)
    write_csv(output/"duplicate_description_audit.csv",("kind","left_text_sha256","right_text_sha256","outcome_ids","trial_ids","partitions","similarity","action"),description_rows)
    write_csv(output/"candidate_trials.csv",("candidate_index","nct_id"),[{"candidate_index":i,"nct_id":n} for i,n in enumerate(sorted(trials))])

    split_counts={}
    for split in RATIOS:
        truth=[];model_queries=[]
        for qid,q in sorted(queries.items()):
            selected=[r for r in q["source_associations"] if r["split"]==split]
            if not selected:continue
            truth.append({"query_id":qid,"query_text":q["query_text"],"split":split,
                "owner_trial_ids":sorted({r["nct_id"] for r in selected}),"source_associations":selected,
                "eligible_for_novel_evaluation":split!="train" and not reasons[qid],"exclusion_reasons":reasons[qid] if split!="train" else []})
            if split!="train" and not reasons[qid]:model_queries.append({"query_id":qid,"query_text":q["query_text"]})
        write_jsonl(output/"truth"/(split+".jsonl"),truth)
        if split!="train":write_jsonl(output/"evaluation"/(split+"_queries.jsonl"),model_queries)
        split_counts[split]={"trials":sum(s==split for s in splits.values()),
            "trials_with_outcomes":sum(counts[n]>0 for n,s in splits.items() if s==split),
            "positive_associations":sum(counts[n] for n,s in splits.items() if s==split),
            "queries_before_embargo":len(truth),"novel_evaluation_queries":len(model_queries),
            "novel_evaluation_positive_records":sum(len(r["source_associations"]) for r in truth if r["eligible_for_novel_evaluation"]),
            "trials_after_embargo":len({n for r in truth if r["eligible_for_novel_evaluation"] for n in r["owner_trial_ids"]})}

    training_queries=[]
    family_members=defaultdict(set)
    for nct,split in splits.items():
        if split=="train":family_members[family_by_nct[nct]["family_id"]].add(nct)
    ambiguous_families={fid:{fid} for fid in family_members}
    for pair in pairs:
        if pair['classification']=='UNRESOLVED':
            left=family_by_nct[pair['left_nct_id']]['family_id']
            right=family_by_nct[pair['right_nct_id']]['family_id']
            ambiguous_families.setdefault(left,{left}).add(right)
            ambiguous_families.setdefault(right,{right}).add(left)
    for qid,q in sorted(queries.items()):
        positive={n for n in q["owner_trial_ids"] if splits[n]=="train"}
        if not positive:continue
        ambiguity={n for other in near[qid] for n in queries[other]["owner_trial_ids"] if splits[n]=="train"}
        positive_families={family_by_nct[n]["family_id"] for n in positive}
        ambiguity|={n for fid in positive_families for other in ambiguous_families[fid] for n in family_members[other]}
        training_queries.append({"query_id":qid,"query_text":q["query_text"],"positive_trial_ids":sorted(positive),
                                 "ambiguous_trial_ids":sorted(ambiguity-positive)})
    write_jsonl(output/"training/queries.jsonl",training_queries)
    write_csv(output/"training/candidates.csv",("nct_id",),[{"nct_id":n} for n in sorted(trials) if splits[n]=="train"])
    context=[{"node_index":r["node_index"],"node_id":r["node_id"],"node_label":r["node_label"],
        "feature_text":r["feature_text"]} for r in nodes if r["node_label"] not in {"PlannedOutcome","SourceDataset"}]
    # Copy existing approved text, not new semantic features or embedding vectors.
    write_jsonl(output/"training/context_nodes.jsonl",context)
    masks=[];retained=[]
    with (EXTRACTION/"message_edges_semantic.csv").open(newline='') as handle:
        for row in csv.DictReader(handle):
            include=row["relationship_type"] not in {TARGET,*extraction.PROVENANCE_TYPES}
            masks.append({"message_edge_index":row["message_edge_index"],"original_relationship_index":row["original_relationship_index"],
                "relationship_type":row["relationship_type"],"message_direction":row["message_direction"],
                "retained":include,"reason":"ALLOWED_NON_TARGET_CONTEXT" if include else "TARGET_OR_PROVENANCE_EXCLUDED"})
            if include:retained.append(row)
    require(len(masks)==100698 and len(retained)==61218,"Masked message counts differ from protocol")
    write_csv(output/"message_edge_mask.csv",tuple(masks[0]),masks)
    write_csv(output/"training/message_edges.csv",extraction.MESSAGE_FIELDS,retained)
    write_csv(output/"training/families.csv",("nct_id","family_id"),[{k:r[k] for k in ("nct_id","family_id")} for r in families if splits[r['nct_id']]=='train'])
    train_files={p.name:extraction.sha256(p) for p in sorted((output/"training").iterdir())}
    write_json(output/"training/manifest.json",{"schema_version":VERSION+"-TRAIN-INPUTS", "status":STATE,
        "training_permitted":False,"seed":SEED,"files_sha256":train_files,
        "extraction_manifest_sha256":EXTRACTION_SHA256,"observed_graph_not_inductive":True})

    policy={"schema_version":VERSION,"status":STATE,"training_permitted":False,"formal_evaluation_status":"NOT_RUN",
        "task":"Registered planned-outcome measure-to-trial association ranking; not clinical outcome prediction",
        "dataset_version":extraction.DATASET_VERSION,"graph_version":extraction.GRAPH_VERSION,"snapshot_date":extraction.SNAPSHOT_DATE,
        "seed":SEED,"allocation":{
            "target_ratios":RATIOS,
            "algorithm":(
                "Family groups ordered by seeded SHA-256 hash of seed and family ID. "
                "Greedy allocation minimizes summed squared relative deviations "
                "in total trials, eligible trials, and positive associations; "
                "split-order tie-break."
            ),
            "performance_used":False
        },        
        "family_screen":{"status":"PROVISIONAL_NOT_EXHAUSTIVE","all_trials_screened":2824,
            "exact_strong":"Exact punctuation-normalized title >=30 characters and >=5 words",
            "near":"Shared non-generic title token >=4 characters occurring in 2..80 trials; title length ratio>=0.8; SequenceMatcher>=0.90",
            "near_strong":"Similarity>=0.95 plus a shared lead sponsor or non-generic intervention; still UNRESOLVED",
            "weak":"Unresolved weak endpoints and their grouped families are quarantined from held-out evaluation",
            "rejected":"Prior explicit REJECTED classifications are preserved, never inferred from differing sponsors",
            "not_evidence_of_identity":"Generic condition, sponsor or outcome strings alone are never family proof"},
        "query_policy":{"normalization":"Unicode NFKC, casefold, whitespace collapse only",
            "semantic_inputs":["normalized measure text only"],"audit_only":["outcome type","time frame","owner NCT ID","source ID","description","evidence ID"],
            "positives":"All exact-normalized registered owners, not clinical-equivalence labels",
            "near_screen":"Punctuation-key groups plus adjacent lexically sorted strings, 30..800 chars, length ratio>=0.9 and SequenceMatcher>=0.95; non-exhaustive",
            "embargo":"Exact cross-partition query groups, cross-partition near candidates, or weak-family quarantine; no clinical equivalence inferred",
            "description_screen":"Exact normalized groups and bounded near screen (max 2000 chars); audit only because descriptions are not model inputs"},
        "graph_policy":{"regime":"Trial-disjoint supervision within an observed non-target graph; NOT unseen-trial inductive evaluation",
            "all_target_edges_masked":True,"target_type":TARGET,"computational_reverses_also_masked":True,
            "retained_message_edges":61218,"provenance_excluded_from_messages":True,"source_graph_unchanged":True,
            "heldout_trial_non_target_context_visible":True,"detached_measure_queries":True,"no_trainable_id_embeddings":True},
        "negative_policy":{"pool":"training trials only","exclude":["all known training owners of exact query","grouped owner families","training owners of screened near queries"],
            "sampling":"Future fixed-seed uniform/hard mixture must be declared before training; no negatives sampled in this stage",
            "caution":"Unlinked does not imply clinically irrelevant; no held-out truth is consulted by the loader"},
        "evaluation":{"candidate_count":2824,"candidate_order":"ascending NCT ID","tie_break":"descending score then ascending NCT ID",
            "metrics":["Recall@1","Recall@5","Recall@10","Hit@1","Hit@5","Hit@10","MRR","coverage","median latency","p95 latency"],
            "recall":"Known registered owners in top-k divided by all known owners; distinct from Hit@k",
            "aggregation":"query micro, owner-trial macro (within owner then equal trials), and family macro (within family then equal families); report single/multi-owner strata",
            "uncertainty":"Paired family-cluster bootstrap; 1000 replicates, fixed seed; identical sampled families for methods; not run",
            "latency":"separate query encoding and ranking; report one-time candidate preparation; no LLM/Neo4j time mixed into ranking",
            "baselines":["training-fitted TF-IDF","pinned MiniLM cosine","deterministic non-target neighbor pooling","untrained GraphSAGE","trained GraphSAGE"],
            "model_selection":"validation only, frozen test once; no model selection performed"},
        "limitations":["Full-cohort protocol/secondary identifiers unavailable in this extraction; family screen is not exhaustive.",
            "New automated family and near-query candidates are not human-reviewed clinical equivalences.",
            "Snapshot may include amendments; no original-registration or prospective clinical claims.",
            "Training-loader isolation is an API boundary, not operating-system access control.",
            "No embeddings, message passing, training or ranking evaluation performed."]}
    write_json(output/"protocol.json",policy)
    family_states={r['family_id']:r['family_status'] for r in families}
    audit={"trials":2824,"trials_with_outcomes":len(counts),"trials_without_outcomes":2824-len(counts),
        "positive_associations":len(associations),"distinct_normalized_queries":len(queries),
        "cross_trial_query_groups":sum(len(q['owner_trial_ids'])>1 for q in queries.values()),
        "cross_trial_query_source_records":sum(len(q['source_associations']) for q in queries.values() if len(q['owner_trial_ids'])>1),
        "family_pair_classifications":{status:sum(r['classification']==status for r in pairs)
            for status in ('CONFIRMED_RELATED','UNRESOLVED','REJECTED')},
        "family_pair_strengths":dict(Counter(r['strength'] for r in pairs)),
        "family_group_classifications":dict(Counter(family_states.values())),
        "largest_family":max(Counter(r['family_id'] for r in families).values()),
        "weak_family_quarantined_trials":sum(r['heldout_review_quarantine'] for r in families),
        "exact_cross_partition_query_groups":sum('EXACT_QUERY_CROSS_PARTITION' in e for e in reasons.values()),
        "near_query_candidates":len(near_records),"near_query_cross_partition_candidates":sum(r['cross_partition'] for r in near_records),
        "description_audit_rows":len(description_rows),"description_kinds":dict(Counter(r['kind'] for r in description_rows)),
        "split_counts":split_counts,"retained_message_edges":len(retained),"removed_target_message_edges":len(masks)-len(retained)}
    write_json(output/"source_audit.json",audit)
    files={str(p.relative_to(output)):extraction.sha256(p) for p in sorted(output.rglob('*')) if p.is_file()}
    write_json(output/"split_manifest.json",{"schema_version":VERSION,"status":STATE,"created_utc":None,
        "code_sha256":{Path(__file__).name:extraction.sha256(Path(__file__)),
            'association_training_data_v2.py':extraction.sha256(Path(__file__).with_name('association_training_data_v2.py'))},
        "seed":SEED,"target_ratios":RATIOS,
        "source_sha256":source_hashes,"files_sha256":files,"actual_counts":audit,"training_permitted":False})
    names=sorted([*files,'split_manifest.json'])
    (output/"SHA256SUMS").write_text(''.join(f"{extraction.sha256(output/name)}  {name}\n" for name in names),encoding='utf-8')
    validate_saved_protocol(output)
    return audit


def validate_saved_protocol(directory=DEFAULT_OUTPUT):
    directory=Path(directory)
    manifest=json.loads((directory/'split_manifest.json').read_text())
    require(manifest['schema_version']==VERSION and manifest['training_permitted'] is False,"Invalid protocol identity/readiness")
    for name,digest in manifest['files_sha256'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,"Unsafe artifact path")
        require(extraction.sha256(directory/name)==digest,'Protocol output checksum mismatch: '+name)
    for name,digest in manifest['source_sha256'].items():
        require(extraction.sha256(ROOT/name)==digest,'Protocol source checksum mismatch: '+name)
    listed={}
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split('  ')
        require(name not in listed and name in {*manifest['files_sha256'],'split_manifest.json'},'Invalid protocol checksum list')
        require(extraction.sha256(directory/name)==digest,'Protocol checksum-list mismatch: '+name)
        listed[name]=digest
    require(set(listed)=={*manifest['files_sha256'],'split_manifest.json'},'Incomplete protocol checksum list')
    rows=read_csv(directory/'trial_splits.csv');splits={r['nct_id']:r['split'] for r in rows}
    require(len(rows)==len(splits)==2824,"Split membership count mismatch")
    families=defaultdict(set)
    for r in rows:families[r['family_id']].add(r['split'])
    require(all(len(v)==1 for v in families.values()),"Family crosses partitions")
    positives=read_csv(directory/'positive_associations.csv')
    require(len(positives)==len({r['outcome_id'] for r in positives})==19740,"Positive audit count mismatch")
    require(all(splits[r['nct_id']]==r['split'] for r in positives),"Association crosses trial partition")
    all_truth=[];eligible_texts={}
    for split in RATIOS:
        truth=read_jsonl(directory/'truth'/(split+'.jsonl'))
        for q in truth:
            require(q['split']==split and all(splits[n]==split for n in q['owner_trial_ids']),"Truth owner partition mismatch")
            all_truth.extend(r['outcome_id'] for r in q['source_associations'])
            if q['eligible_for_novel_evaluation']:
                require(not q['exclusion_reasons'],"Embargoed query published for evaluation")
                eligible_texts[q['query_text']]=split
    require(len(all_truth)==len(set(all_truth))==19740,"Truth records missing or duplicated")
    catalog=read_jsonl(directory/'query_catalog.jsonl')
    for q in catalog:
        if q['query_text'] in eligible_texts:
            require({splits[n] for n in q['owner_trial_ids']}=={eligible_texts[q['query_text']]},"Evaluation query overlaps partitions")
    edges=read_csv(directory/'training/message_edges.csv')
    require(len(edges)==61218 and all(r['relationship_type'] not in {TARGET,*extraction.PROVENANCE_TYPES} for r in edges),"Target/provenance edge survived masking")
    mask=read_csv(directory/'message_edge_mask.csv')
    require(len(mask)==100698 and sum(r['retained']=='True' for r in mask)==61218,"Mask count mismatch")
    source_messages=read_csv(EXTRACTION/'message_edges_semantic.csv')
    require([r['message_edge_index'] for r in mask]==[r['message_edge_index'] for r in source_messages], 'Mask ordering/identity mismatch')
    for actual,original in zip(mask,source_messages):
        expected=original['relationship_type'] not in {TARGET,*extraction.PROVENANCE_TYPES}
        require(actual['retained']==str(expected) and all(actual[k]==original[k] for k in
            ('original_relationship_index','relationship_type','message_direction')), 'Incorrect target/reverse mask')
    require(edges==[r for r in source_messages if r['relationship_type'] not in {TARGET,*extraction.PROVENANCE_TYPES}], 'Masked context differs from pinned non-target edges')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--validate-only',action='store_true')
    args=parser.parse_args()
    try:
        result=(validate_saved_protocol(args.output_dir)['actual_counts'] if args.validate_only else prepare_protocol(args.output_dir))
    except (ProtocolError,OSError,ValueError) as exc:
        parser.exit(1,f'Protocol preparation failed; no fallback/overwrite: {exc}\n')
    print(json.dumps({'output_dir':str(args.output_dir),'status':STATE,'counts':result},indent=2))


if __name__=='__main__':main()
