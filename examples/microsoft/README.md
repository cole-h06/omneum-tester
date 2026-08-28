# Microsoft Agent Framework

This example integrates Omneum into a Microsoft Agent Framework agent.

It uses the enterprise workflow from `examples/enterprise` as its retrieval
scenario, then maps the retrieved results through `ContextMapper` before
evaluation. The Microsoft Agent Framework agent provides the orchestration.

## Flow

- Invoke the retrieval tool.
- Collect the retrieved observations.
- Submit the observations through the enterprise workflow's Omneum evaluation path.
- Generate the final response from the returned assertion evaluation.

## Requirements

- Python 3.10 or newer
- An `OPENAI_API_KEY`
- An `OPENAI_MODEL`

Install the Omneum wheel matching your Python version and platform from the
package root.

For example, on Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

Then install the required packages:

```bash
pip install agent-framework
```

Export your OpenAI credentials:

```bash
export OPENAI_API_KEY=<your-api-key>
export OPENAI_MODEL=gpt-5.5
```

Choose the Omneum wheel matching your Python version and operating system.

## Run

```bash
python -m examples.microsoft.run
```

## Files

- `agent.py` — Microsoft Agent Framework agent and Omneum tool definition
- `run.py` — entry point