# Source-Level Recursive Self-Improvement Experiment

This experiment is the source-code successor to the JSON-policy prototype. Its
mutable artifact is a real Python module, `baseline_optimizer.py`. The module
contains the optimizer's parent-selection and proposal logic. Each candidate is
a complete child source file, saved alongside an exact unified diff.

## The loop

```text
current optimizer source
  -> SourceMutationAI parses/analyses its constants and proposal algorithm
  -> synthesizes bounded Python child source + exact diff
  -> source validator
  -> Linux namespace worker produces a fixed-budget point trace
  -> independent parent evaluator replays trace against fixed objectives
  -> train ranking, independent validation gate, audit
  -> promoted child's exact source becomes the next parent
```

`SourceMutationAI` is a local, deterministic program synthesizer, not an LLM.
It searches a deliberately small grammar: three different `propose` function
bodies (Gaussian, coordinate, Cauchy) and seven hard-coded numeric constants.
An LLM could be substituted only as an offline source-proposal producer; every
proposal would still have to clear the same source validator and evaluator.

## Classification—do not conflate these

| Term | In this experiment |
| --- | --- |
| Parameter optimization | Not present. Nothing learns model weights/parameters from data. |
| Hyperparameter optimization | Present when a child edits source constants such as `ELITE_BIAS`. |
| Evolutionary search | Present: multiple mutations, train ranking, elitist retention. |
| Code generation | Present: the synthesizer emits a complete child `.py` module and diff. |
| Automated program synthesis | Present, but constrained: it searches an explicitly limited source grammar. |
| Recursive self-improvement | Present only in a narrow source-level sense when a promoted child module becomes the source parent of subsequent synthesis rounds. |

### Minimum criterion for the narrow RSI label

This system may be called a *bounded source-level RSI demonstration* only if all
of these are true in its log:

1. an actual executable source child differs from the parent, rather than merely
   an external configuration record;
2. an independent evaluator scores the child's externally replayed behavior;
3. at least one **algorithmic** source rewrite (not only a constant edit) clears
   the validation gate; and
4. that exact promoted source is used as the parent in a later generation.

Even then, it is not open-ended or general RSI. The generator, evaluator,
benchmark, grammar, resource bounds, and objective cannot themselves be
modified. If no algorithmic child is promoted, the run must be reported as
source-level hyperparameter/evolutionary optimization—not RSI.

## Evaluator independence and containment

The child source never runs in the evaluator process. A child is executed in a
fresh Linux user, mount, PID, and network namespace using `unshare`:

- its chroot has only a read-only `/usr` runtime, read-only candidate source,
  read-only trace worker, an isolated proc filesystem, and a tmpfs;
- no host home, experiment logs, evaluator source, credentials, or network
  namespace is mounted into it;
- the child source grammar bans imports, reflection/private attributes, file
  operations, process APIs, dynamic calls, and unsupported syntax;
- the worker emits only candidate points. It emits **no scores**;
- the parent-side evaluator, outside the namespace and not mounted inside it,
  verifies trace length/range/shape and recomputes every objective cost itself.

Thus a candidate cannot alter the evaluator filesystem, alter its process,
report a fabricated score, alter the fixed call budget, or promote itself.
The parent launcher writes only inside `source_rsi/source_runs/<run>/`; it
rejects baseline/output path escapes and does no network or deployment work.

This is strong containment for this restricted Python DSL, not a claim that
arbitrary hostile native code is safely contained. The launcher refuses to run
if `unshare` is unavailable rather than silently falling back to host execution.

## Benchmark, selection, and logs

The evaluator owns four 4D objectives (Sphere, Rastrigin, Ackley, Rosenbrock),
240 calls each, and three deterministic seeds per split. Score is
`1 / (1 + best_cost)`, averaged across the 12 tasks. Train ranks children;
validation independently gates promotion by `--min-improvement` (0.002);
audit is report-only.

Each `generation.json` and the aggregate `run.json` record parent hash, child
hash, exact unified diff, field changes, whether the proposal changed an
algorithm body or only a numeric source constant, train/validation/audit scores,
promotion decision, and cumulative validation improvement. Candidate source and
`.diff` files are retained under `candidates/generation-*/`.

## Run

```bash
cd /home/shanky/Documents/Code/sandboxed_rsi_prototype
python3 -m unittest discover -s tests -v
python3 run_source_rsi.py --generations 4 --candidates 6 --train-survivors 2 \
  --output source_rsi/source_runs/my-source-run
```

No third-party dependencies are required; Python 3.10+ and Linux `unshare` are
required. The prior JSON-policy prototype remains in `rsi/` for comparison.

## Limits and non-generalization

This result does not establish AGI, self-awareness, autonomous motivation,
self-preservation, or a pathway to an intelligence explosion. It is bounded
program search across three known local-search operators on a fixed benchmark.
It cannot modify its proposal generator, validation criterion, containment,
objectives, data, hardware, or its permitted language. Fixed validation also
risks repeated-selection overfitting; a serious study needs larger held-out and
unseen task distributions, confidence intervals, and a final untouched test.

Capability, objective, and motivation remain separate. This system has an
externally supplied scoring routine and executes only on human invocation; it
does not possess a desire to improve or persist.
