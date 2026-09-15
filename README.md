# Sandboxed Recursive Self-Improvement Prototype

This is an **offline, disposable research prototype**.  It repeatedly improves a
small, serializable search-policy program on a fixed numerical-optimization
benchmark.  It is deliberately not an agent with access to a shell, files beyond
its run directory, credentials, a network, deployment APIs, or arbitrary code
execution.

The original JSON-policy experiment remains below for comparison. The stronger
source-level experiment is implemented in `source_rsi/`; its architecture,
containment model, definitions, and run instructions are in
`source_rsi/README.md`, with `run_source_rsi.py` as its entry point.

## Precise definition used here

For this experiment, *recursive self-improvement (RSI)* means an iterative
process in which a system:

1. represents the algorithm it currently uses as a mutable program artifact;
2. produces proposed modifications to that artifact using information from prior
   evaluations;
3. independently evaluates each proposal against a predeclared objective;
4. makes a proposal the new parent only when it beats the incumbent on an
   isolated validation suite; and
5. uses the selected parent to generate the next generation.

The recursion is over the **search policy**, not the generator or evaluator.
The term is justified only in this narrow operational sense: subsequent changes
are conditioned on and can replace the program that performs the benchmark
search.  It is not evidence of open-ended self-improvement, self-awareness,
agency, or AGI.

## What this is—and is not

| Category | Present? | Why |
| --- | --- | --- |
| Ordinary automated optimization | Yes | It tunes a bounded program against a scalar score. |
| Evolutionary search | Yes | Mutation, a population of proposals, elitist selection. |
| Narrow RSI (definition above) | Yes | The retained policy is both the current algorithm and the parent for later modifications. |
| Arbitrary self-modifying code | No | Candidates are validated JSON DSL, never Python/source text. |
| Demonstrated improvement | Only when logs show it | A retained candidate must pass validation; no scores are claimed in advance. |

An optional LLM could replace `MutationGenerator.propose` with structured JSON
proposals.  It is intentionally **not enabled**: generation is local and
deterministic.  An LLM would be the *proposal generator*, never the policy,
evaluator, or selector, and its JSON must go through exactly the same validator.

## Architecture

```text
                prior generation summaries
                          |
                          v
  generator --> candidate policy JSON --> schema/path validation
                                         |
                                         v
 baseline/incumbent --> isolated evaluator subprocess --> metrics JSON
                                         |
                                         v
                         selector (validation gate)
                                         |
                         +---------------+
                         | retain incumbent or candidate
                         v
                  next generation's parent policy
```

The modified program is `PolicyProgram`: a numeric, fixed-grammar search
algorithm that decides population size, initialization, local-mutation scale,
cooling, restart rate, elitism, and one bounded proposal kernel (Gaussian,
coordinate, or Cauchy).  The generator, evaluator, selector, and
benchmark are distinct modules and never import candidate-provided code.

## Safety boundary

The Python implementation is a *defense in depth demonstration*, not a complete
OS security boundary.  It applies these controls:

- candidates are data-only JSON with exact allowed keys, finite bounded numeric
  fields, and no paths, imports, expressions, or source code;
- all writable run paths are canonicalized and constrained under `--output`;
- each evaluation occurs in a fresh subprocess with a scrubbed environment,
  bounded timeout, and no inherited stdin;
- the evaluator accepts a candidate filename only from its private working
  directory and writes one JSON result;
- no network or deployment functionality exists in this code.

For an actual containment boundary, run the supplied Docker command.  It drops
Linux capabilities, makes the root filesystem read-only, uses a tmpfs working
directory, limits CPU/memory/processes, and disables networking.  Do **not**
mistake Python-level controls for sufficient containment of untrusted Python.

## Directory structure

```text
sandboxed_rsi_prototype/
  rsi/                 implementation
  tests/               offline tests
  artifacts/           baseline policy artifact
  logs/                generated runs (gitignored)
  Dockerfile           optional stronger sandbox
  run_experiment.py    CLI entry point
```

## Install and run

Requirements: Python 3.10+; no third-party packages and no network access.

```bash
cd /home/shanky/Documents/Code/sandboxed_rsi_prototype
python3 -m unittest discover -s tests -v
python3 run_experiment.py --generations 5 --candidates 12 --output logs/demo
```

