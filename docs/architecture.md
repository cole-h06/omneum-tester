# Omneum Architecture

This document describes the architecture of the Omneum assertion-evaluation system and the boundary between an integrating application, the Python SDK, and the Omneum server.

## 1. Architectural Boundary

Omneum sits between information-producing parts of an agent workflow and the point where that information is consumed downstream.

A typical flow is:

```text
Retrieval / Tools / Workflow State
              ↓
       Application Data
              ↓
Semantic Normalization + Provenance Mapping
              ↓
   Omneum Python SDK
              ↓
    Dependency Estimation
              ↓
 Privacy-Preserving Linkage
              ↓
      Omneum MCP Server
              ↓
      Evaluation Result
              ↓
      Agent Control Flow
```

The application remains responsible for deciding what information represents the same structured assertion.

Omneum handles the evaluation after that boundary has been established.

Provenance is allowed to be partial. If the runtime has provenance information, it can supply it. If it does not, the field remains unavailable.

Missing provenance is not treated as observed independence.

## 2. Application Integration

Applications can enter the evaluation pipeline through either `StructuredAssertion` or `ContextMapper`.

### Structured assertions

`StructuredAssertion` is the direct path when the application already has a normalized assertion and its supporting sources.

The application provides a structured identity of the form:

```text
(entity_namespace, entity, attribute) → value
```

along with the sources that surfaced that value.

### Existing runtime data

`ContextMapper` is the adapter path for applications that already have retrieval results, tool responses, connector records, models, or workflow state in their own schemas.

The mapper identifies where Omneum's canonical fields exist in those objects.

```text
Application Record
       ↓
 ContextMapper
       ↓
Canonical Assertion + Provenance Fields
```

The application does not need to reconstruct its runtime objects around Omneum.

Concrete provenance should be mapped into the corresponding canonical fields when it exists. Examples include upstream source relationships, citations, assertion lineage, source modification timestamps, and retrieval records.

If the runtime does not have a field, leave it unset.

Do not manufacture provenance to fill the schema.

Arbitrary application metadata can be retained separately. It does not automatically participate in dependency estimation.

The complete mapping contract is documented in [`context_mapper.md`](context_mapper.md).

## 3. Client-Side Evaluation Preparation

Before an assertion evaluation is sent to the server, the Python SDK prepares the information needed by the evaluation protocol.

At a high level:

```text
StructuredAssertion / ContextMapper
              ↓
      Canonical Observations
              ↓
 Dependency Signal Derivation
              ↓
Pairwise Dependency Estimation
              ↓
       Linkage Encoding
              ↓
          VOPRF
              ↓
   Evaluation Request
```

These stages happen behind the high-level SDK interfaces.

### Semantic normalization

Semantic normalization belongs to the application.

Omneum does not use an LLM to decide that two differently expressed pieces of retrieved information represent the same entity, attribute, and value.

The SDK operates on the structured representation supplied by the integration.

### Canonical representation

The SDK converts application-facing inputs into Omneum's internal observation representation.

An observation associates a structured claim with the source that produced it and can retain provenance needed for dependency estimation.

Canonicalization also provides deterministic byte representations for values that participate in privacy-preserving linkage.

Canonical encoding rules are documented in [`canonicalization.md`](canonicalization.md).

## 4. Source Dependency Estimation

Source dependency is estimated on the client before the assertion evaluation request is constructed.

The estimator operates on provenance and structural information available in the current evaluation.

Canonical dependency signals are:

```text
upstream
citation
assertion_lineage
ownership
temporal
graph
retrieval
```

Concrete provenance is preferred over application-generated dependency scores. The SDK derives the corresponding signals when the required information is available.

Integrations that already compute a value matching one of Omneum's canonical signal semantics can provide an explicit `DependencySignal`, but this is an advanced path rather than the normal integration boundary.

### Observable and unavailable signals

A signal can be observable or unavailable.

These are different states:

```python
DependencySignal(value=0.0, observable=True)
DependencySignal(value=0.0, observable=False)
```

The first means the relevant information was available and indicated no dependency on that axis.

The second means the information needed to evaluate that signal was unavailable.

The estimator does not convert unavailable signals into observed zeroes.

### Pairwise dependency

For each source pair, the estimator combines the signals that were actually observable.

Dependency is normalized over those observable signals rather than over the entire configured signal set.

Signal coverage is retained separately.

Conceptually:

```text
observable provenance
        ↓
dependency signals
        ↓
pairwise dependency
        +
weighted signal coverage
```

This allows the system to distinguish an observed dependency relationship from how much information was available to estimate it.

For example, if upstream provenance is the only observable signal and establishes complete dependency, the dependency estimate can be `1.0` even when weighted signal coverage is substantially lower.

Coverage is not a probability that the dependency estimate is correct.

### Evaluation boundary

The application provenance used to derive dependency remains on the client.

The server-side assertion evaluation receives the numeric source-pair information required by the evaluation rather than the raw provenance used to derive it.

This keeps runtime-specific provenance outside the server evaluation boundary.

## 5. Privacy-Preserving Linkage

Omneum needs stable identifiers for matching private source and structured assertion data across an evaluation without sending those values to the server in plaintext.

The SDK uses an RFC 9497 VOPRF with the `ristretto255-SHA512` ciphersuite for this linkage.

