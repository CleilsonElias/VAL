# Release procedure

This directory is the VAL 0.2.0 research reference. Before a release, run:

```bash
python -m pip install -e .
python tools/validate.py
python studies/manuscript_revision/experiments/check_revision.py -v
python tools/verify_frozen_study.py
```

Inspect the changed files and CI results before tagging a new version. Preserve
recorded historical data and the frozen manuscript study. Never rewrite an old
tag to make it point to a correction. The 0.1.0 ZIP predates GitHub publication.

The public description must retain the experimental scope, external context
signal, synthetic inputs, stronger quota controls and explicit LoRA/REM status.
Do not describe the code as a consciousness measure or a reproduced LLM safety
guarantee. A DOI is included only after an actual registration.