For stronger containment (build only from a trusted, locally available Python
base image—otherwise this command would need an image pull):

```bash
docker build -t local-rsi-prototype .
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --pids-limit 64 --memory 256m --cpus 1 --tmpfs /work:rw,noexec,nosuid,size=64m \
  local-rsi-prototype --generations 5 --candidates 12 --output /work/run
```

## Reproducible benchmark and scoring

Each policy receives 320 objective calls on 4D Sphere, Rastrigin, Ackley, and
Rosenbrock.  Scores are `1 / (1 + best_cost)` and are averaged over seven fixed
seeds per split.  Lower costs are better; the result also reports mean cost.
The benchmark functions, dimension, budget, and split seeds are hard-coded in
`rsi/benchmark.py`; candidates cannot modify them.

Train seeds guide proposal ranking.  Validation seeds decide promotion.  An
improvement must exceed `--min-improvement` (default `0.002`) on validation,
which protects the best known program from routine noise/regressions.  The
final audit suite is logged but not used for selection.  Fixed suites make exact
reproduction possible, but repeated selection still risks benchmark overfitting.

Metrics per generation include parent/candidate hashes, changed fields, train
and validation score/cost, decision, errors, elapsed time, and final-audit
metrics.  `run.json` records every attempt; `summary.json` records the champion
trajectory; each candidate result is retained separately.

## Evaluation and selection

1. Evaluate incumbent once on train, validation, and audit splits.
2. Generate bounded mutations plus one deterministic, history-informed
   extrapolation proposal.
3. Evaluate all valid candidates on train.  Keep the top `--train-survivors`.
4. Evaluate only those survivors on validation in separate subprocesses.
5. Promote the best candidate only if its validation score clears the incumbent
   by the configured margin; otherwise retain the incumbent.
6. Audit the retained incumbent.  Its artifact becomes the next parent.

This explicitly separates optimization signal (train), selection (validation),
and reporting (audit).  Audit is not a claim of statistically rigorous
generalization: seven deterministic seeds are intentionally small enough for a
toy experiment.

## Failure modes and bottlenecks

- **Overfitting / multiple comparisons:** validation is consulted many times;
  reserve a final, untouched suite for a real study.
- **No improvement:** the bounded grammar may lack a better policy, or the
  baseline may already be adequate.
- **Stochastic luck:** fixed seeds reduce noise but do not remove it; increase
  seeds and confidence intervals for a serious result.
- **Benchmark gaming:** policies may exploit details of these smooth functions.
- **Evaluation cost:** broad, reliable evaluation is the limiting resource.
- **Generator stagnation:** local mutation has no guarantee of finding useful
  structural algorithms.
- **Containment limits:** the included subprocess is not a substitute for a VM
  or a properly configured container for adversarial code.

## Why this does not generalize to AGI

The policy language has seven bounded numbers and one three-way algorithmic
choice; it cannot alter its own
representation, evaluator, objectives, sandbox, or computational resources. It
has no world model, long-horizon planning, ability to acquire data, experiments,
tool use, transfer learning, or semantic understanding.  The objective is
externally fixed and narrow.  Success merely demonstrates benchmarked algorithm
configuration/strategy search; it does not support claims about intelligence
explosion or general recursive improvement.

## Capabilities a stronger form would theoretically need

A stronger research system would require safe, inspectable representation and
editing of algorithms/models; reliable code synthesis and formal/empirical
verification; broad held-out task distributions; calibrated uncertainty and
causal experiment design; efficient resource allocation; interpretable
mechanisms for rollback and corrigibility; robust isolation; and governance for
any external tools or deployment.  Those ingredients raise safety and alignment
questions rather than implying a goal to persist or improve.

Capability, objective, and motivation are separate variables.  This program
only executes a human-invoked loop toward a supplied score.  It has neither
preferences nor any mechanism or incentive for self-preservation.

## Honest results policy

The repository ships with a baseline artifact, not precomputed improvement
claims.  Run the commands above and inspect the created log.  A run with no
promotion is a valid outcome, and errors/rejections are logged rather than
silently discarded.
