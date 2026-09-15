# CadenceAI

CadenceAI is a multi-agent video production pipeline for turning a story idea into a structured world, script, storyboard, visual prompts, generated clips, and post-produced output.

## Project layout

- `agents/`: specialist agents and the production orchestrator
- `core/`: shared data models, API wrappers, and session utilities
- `docs/`: API and architecture notes
- `scripts/`: local media and animation helpers
- `tests/`: API and module tests
- `pipeline_output/`: generated intermediate results (large media is ignored)

## Configuration

API keys are intentionally not stored in this repository. Copy `.env.video.example` to a local environment file or export these variables in your shell:

- `ARK_LLM_API_KEY` or `VOLC_API_KEY`
- `ARK_VIDEO_API_KEY` or `ARK_API_KEY`
- `AUDIO_API_KEY` or `TTS_API_KEY`

The `.env` files are ignored by Git. Never commit real credentials. The example file contains placeholders only.

## Run

Use Python 3 and install the dependencies required by the agents and media helpers in your environment. The main entry point is:

```powershell
python run_complete_pipeline.py
```

The pipeline currently uses project-specific local paths for reference media and output. Adjust those paths in `run_complete_pipeline.py` for another machine.

## Security note

If a credential has ever been placed in a source file, test file, documentation file, or chat transcript, revoke it at the provider and create a replacement before running the pipeline again.