The flow is:

```text
Private Application Value
          ↓
 Canonicalize + Serialize
          ↓
       Blind Locally
          ↓
  VOPRF Server Evaluation
          ↓
   Verify Proof Locally
          ↓
   Unblind + Finalize
          ↓
      Linkage Token
```

The client blinds each encoded input before sending it to the server.

The server evaluates the blinded element using its VOPRF private key and returns the evaluated element together with a proof.

The client verifies the proof and finalizes the result locally.

Matching encoded inputs under the same linkage configuration resolve to stable opaque identifiers.

The VOPRF is used for linkage privacy. It is not general request encryption.

The server can still observe protocol traffic and relationships among opaque identifiers submitted during evaluation.

Protocol details are documented in [`protocol.md`](protocol.md).

## 6. Evaluation Graph

Assertion evaluation operates on a bipartite graph.

Sources and claims are nodes. Assertions form edges between a source and the claim it supports.

```text
Source A ─────┐
              ├── Claim X
Source B ─────┘

Source C ───────── Claim Y
```

Source dependency modifies how much apparently separate support should be treated as independent.

Two sources can therefore support the same claim while contributing less than two fully independent units of support.

The graph is constructed for the current evaluation from the opaque source and claim identifiers produced by the linkage process together with the numeric evaluation inputs supplied by the client.

The server does not need the plaintext source identifiers or structured values to construct this graph.

## 7. Evaluation

The server performs assertion evaluation over the request-scoped graph.

The evaluation produces structured results that can include:

- claim support;
- estimated independent support;
- conflicting claims;
- pairwise source dependency and associated coverage.

`support` is a graph-derived score. It is not a probability that a claim is correct.

`estimated_independent_support_count` adjusts raw supporting-source count according to estimated dependency among those sources.

Conflicting structured values remain separate claims rather than being collapsed into one value.

The server returns these values to the SDK as structured evaluation data.

Routing decisions remain outside Omneum. An application can retrieve again, branch to another check, reject disputed context, or apply its own policy before the next model call.

## 8. Client and Server Responsibilities

The client SDK is responsible for application-facing evaluation preparation.

This includes:

- adapting structured assertions or mapped runtime data;
- preserving canonical provenance fields;
- deriving available dependency signals;
- estimating pairwise source dependency;
- canonicalizing linkage inputs;
- performing VOPRF blinding, proof verification, and finalization;
- constructing validated evaluation requests;
- decoding structured evaluation responses.

The server is responsible for the deployment-side protocol and evaluation boundary.

This includes:

- serving the MCP interface;
- evaluating blinded VOPRF inputs with the deployment key;
- validating assertion-evaluation requests;
- constructing the request-scoped evaluation graph;
- running assertion evaluation;
- returning structured results.

The split is intentional. Private application data and detailed runtime provenance do not need to become server-side application state for the evaluation to work.

## 9. Deployment Model

A local Omneum deployment is initialized with:

```bash
omneum init
```

The deployment contains configuration and VOPRF key material.

```text
config.toml
keys/
└── voprf.key
```

The non-secret deployment configuration is stored separately from the VOPRF private key.

The private key must not be committed to source control.

For the current local deployment model, the Python SDK connects to the Omneum MCP server over `stdio`.

```text
Agent Application
       │
       │ Python SDK
       ▼
  MCP stdio transport
       │
       ▼
  Omneum Server
```

Remote transport is not currently part of the Python SDK surface.

## 10. State Model

Assertion evaluation is request-scoped.

The server receives the inputs required for an evaluation, constructs the graph for that request, runs the evaluation, and returns the result.

The current open-source server does not require a persistent application database for this flow.

Persistent organizations, workspaces, agents, historical evaluation state, and other control-plane data belong to a hosted deployment model rather than the local MCP evaluation path.

VOPRF key material is deployment state and persists independently of individual assertion evaluations.

## 11. Trust Boundary

The primary trust boundary is between the application-side SDK and the Omneum server.

The client retains:

- raw source identifiers;
- structured entity, attribute, and value data;
- source provenance and retrieval records;
- application metadata;
- semantic normalization logic;
- local VOPRF blinding and finalization state.

The server receives what it needs to perform the protocol:

- blinded VOPRF inputs during linkage;
- opaque linkage identifiers during assertion evaluation;
- numeric source-pair dependency data required by the evaluation;
- protocol and deployment metadata.

The VOPRF prevents the server from learning the private values used to derive linkage tokens directly from the VOPRF exchange.

It does not conceal all request structure. The server can observe opaque identifiers and relationships submitted during an evaluation.

This boundary should be kept in mind when adding new protocol fields: application provenance should not cross it merely because it is convenient for the server implementation.

## 12. Design Constraints

The current architecture deliberately keeps several responsibilities outside Omneum.

The application owns semantic normalization and routing policy.

The SDK owns adaptation, dependency estimation, and privacy-preserving linkage.

The server owns the request-scoped graph evaluation and VOPRF server operation.

The system does not require complete provenance. Partial provenance is expected, and unavailable signals remain unavailable.

The local MCP server does not depend on the hosted Omneum database or control plane.

These boundaries may evolve as hosted deployments and additional SDKs are introduced, but changes should preserve the distinction between application data, client-side evaluation preparation, and server-side evaluation.
