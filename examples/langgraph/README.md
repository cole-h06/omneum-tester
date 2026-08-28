# LangGraph

This example integrates Omneum into a LangGraph workflow.

It uses the enterprise workflow from `examples/enterprise` as its retrieval
scenario, then maps the retrieved results through `ContextMapper` before
evaluation. The LangGraph graph provides the orchestration.

## Flow

- Execute the retrieval nodes in parallel.
- Merge the retrieved observations.
- Submit the observations through the enterprise workflow's Omneum evaluation path.
- Generate the final response from the assertion evaluation.

## Requirements

Install the Omneum wheel matching your Python version and platform from the package root.

For example, on Apple Silicon with Python 3.14:

```bash
pip install ./omneum-1.0.0-cp314-cp314-macosx_11_0_arm64.whl
```

Then install LangGraph:

```bash
pip install langgraph
```

Choose the Omneum wheel matching your Python version and operating system.

## Run

```bash
python -m examples.langgraph.run
```

## Files

- `graph.py` — graph definition
- `nodes.py` — retrieval and Omneum nodes
- `state.py` — shared graph state
- `run.py` — entry point
