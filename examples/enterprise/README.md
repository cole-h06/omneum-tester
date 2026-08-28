# Enterprise

This example integrates Omneum into an enterprise AI application that retrieves information from multiple internal and external sources.

The application answers the question:

> May the EU Customer Support Copilot send unredacted customer-ticket content to
> the approved hosted model in production? What provider-retention and
> processing-region settings are required?

Five retrieval agents collect structured observations from enterprise systems such as governance documents, deployment records, live configuration, generated reports, and vendor documentation.

This workflow intentionally uses Omneum's lower-level `client.evaluate_assertion()` interface, supplying `Observation` objects directly. Applications that already normalize information into `StructuredAssertion` objects can instead use `client.evaluate()`. Existing retrieval or tool outputs can be adapted through `client.evaluate_mapped()` and a `ContextMapper`.

Omneum evaluates:

- Which claims are most strongly supported
- Where retrieved information conflicts
- Which sources appear dependent
- Source reliability and claim support

For reproducibility purposes, the retrieval agents are simulated with simple Python functions. They do not call an LLM or access the network.

## Requirements

Install the Omneum wheel for your platform from the package root.

For example, on Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

Choose the wheel matching your Python version and operating system.

## Run

```bash
python -m examples.enterprise.workflow.run
```

This example creates a temporary local stdio deployment using a deterministic, example-only VOPRF key. The temporary key is removed when the workflow exits and must never be used in production.

## Output

Representative output:

```text
Application conclusion
Customer content must be redacted.
Provider retention must be 0 days.
Processing must remain in the EU.
The stale deployment runbook and recent readiness brief disagree with these controls.
The readiness brief is derived from the stale runbook and is not an independent source.
Vendor documentation confirms only:
• Provider retention
• Processing region

Source reliability

AI data-governance policy
Reliability: 0.27

AI gateway
Reliability: 0.27

Copilot readiness brief
Reliability: 0.00

Model registry
Reliability: 0.27

Stale deployment runbook
Reliability: 0.00

Vendor enterprise data controls
Reliability: 0.18

Claims

Claim: Input data policy = redacted customer content only
Support: 0.10
Agreement weight: 0.60
Supporting sources: 3
Estimated independent support: 1.65
Source-dependency confidence: 1.00
Conflicting value: unredacted customer content allowed

Explanation:
3 sources support this claim, with an estimated 1.65 independent sources. The available dependency signals indicate that some supporting sources are related. 1 conflicting value was identified for the same attribute.

Claim: Processing region = EU
Support: 0.19
Agreement weight: 0.67
Supporting sources: 4
Estimated independent support: 2.40
Source-dependency confidence: 1.00
Conflicting value: US

Explanation:
4 sources support this claim, with an estimated 2.40 independent sources. The available dependency signals indicate that some supporting sources are related. 1 conflicting value was identified for the same attribute.

Claim: Provider retention = 0 days
Support: 0.19
Agreement weight: 0.67
Supporting sources: 4
Estimated independent support: 2.40
Source-dependency confidence: 1.00
Conflicting value: 30 days

Explanation:
4 sources support this claim, with an estimated 2.40 independent sources. The available dependency signals indicate that some supporting sources are related. 1 conflicting value was identified for the same attribute.

Pair dependencies

AI data-governance policy ↔ Model registry

Independence: 0.46

• Direct citation
• 3 derived assertions
• Updated 23 hours apart
• 3 matching claims

Stale deployment runbook ↔ Copilot readiness brief

Independence: 0.42

• Direct citation
• 3 derived assertions
• Same owner
• 3 matching claims

## Related examples

The enterprise workflow is reused by the framework integrations.

- `examples/langgraph`
- `examples/crewai`
- `examples/llamaindex`
- `examples/microsoft`
- `examples/openai_agents`