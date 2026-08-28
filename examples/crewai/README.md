# CrewAI

This example integrates Omneum into a CrewAI Flow.

It reuses the enterprise workflow from `examples/enterprise`. Only the
orchestration changes.

## Flow

- Execute the retrieval steps in parallel.
- Merge the retrieved observations.
- Submit the observations to Omneum.
- Generate the final response from the assertion evaluation.

## Requirements

CrewAI supports Python 3.10–3.13 for this example.

Install the Omneum wheel matching your Python version and platform from the package root.

For example, on Apple Silicon with Python 3.13:

```bash
pip install ./omneum-1.0.0-cp313-cp313-macosx_11_0_arm64.whl
```

Then install CrewAI:

```bash
pip install crewai
```

Choose the Omneum wheel matching your Python version and operating system.

## Run

From the package root:

```bash
python -m examples.crewai.run
```

## Files

- `flow.py` — CrewAI Flow definition
- `state.py` — shared workflow state
- `run.py` — entry point
