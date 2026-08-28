# Omneum

Omneum is an open-source data trust gateway for agentic systems. It evaluates information returned by retrieval and tool execution before that information is included in the next model context.

Agent workflows routinely assemble context from search results, APIs, databases, internal services, documents, MCP tools, and earlier agent steps. Several results can appear to independently support the same information even when they ultimately came from one upstream source. Other branches may return conflicting values, stale copies, or provenance that was only partially preserved by the runtime.

Omneum evaluates that structure without adding another LLM call.

> **Tester package:** This repository contains prebuilt Omneum wheels, documentation, and examples for integrating Omneum into an existing agent application. You do not need the Omneum source repository.

## What Omneum does

- **Source dependency estimation:** Estimates whether supporting sources are independent using the provenance and structural information actually available to the application.

- **Conflict detection:** Surfaces competing structured values for the same entity and attribute.

- **Context-quality signals:** Returns support, estimated independent support, pairwise dependency, and signal coverage for use in agent control flow.

- **Privacy-preserving linkage:** Uses an RFC 9497 VOPRF to derive stable opaque identifiers without sending private source identifiers or structured linkage values to the server in plaintext.

One distinction matters throughout the dependency API: **missing information is not evidence of independence.**

If the runtime knows that two sources share an upstream origin but has no ownership or citation information, Omneum uses the upstream relationship and leaves the other signals unobserved. Integrations should not manufacture metadata just to fill the schema.

## Quickstart

This tester assumes a Python-based agent application.

### 1. Install Omneum

Create and activate a virtual environment:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
```

Install the wheel matching your Python version and platform.

For example, on an Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

If you pull an updated wheel with the same package version, force the reinstall:

```bash
pip install --force-reinstall ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

### 2. Initialize a local deployment

```bash
omneum init
```

This creates the deployment configuration and VOPRF key material used by the local server.

### 3. Connect to the MCP server

Omneum runs locally as an MCP server over `stdio`:

```python
from mcp import StdioServerParameters

from omneum import OmneumClientConfig, open_stdio_client

config = OmneumClientConfig.from_local_deployment()

server = StdioServerParameters(
    command="omneum-server",
)
```

The SDK loads the initialized deployment configuration when it opens the MCP connection.

## Evaluate a structured assertion

Use `StructuredAssertion` when the application already knows the structured assertion it wants evaluated.

```python
from datetime import datetime, timezone

from omneum import (
    AssertionSource,
    DependencyEstimatorConfig,
    Source,
    StructuredAssertion,
)

now = datetime.now(timezone.utc)

assertion = StructuredAssertion(
    entity_namespace="service",
    entity="payment_api",
    attribute="status_code",
    value=200,
    sources=(
        AssertionSource(
            source=Source(
                kind="web_document",
                identifier="https://research.example.com/payment-status",
            ),
            assertion_id="result-1",
            observed_at=now,
        ),
        AssertionSource(
            source=Source(
                kind="web_document",
                identifier="https://analytics.example.com/payment-status",
            ),
            assertion_id="result-2",
            observed_at=now,
        ),
    ),
)

estimator = DependencyEstimatorConfig()

async with open_stdio_client(config, server) as client:
    result = await client.evaluate(
        assertion,
        estimator=estimator,
    )
```

This is the high-level path. You do not need to construct `Observation`, `Claim`, `Retrieval`, or `SourceReference` objects unless you need the lower-level API.

The application remains responsible for semantic normalization. Omneum does not use an LLM to decide that two differently expressed results represent the same structured assertion.

## Map existing application data

Most integrations already have retrieval results, tool responses, connector records, Pydantic models, or workflow state. They should not need to rebuild those objects around Omneum.

`ContextMapper` tells Omneum where its canonical fields exist in the application's current data.

Suppose a retrieval step returns:

```python
results = [
    {
        "id": "result-1",
        "url": "https://research.example.com/payment-status",
        "entity": "payment_api",
        "status_code": 200,
    },
    {
        "id": "result-2",
        "url": "https://analytics.example.com/payment-status",
        "entity": "payment_api",
        "status_code": 200,
    },
]
```

Define the mapping:

```python
from omneum import ContextMapper, Source

mapper = ContextMapper(
    source=lambda result: Source(
        kind="web_document",
        identifier=result["url"],
    ),
    entity_namespace=lambda result: "service",
    entity="entity",
    attribute=lambda result: "status_code",
    value="status_code",
    assertion_id="id",
    observed_at=lambda result: now,
)
```

Then evaluate the mapped observations through the normal pipeline:

```python
async with open_stdio_client(config, server) as client:
    observations = mapper.map_many(results)

    result = await client.evaluate_assertion(
        observations,
        estimator=estimator,
    )
```

Required and optional field mappings can use field paths or callables. Concrete provenance such as upstream sources, citations, assertion lineage, source timestamps, and retrieval records can be mapped when the runtime has them.

