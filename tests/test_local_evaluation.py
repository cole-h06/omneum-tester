from dataclasses import replace
from contextlib import redirect_stdout
from datetime import datetime, timezone
import json
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import local_evaluation as adapter
from omneum.dependency import DependencyEstimatorConfig, DependencySignal, estimate_dependencies
from omneum.engine_graph import AssertionTriple, SourcePair, build_graph
from omneum.inference import infer
from omneum.information import Claim, Observation, Retrieval, Source, SourceReference


def fixture(*, shared=False, conflict=False, missing=False):
    sources = tuple(Source("web_document", f"https://synthetic.invalid/{n}") for n in range(3))
    config = DependencyEstimatorConfig(
        upstream_weight=1.0, citation_weight=0.0, assertion_lineage_weight=0.0,
        ownership_weight=0.0, temporal_weight=0.0, graph_weight=0.0,
        temporal_window_seconds=3600.0,
    )
    observations = tuple(Observation(
        assertion_id=f"assertion-{n}", source=source,
        claim=Claim("service", "synthetic", "status", "paused" if conflict and n == 2 else "ready"),
        observed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        upstream_sources=None if missing else (SourceReference(
            "web_document", "https://root.invalid/shared" if shared else f"https://root.invalid/{n}"),),
    ) for n, source in enumerate(sources))
    return adapter.Case("synthetic-smoke", sources, observations, config)


