# Local numerical evaluation

Use the prebuilt Omneum **1.0.3** wheel in your existing Python 3.11–3.14
environment. This adapter runs the production dependency estimator, graph
builder and BRAID inference engine locally. No daemon, initialization, root
access or Omneum rebuild is required.

| Path | What it evaluates |
|---|---|
| This adapter | Dependencies, source reliability, claim support and conflicts |
| SDK/MCP deployment | The numerical evaluation plus MCP transport, VOPRF verification and authenticated daemon interaction |

The adapter does not test MCP, VOPRF verification or daemon security boundaries.
Its local source/claim labels are not cryptographic linkage tokens.

## Add to an existing harness

Place `local_evaluation.py` beside your harness script, or run with the tester
repository on your Python import path. Immediately after your existing
`estimate_dependencies(sources, observations, estimator)` call, add:

```python
from local_evaluation import evaluate_and_report

evaluate_and_report(
    sources, observations, estimator,
    case_id="my-case",
    json_output="local-results.json",
)
```

Use the same three argument objects your estimator call already uses, whatever
your variable names are. Run your harness as usual. No input export is needed.
For multiple cases or repeated runs, use a fresh output filename for each call;
existing files are never overwritten. The output parent directory must exist.

The helper prints source reliability, claim support, supporting sources and
assertion IDs, estimated independent support, conflicting claims, dependency
coverage and evaluation latency. It saves detailed pairwise diagnostics and all
numerical results in the separate JSON file, and returns that report as a dict.
It repeats estimation with your original inputs; your existing result variables
remain untouched. Latency covers estimation, graph construction and inference,
not report rendering or file I/O.

The JSON includes the original mapped inputs and configuration. Treat it as
local evaluation data, not anonymized telemetry. Do not commit private reports.

## Try the included synthetic example

From this repository, with the 1.0.3 wheel installed:

```sh
python local_evaluation.py examples/local-evaluation-synthetic.json --json-output synthetic-local-results.json
```

The example covers independent agreement, shared upstream provenance, conflicts
and missing provenance. It is an adapter test fixture, not an external tester's
results. Scores describe the supplied graph; they are not truth probabilities.

## Input boundaries

- `sources` and `observations` must be the original tuples of Omneum `Source`
  and `Observation` objects; `estimator` must be your existing
  `DependencyEstimatorConfig`. The adapter supplies no default weights.
- Preserve each batch and its assertion lineage. Invalid graphs fail rather
  than being repaired. An empty batch is explicitly reported as not evaluated.
- Missing provenance stays unknown. Low dependency with missing signal coverage
  is not evidence of independence. Known empty collections stay distinct from
  missing collections.
- A conflict requires competing structured values for the same entity/attribute
  in the inputs. The adapter does not extract claims from text or conflict flags,
  reinterpret similarity as lineage, or enrich inputs from ground-truth labels.
- Numerical results and local labels are deterministic for identical inputs.
  Measured latency varies. This module supports package version 1.0.3 only.

For optional batch export, collect `Case(case_id, sources, observations,
estimator)` objects and JSON-serialize `export_cases(cases)` from this module.
Pass that exported file to the CLI in place of the example. Raw Recall wire
responses are not mapped input files and are not accepted.

## Validation

```sh
python -B -m unittest discover -s tests -p test_local_evaluation.py -v
```

All 15 adapter tests pass using the prebuilt macOS ARM64 CPython 3.13 wheel.
The wheel was extracted into an isolated import directory and used with existing
Python dependencies; Omneum was not rebuilt. All 16 supplied wheel hashes match
`PROVENANCE.json`. The estimator, graph, inference, canonicalization,
serialization, information-model and SDK-client Python implementations match
across those wheels after normalizing line endings. Other platform binaries
have not been executed for this adapter review.

Tests cover input preservation, source/claim identity, lineage, missing
provenance, dependency adjustment, conflicts, deterministic output, UTF-8 input,
version enforcement and both harness/CLI reporting. Genuine SDK/MCP numerical
parity remains unverified: no provisioned daemon was available. No mock daemon
or cryptographic bypass was used.