If it doesn't have them, leave them unset.

`ContextMapper` also supports explicit dependency signals for integrations that already compute something matching Omneum's signal semantics. This is an escape hatch, not the normal way to pass raw application metadata.

See [`docs/context_mapper.md`](docs/context_mapper.md) for the complete mapping contract.

## Dependency estimation

Multiple retrieved results are not necessarily multiple independent sources.

For each source pair, Omneum can use available information about:

```text
upstream
citation
assertion_lineage
ownership
temporal
graph
retrieval
```

`DependencyEstimatorConfig` controls how those signals contribute to the estimate.

```python
from omneum import DependencyEstimatorConfig

estimator = DependencyEstimatorConfig()
```

Not every signal needs to exist for every pair.

For example, if upstream provenance is the only observable signal and it indicates complete dependency, Omneum can return:

```text
dependency                = 1.0
weighted_signal_coverage  = 0.25
```

The dependency estimate is normalized over the signals that were actually observable. Coverage is reported separately.

That distinction is deliberate. A low coverage value means the estimator had limited information; it does not turn an observed dependency relationship into apparent independence.

Likewise:

```python
DependencySignal(value=0.0, observable=True)
```

is different from a signal that was not observable at all. The former says the integration had information about that relationship and observed zero dependency on that axis. The latter says it did not have the information.

Pairwise dependency is then used to adjust raw source count into `estimated_independent_support_count`.

See [`docs/sdk.md`](docs/sdk.md#dependency-estimation) for estimator configuration and the full result model.

## Use the evaluation result

The high-level and mapped paths return an `AssertionEvaluation`.

```python
for claim in result.claim_support:
    print("Support:", claim.support)
    print(
        "Independent support:",
        claim.estimated_independent_support_count,
    )
    print("Conflicts:", claim.conflicting_claims)
```

These values are intended for agent control flow. An application can retrieve again when independent support is insufficient, branch when values conflict, or attach the evaluation to information passed downstream.

Omneum returns the signals. The application decides what to do with them.

## Where Omneum fits

```text
Search / Retrieval / Tool Execution
                ↓
       Existing Application Data
                ↓
     Application-Defined Normalization
                ↓
  StructuredAssertion / ContextMapper
                ↓
          Omneum Evaluation
                ↓
 Support / Dependency / Conflict Signals
                ↓
       Agent Control Flow
                ↓
        Next Model Context
```

Omneum does not replace the retrieval system, MCP client, tool runtime, or orchestration framework. It evaluates information those components have already surfaced.

## Lower-level observation API

`Observation` is Omneum's lower-level source-specific representation.

An observation associates a `Claim` with the source that produced it and can retain detailed provenance, retrieval metadata, source relationships, assertion lineage, and explicit dependency signals.

`client.evaluate_assertion()` accepts observations directly.

Most integrations shouldn't start here. Use it when you actually need control over the complete observation representation; otherwise use `StructuredAssertion` or `ContextMapper`.

All entry paths feed the same assertion-evaluation pipeline and return an `AssertionEvaluation`.

## Privacy

Omneum uses an RFC 9497 VOPRF with the `ristretto255-SHA512` ciphersuite to derive stable linkage tokens for private source and structured assertion data.

Canonicalization, serialization, VOPRF blinding, proof verification, finalization, and token encoding happen through the client SDK. Source identifiers and structured linkage values are not sent to the Omneum server in plaintext during token generation.

Matching inputs can therefore resolve to stable opaque identifiers within the same deployment, key version, linkage configuration, and purpose.

This is not general request encryption.

The server can still observe protocol traffic and relationships among opaque identifiers submitted for evaluation. The VOPRF protects the private values used to derive the tokens; it does not conceal the entire MCP request.

## Documentation

- [`docs/context_mapper.md`](docs/context_mapper.md) — `ContextMapper` fields, source identity, lineage semantics, retrievals, missing-data behavior, and explicit signals.
- [`docs/sdk.md`](docs/sdk.md) — SDK models, dependency-estimator configuration, evaluation results, and lower-level interfaces.
- [`docs/api.md`](docs/api.md) — MCP request and response schemas, validation behavior, server limits, and errors.
- [`docs/protocol.md`](docs/protocol.md) — MCP transport, deployment metadata, linkage flow, and VOPRF behavior.
- [`docs/canonicalization.md`](docs/canonicalization.md) — Canonical encodings used to construct deterministic linkage inputs.
- [`examples/`](examples/) — Framework-specific and end-to-end integrations.

## Status

Omneum is an early release. The SDK and integration surface may change as it gets exercised against real agent systems.

If an integration forces you to invent metadata you don't actually have, or makes provenance your runtime already tracks awkward to represent, that's useful feedback.

Issues and contributions are welcome.

## License

See [`LICENSE`](LICENSE).