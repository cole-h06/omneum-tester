# OpenAI Agents SDK

This example integrates Omneum into an OpenAI Agents SDK workflow.

It uses the enterprise workflow from `examples/enterprise` as its retrieval
scenario, then maps the retrieved results through `ContextMapper` before
evaluation. The OpenAI Agents SDK provides the orchestration.

## Flow

- Invoke the retrieval tool.
- Collect the retrieved observations.
- Submit the observations to Omneum.
- Generate the final response from the returned assertion evaluation.

## Requirements

- Python 3.10 or newer
- An `OPENAI_API_KEY`

Install the Omneum wheel matching your Python version and platform from the
package root.

For example, on Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

Then install the OpenAI Agents SDK:

```bash
pip install openai-agents
```

Export your OpenAI API key:

```bash
export OPENAI_API_KEY=<your-api-key>
```

Choose the Omneum wheel matching your Python version and operating system.

## Run

```bash
python -m examples.openai_agents.run
```

## Files

- `agent.py` — agent and Omneum tool definition
- `run.py` — entry point