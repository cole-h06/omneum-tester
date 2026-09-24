"""Local numerical evaluation of already-mapped observations with Omneum 1.0.3.

No Recall extraction, provenance enrichment, MCP, VOPRF, or daemon startup.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
import importlib.metadata
import json
from pathlib import Path
import sys
from time import perf_counter

from omneum.canonicalization import (
    canonicalize_attribute, canonicalize_entity, canonicalize_source,
    canonicalize_value,
)
from omneum.dependency import (
    DependencyEstimatorConfig, DependencySignal, estimate_dependencies,
)
from omneum.engine_graph import AssertionTriple, SourcePair, build_graph
from omneum.inference import infer
from omneum.information import Claim, Observation, Retrieval, Source, SourceReference
from omneum.serialization import serialize_attribute, serialize_claim, serialize_source

PATH_LABEL = "Local algorithm evaluation (no MCP, VOPRF verification, or daemon isolation)"


@dataclass(frozen=True)
class Case:
    case_id: str
    sources: tuple[Source, ...]
    observations: tuple[Observation, ...]
    estimator: DependencyEstimatorConfig


def json_value(value):
    """Lossless JSON representation of the supported mapped input objects."""
    if isinstance(value, Claim):
        return {"entity_namespace": value.entity_namespace, "entity": value.entity,
                "attribute": value.attribute, "value": value.value}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Observation):
        data = {f.name: json_value(getattr(value, f.name)) for f in fields(value)}
        data["dependency_signals"] = {
            key: {"encoding": "dependency_signal" if type(signal) is DependencySignal else "json",
                  "value": json_value(signal)}
            for key, signal in value.dependency_signals.items()
        }
        return data
    if is_dataclass(value):
        return {f.name: json_value(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def export_cases(cases):
    """Call from the existing harness after its mapping; no remapping occurs."""
    return {"schema_version": 1, "cases": [json_value(case) for case in cases]}


def _source_key(source):
    return serialize_source(source.kind, canonicalize_source(source.kind, source.identifier))


def _claim_keys(claim):
    attribute = (claim.entity_namespace,
                 canonicalize_entity(claim.entity_namespace, claim.entity),
                 canonicalize_attribute(claim.attribute))
    return (serialize_attribute(*attribute),
            serialize_claim(*attribute, canonicalize_value(claim.value)))


def _ids(keys, prefix):
    # Local labels only. They are neither cryptographic linkage nor anonymization.
    return {key: f"{prefix}{n:04d}" for n, key in enumerate(sorted(set(keys)), 1)}


def evaluate_case(case: Case):
    if importlib.metadata.version("omneum") != "1.0.3":
        raise ValueError("This adapter requires the prebuilt Omneum 1.0.3 package.")
    if type(case.case_id) is not str or not case.case_id:
        raise ValueError("case_id must be a nonempty string")
    if type(case.sources) is not tuple or type(case.observations) is not tuple:
        raise TypeError("sources and observations must be tuples")
    if type(case.estimator) is not DependencyEstimatorConfig:
        raise TypeError("estimator must be DependencyEstimatorConfig")
    started = perf_counter()
    if not case.observations and not case.sources:
        return {"case_id": case.case_id, "status": "not_evaluated",
                "reason": "No mapped observations; no numerical scores were produced.",
                "elapsed_ms": (perf_counter() - started) * 1000,
                "input": json_value(case)}

    # Original tuples/configuration enter the production estimator unchanged.
    pairs, clusters = estimate_dependencies(case.sources, case.observations, case.estimator)
    source_ids = _ids((_source_key(s) for s in case.sources), "s")
    rows = [(o, _source_key(o.source), *_claim_keys(o.claim)) for o in case.observations]
    attribute_ids = _ids((r[2] for r in rows), "a")
    claim_ids = _ids((r[3] for r in rows), "c")
    triples = tuple(AssertionTriple(source_ids[s], attribute_ids[a], claim_ids[c])
                    for _, s, a, c in rows)
    graph_pairs = []
    for pair in pairs:
        a, b = sorted((source_ids[_source_key(pair.source_a)],
                       source_ids[_source_key(pair.source_b)]))
        graph_pairs.append(SourcePair(a, b, pair.dependency, pair.weighted_signal_coverage))
    result = infer(build_graph(triples, tuple(graph_pairs)))
    elapsed_ms = (perf_counter() - started) * 1000
    return {
        "case_id": case.case_id, "status": "evaluated", "elapsed_ms": elapsed_ms,
        "input": json_value(case),
        "sources": {local: json.loads(key) for key, local in source_ids.items()},
        "attributes": {local: json.loads(key) for key, local in attribute_ids.items()},
        "claims": {local: json.loads(key) for key, local in claim_ids.items()},
        "assertions": sorted(({
            "assertion_id": o.assertion_id, "source_id": source_ids[s],
            "attribute_id": attribute_ids[a], "claim_id": claim_ids[c],
        } for o, s, a, c in rows), key=lambda r: r["assertion_id"]),
        "inference": json_value(result),
        "pairwise_dependencies": json_value(pairs),
        "dependency_clusters": json_value(clusters),
    }


def evaluate_cases(cases):
    cases = tuple(cases)
    if not cases:
        raise ValueError("At least one case is required")
    if len({c.case_id for c in cases}) != len(cases):
        raise ValueError("Duplicate case_id")
    return {"schema_version": 1, "execution_path": PATH_LABEL,
            "omneum_version": importlib.metadata.version("omneum"),
            "cases": [evaluate_case(c) for c in sorted(cases, key=lambda c: c.case_id)]}


def _write_report(report, json_output):
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    # Exclusive creation also protects the caller's corpus and prior reports.
    with Path(json_output).open("x", encoding="utf-8") as output:
        output.write(encoded)
    print(render_report(report))
    print(f"\nDetailed local JSON: {json_output}")


def evaluate_and_report(sources, observations, estimator, *, case_id, json_output):
    """Drop-in harness entry point using the existing estimator's exact inputs.

    Prints the concise report, creates a separate JSON report, and returns the
    report dictionary. Use a new output path for each case/run. Does not export
    inputs first, configure a daemon, or contact MCP.
    """
    report = evaluate_cases((Case(case_id, sources, observations, estimator),))
    _write_report(report, json_output)
    return report


def _text(value):
    # Escape terminal control characters in identifiers/values.
    return json.dumps(value, ensure_ascii=True, sort_keys=True, allow_nan=False)


def render_report(report, *, include_latency=True):
    lines = [PATH_LABEL, "Scores describe this supplied graph; they are not truth probabilities."]
    for case in report["cases"]:
        lines.extend(["", f"Case {_text(case['case_id'])}"])
        if case["status"] != "evaluated":
            lines.append(case["reason"])
            continue
        result = case["inference"]
        for source in result["source_reliability"]:
            sid = source["source_id"]
            label = case["sources"][sid]
            lines.append(f"  {sid} {label['kind']} {_text(label['identifier'])}: "
                         f"reliability {source['reliability']:.6f}")
        for support in result["claim_support"]:
            cid = support["claim_id"]
            claim = case["claims"][cid]
            sources = ", ".join(s["source_id"] for s in support["supporting_sources"])
            assertions = ", ".join(_text(r["assertion_id"]) for r in case["assertions"]
                                   if r["claim_id"] == cid)
            lines.append(f"  {cid} {_text(claim['entity'])}.{_text(claim['attribute'])} = {_text(claim['value'])}")
            lines.append(f"    support {support['support']:.6f}; sources {support['supporting_source_count']}; "
                         f"estimated independent support {support['estimated_independent_support_count']:.6f}")
            lines.append(f"    supporting: {sources}; assertions: {assertions}")
            conflicts = ", ".join(f"{c['claim_id']} ({c['support']:.6f})" for c in support["conflicting_claims"])
            lines.append(f"    conflicts: {conflicts or 'none'}")
        pairs = case["pairwise_dependencies"]
        if pairs:
            coverage = [p["weighted_signal_coverage"] for p in pairs]
            lines.append(f"  Dependencies: {len(pairs)} pairs; max {max(p['dependency'] for p in pairs):.6f}; "
                         f"coverage {min(coverage):.3f}..{max(coverage):.3f}; "
                         f"{sum(c == 0 for c in coverage)} pairs with no observed weighted signals")
            if min(coverage) < 1:
                lines.append("  Missing signals remain unknown; low dependency does not establish independence.")
        else:
            lines.append("  Dependencies: no source pairs (single source).")
        meta = result["metadata"]
        lines.append(f"  Converged: {meta['converged']}; iterations: {meta['iterations']}")
        if include_latency:
            lines.append(f"  Evaluation latency: {case['elapsed_ms']:.3f} ms (estimator + graph + inference)")
    return "\n".join(lines)


def _keys(obj, required, optional=()):
    if type(obj) is not dict or set(obj) - set(required) - set(optional) or set(required) - set(obj):
        raise ValueError(f"Expected fields {sorted(required)}; optional {sorted(optional)}")


def _nullable_tuple(value, convert):
    if value is None:
        return None
    if type(value) is not list:
        raise ValueError("Provenance collections must be arrays or null")
    return tuple(convert(v) for v in value)


def _observation(row):
    _keys(row, ("assertion_id", "source", "claim", "observed_at"),
          ("source_modified_at", "upstream_sources", "cited_sources", "parent_assertion_ids",
           "retrievals", "metadata", "dependency_signals"))
    data = dict(row)
    data["source"] = Source(**data["source"])
    data["claim"] = Claim(**data["claim"])
    data["observed_at"] = datetime.fromisoformat(data["observed_at"])
    if data.get("source_modified_at") is not None:
        data["source_modified_at"] = datetime.fromisoformat(data["source_modified_at"])
    for name in ("upstream_sources", "cited_sources"):
        data[name] = _nullable_tuple(data.get(name), lambda v: SourceReference(**v))
    data["parent_assertion_ids"] = _nullable_tuple(data.get("parent_assertion_ids"), lambda v: v)
    def retrieval(v):
        return Retrieval(**{**v, "retrieved_at": datetime.fromisoformat(v["retrieved_at"])})
    data["retrievals"] = _nullable_tuple(data.get("retrievals"), retrieval)
    def signal(v):
        _keys(v, ("encoding", "value"))
        if v["encoding"] == "dependency_signal":
            return DependencySignal(**v["value"])
        if v["encoding"] == "json":
            return v["value"]
        raise ValueError("Unknown dependency signal encoding")
    data["dependency_signals"] = {k: signal(v) for k, v in data.get("dependency_signals", {}).items()}
    return Observation(**data)


def load_cases(document):
    _keys(document, ("schema_version", "cases"))
    if type(document["schema_version"]) is not int or document["schema_version"] != 1:
        raise ValueError("Unsupported mapped-input schema version")
    if type(document["cases"]) is not list:
        raise ValueError("cases must be an array")
    result = []
    for row in document["cases"]:
        _keys(row, ("case_id", "sources", "observations", "estimator"))
        if type(row["sources"]) is not list or type(row["observations"]) is not list:
            raise ValueError("sources and observations must be arrays")
        result.append(Case(row["case_id"], tuple(Source(**v) for v in row["sources"]),
                           tuple(_observation(v) for v in row["observations"]),
                           DependencyEstimatorConfig(**row["estimator"])))
    return tuple(result)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=PATH_LABEL)
    parser.add_argument("input", type=Path, help="Mapped cases exported by the existing Recall harness, not raw wire JSON")
    parser.add_argument("--json-output", type=Path, default=Path("local-evaluation.json"))
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
        report = evaluate_cases(load_cases(document))
        _write_report(report, args.json_output)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.exit(1, f"Local evaluation failed: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
