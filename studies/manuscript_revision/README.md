# VAL revised manuscript and supplementary study

This package accompanies the revised formulation dated 11 November 2026.
The numerical runtime under `reference/` is the unchanged VAL Reference 0.1.0
core. This is a manuscript revision and experiment supplement, not a claim that
a new software release has been published.

The revised controller explicitly selects `shadow_policy="raw_interval"`.
The original 0.1.0 default remains the legacy interval. Adaptive thresholds
and adaptive quota controls receive the same external target signal.

## Contents

- `manuscript/`: revised Markdown source with numbered equations and manuscript template.
- `MAPA_DAS_CORRECOES.md`: structural and scientific changes explained in Portuguese.
- `experiments/`: reproducible revision benchmark, focused checks and report preparation.
- `results/`: 864-run records, six passing revision checks, plots and execution logs.
- `reference/`: unchanged 0.1.0 numerical core and its MIT attribution.

## Reproduce the experiment

Python 3.11 or newer; no external runtime dependency:

```bash
python experiments/check_revision.py -v
python experiments/revision_benchmark.py --output results/new_run.json
```

Choose a new output path; the script refuses to overwrite recorded results.
The recorded run used Python 3.12. Its elapsed time is not a benchmark of the
author's workstation. All input scores, vectors and episodic codes are synthetic.

To rebuild the figure and fill the manuscript from the recorded outputs,
install Matplotlib and run `python experiments/prepare_manuscript.py`.
DOCX conversion additionally uses Pandoc, python-docx and the included formatting
script. Editable equations are stored as native Word math; PDF is the visually
verified export of the revised document. References and interpretation require
human review before a journal submission.

New experiment and document-generation scripts are MIT licensed under the
included LICENSE. Original manuscript rights are not changed by that license.