class LocalEvaluationTests(unittest.TestCase):
    def test_rejects_other_package_versions(self):
        with patch.object(adapter.importlib.metadata, "version", return_value="1.0.4"):
            with self.assertRaisesRegex(ValueError, "1.0.3"):
                adapter.evaluate_case(fixture())

    def test_internal_sources_and_multiple_attributes_keep_identity(self):
        case = fixture()
        sources = tuple(Source("internal_resource",
            f"v1:11111111-1111-4111-8111-111111111111:22222222-2222-4222-8222-{n+1:012d}")
            for n in range(3))
        observations = tuple(replace(o, source=s, upstream_sources=None)
                             for o, s in zip(case.observations, sources))
        # The same JSON value on a different attribute must be a different claim.
        observations += (replace(observations[0], assertion_id="other-attribute",
                                 claim=Claim("service", "synthetic", "backup_status", "ready")),)
        result = adapter.evaluate_case(replace(case, sources=sources, observations=observations))
        self.assertEqual(result["inference"]["summary"],
                         {"source_count": 3, "claim_count": 2, "assertion_count": 4})
        self.assertEqual({s["identifier"] for s in result["sources"].values()},
                         {s.identifier for s in sources})
        support = {result["claims"][c["claim_id"]]["attribute"]: c
                   for c in result["inference"]["claim_support"]}
        self.assertEqual(support["status"]["supporting_source_count"], 3)
        self.assertEqual(support["backup_status"]["supporting_source_count"], 1)
        self.assertTrue(all(not c["conflicting_claims"] for c in support.values()))

    def test_utf8_cli_and_safe_human_labels(self):
        case = fixture()
        case = replace(case, observations=tuple(replace(o,
            claim=Claim("service", "caf\u00e9", "status\x1b[31m", "pr\u00eat")) for o in case.observations))
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.json", Path(directory) / "output.json"
            source.write_text(json.dumps(adapter.export_cases([case]), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", adapter.__file__, str(source),
                                     "--json-output", str(output)], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("\x1b", result.stdout)
            claims = json.loads(output.read_text(encoding="utf-8"))["cases"][0]["claims"]
            self.assertEqual(next(iter(claims.values()))["entity"], "caf\u00e9")
            self.assertEqual(next(iter(claims.values()))["value"], "pr\u00eat")

    def test_minimal_harness_integration(self):
        case = fixture(conflict=True)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.json"
            text = io.StringIO()
            with patch.object(adapter, "estimate_dependencies", wraps=estimate_dependencies) as estimator:
                with redirect_stdout(text):
                    report = adapter.evaluate_and_report(
                        case.sources, case.observations, case.estimator,
                        case_id=case.case_id, json_output=output)
            args = estimator.call_args.args
            self.assertIs(args[0], case.sources)
            self.assertIs(args[1], case.observations)
            self.assertIs(args[2], case.estimator)
            self.assertEqual(json.loads(output.read_text()), report)
            for label in ("reliability", "support", "estimated independent support", "conflicts"):
                self.assertIn(label, text.getvalue())
            before = output.read_bytes()
            with self.assertRaises(FileExistsError):
                adapter.evaluate_and_report(case.sources, case.observations, case.estimator,
                                            case_id=case.case_id, json_output=output)
            self.assertEqual(output.read_bytes(), before)

    def test_original_mapping_and_configuration_reach_estimator(self):
        case = fixture()
        original = case.observations[1]
        enriched = replace(original, parent_assertion_ids=("assertion-0",),
                           metadata={"related_via": ["assertion-2"], "weak_result": True},
                           retrievals=(Retrieval("r1", "search", "resource", original.observed_at,
                                                 {"score": 163.934}),),
                           dependency_signals={"retrieval": DependencySignal(0.4, True)})
        case = replace(case, observations=(case.observations[0], enriched, case.observations[2]))
        before = adapter.export_cases([case])
        with patch.object(adapter, "estimate_dependencies", wraps=estimate_dependencies) as estimator:
            result = adapter.evaluate_case(case)
        args = estimator.call_args.args
        self.assertIs(args[0], case.sources)
        self.assertIs(args[1], case.observations)
        self.assertIs(args[2], case.estimator)
        self.assertEqual(adapter.export_cases([case]), before)
        self.assertEqual(result["input"]["observations"][1]["parent_assertion_ids"], ["assertion-0"])

    def test_json_roundtrip_preserves_missing_empty_and_lineage(self):
        case = fixture(missing=True)
        rows = list(case.observations)
        rows[0] = replace(rows[0], upstream_sources=(), cited_sources=(), retrievals=(),
                          parent_assertion_ids=(), metadata={"score": 164.0})
        rows[1] = replace(rows[1], parent_assertion_ids=(rows[0].assertion_id,),
                          dependency_signals={"retrieval": DependencySignal(0.3, False),
                                              "raw": {"value": 0.4, "observable": False}})
        case = replace(case, observations=tuple(rows))
        doc = adapter.export_cases([case])
        loaded, = adapter.load_cases(json.loads(json.dumps(doc)))
        self.assertEqual(loaded, case)
        self.assertIsNone(loaded.observations[2].upstream_sources)
        self.assertEqual(loaded.observations[0].upstream_sources, ())

    def test_dependency_adjustment_uses_production_result(self):
        independent = adapter.evaluate_case(fixture())["inference"]["claim_support"][0]
        shared_case = fixture(shared=True)
        dependent = adapter.evaluate_case(shared_case)["inference"]["claim_support"][0]
        self.assertEqual(independent["supporting_source_count"], 3)
        self.assertAlmostEqual(independent["estimated_independent_support_count"], 3.0)
        self.assertAlmostEqual(dependent["estimated_independent_support_count"], 1.0)
        self.assertLess(dependent["support"], independent["support"])
        # Independent construction from the original estimator output checks the
        # adapter's wiring, not transport/cryptographic parity.
        pairs, _ = estimate_dependencies(shared_case.sources, shared_case.observations, shared_case.estimator)
        sid = {s.identifier: str(n) for n, s in enumerate(shared_case.sources)}
        graph = build_graph(tuple(AssertionTriple(str(n), "a", "c") for n in range(3)),
                            tuple(SourcePair(sid[p.source_a.identifier], sid[p.source_b.identifier],
                                             p.dependency, p.weighted_signal_coverage) for p in pairs))
        self.assertAlmostEqual(dependent["support"], infer(graph).claim_support[0].support)

    def test_conflicts_are_engine_results(self):
        result = adapter.evaluate_case(fixture(conflict=True))
        support = result["inference"]["claim_support"]
        self.assertEqual(len(support), 2)
        for claim in support:
            self.assertEqual(len(claim["conflicting_claims"]), 1)
            self.assertNotEqual(claim["claim_id"], claim["conflicting_claims"][0]["claim_id"])
        text = adapter.render_report({"cases": [result]})
        self.assertIn('"paused"', text)
        self.assertIn('"ready"', text)
        self.assertIn('assertion-2', text)

    def test_missing_provenance_does_not_become_known_independence(self):
        result = adapter.evaluate_case(fixture(missing=True))
        for pair in result["pairwise_dependencies"]:
            self.assertEqual(pair["weighted_signal_coverage"], 0.0)
            self.assertFalse(pair["signals"]["upstream_observable"])
        self.assertIn("remain unknown", adapter.render_report({"cases": [result]}))

    def test_canonicalization_matches_production_identity(self):
        case = fixture()
        rows = tuple(replace(o, source=Source("web_document", o.source.identifier.replace("https", "HTTPS")),
                             claim=Claim("service", " SYNTHETIC ", " Status ", " ready "))
                     for o in case.observations)
        expected = adapter.evaluate_case(case)
        actual = adapter.evaluate_case(replace(case, observations=rows))
        for key in ("sources", "claims", "attributes", "assertions", "inference"):
            self.assertEqual(actual[key], expected[key])

    def test_invalid_mapping_fails_without_repair(self):
        case = fixture()
        with self.assertRaises(ValueError):
            adapter.evaluate_case(replace(case, observations=case.observations + (case.observations[0],)))
        with self.assertRaises(ValueError):
            adapter.evaluate_case(replace(case, observations=(replace(case.observations[0],
                parent_assertion_ids=("unavailable-parent",)), *case.observations[1:])))

    def test_deterministic_numerics_and_rendering(self):
        case = fixture(conflict=True)
        left, right = adapter.evaluate_case(case), adapter.evaluate_case(case)
        left.pop("elapsed_ms")
        right.pop("elapsed_ms")
        self.assertEqual(left, right)
        reversed_result = adapter.evaluate_case(replace(case, sources=case.sources[::-1],
                                                        observations=case.observations[::-1]))
        for key in ("sources", "claims", "assertions", "inference", "pairwise_dependencies"):
            self.assertEqual(left[key], reversed_result[key])
        self.assertEqual(adapter.render_report({"cases": [left]}, include_latency=False),
                         adapter.render_report({"cases": [right]}, include_latency=False))

    def test_empty_case_is_explicitly_not_evaluated(self):
        case = replace(fixture(), sources=(), observations=())
        result = adapter.evaluate_case(case)
        self.assertEqual(result["status"], "not_evaluated")
        self.assertNotIn("inference", result)

    def test_raw_recall_and_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            adapter.load_cases({"request": {}, "response": {"hits": []}})
        with self.assertRaises(ValueError):
            json.loads('{"schema_version":1,"schema_version":2}', object_pairs_hook=adapter._unique_object)

    def test_cli_with_prebuilt_wheel_and_no_daemon(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "mapped.json"
            output = Path(directory) / "report.json"
            source.write_text(json.dumps(adapter.export_cases([fixture(conflict=True)])))
            command = [sys.executable, "-B", adapter.__file__, str(source), "--json-output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text())
            self.assertEqual(report["omneum_version"], "1.0.3")
            self.assertIn("no MCP, VOPRF verification, or daemon isolation", result.stdout)
            self.assertNotIn("pairwise_dependencies", result.stdout)
            self.assertIn("pairwise_dependencies", report["cases"][0])
            # An accidental rerun cannot overwrite a previous report.
            before = output.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
