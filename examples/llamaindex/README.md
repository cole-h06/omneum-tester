# LlamaIndex

This example integrates Omneum into a LlamaIndex Workflow.

It uses the enterprise workflow from `examples/enterprise` as its retrieval
scenario, then maps the retrieved results through `ContextMapper` before
evaluation. The LlamaIndex Workflow provides the orchestration.

## Flow

- Execute the retrieval workflow.
- Collect the retrieved observations.
- Submit the observations through the enterprise workflow's Omneum evaluation path.
- Generate the final response from the returned assertion evaluation.

## Requirements

Install the Omneum wheel matching your Python version and platform from the package root.

For example, on Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

Then install LlamaIndex:

```bash
pip install llamaindex
```

Choose the Omneum wheel matching your Python version and operating system.

## Run

```bash
python -m examples.llamaindex.run
```

## Files

- `workflow.py` — LlamaIndex Workflow definition
- `run.py` — entry point