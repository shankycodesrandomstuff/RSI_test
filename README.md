# Sandboxed Recursive Self-Improvement Prototype

A deliberately bounded research prototype for studying **recursive self-improvement (RSI)** without giving an optimizer unrestricted access to its own runtime, evaluator, objectives, filesystem, network, or deployment environment.

> **Status:** Offline research prototype. Python 3.10+ required. Linux `unshare` is required for the source-level experiment.

## What this project actually demonstrates

This repository contains two related experiments:

1. **`rsi/`** — a JSON-policy prototype in which the mutable optimizer is represented as a restricted data structure.
2. **`source_rsi/`** — the stronger source-level experiment, where the mutable artifact is a real Python optimizer module.

The source-level experiment is the primary implementation. It can generate candidate source files, validate them, execute them inside a Linux namespace sandbox, independently recompute their benchmark scores, and promote a candidate only when it clears a validation threshold.

The RSI claim is intentionally narrow. A run qualifies as a bounded source-level RSI demonstration only when an actual executable child source differs from its parent, an independent evaluator scores it, an algorithmic source rewrite clears validation, and that exact promoted source becomes the parent for a later generation. This is **not** evidence of AGI, open-ended self-improvement, self-awareness, autonomy, or an intelligence explosion.

## Architecture

```text
                         HUMAN / CLI
                              |
                              v
                    +-------------------+
                    |    RSI Engine     |
                    | trusted control    |
                    +---------+---------+
                              |
                       current source
                              |
                              v
                    +-------------------+
                    | SourceMutationAI   |
                    | bounded synthesis  |
                    +---------+---------+
                              |
                       child Python
                              |
                              v
                    +-------------------+
                    | Source Validator   |
                    | AST + tiny grammar |
                    +---------+---------+
                              |
                           accepted
                              |
                              v
                    +-------------------+
                    | Linux Sandbox      |
                    | user/mount/PID/net |
                    | namespaces         |
                    +---------+---------+
                              |
                         point traces
                              |
                              v
                    +-------------------+
                    | Parent Evaluator   |
                    | recomputes scores  |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    | Validation Gate    |
                    | promote / retain   |
                    +---------+---------+
                              |
                              v
                       next parent
```

The generator, evaluator, selector, and benchmark are separate trusted components. The candidate never controls the promotion decision.

## Source-level experiment

The source-level loop is implemented in `source_rsi/engine.py`:

```text
parent optimizer source
        |
        v
SourceMutationAI
        |
        +--> bounded Python child + exact unified diff
        |
        v
candidate_validation.load_candidate()
        |
        v
train evaluation
        |
        v
best train survivors
        |
        v
independent validation
        |
        v
promotion threshold
   +----+----+
   |         |
retain    promote
   |         |
   +----+----+
        |
        v
independent audit
        |
        v
next generation parent
```

`engine.py` also constrains configuration values, prevents path traversal, refuses to overwrite non-empty run directories, validates the baseline before candidate execution, records parent/child hashes and exact diffs, and writes the final promoted source as `best_optimizer.py`.

## Candidate source security

Candidates are real Python source, but they are restricted to a deliberately tiny language before execution.

`source_rsi/trusted/candidate_validation.py` enforces:

- a maximum source size of 12,000 UTF-8 bytes;
- exactly seven bounded numeric configuration fields plus `ALGORITHM`;
- only the fixed `select_parent(state, rng)` and `propose(state, rng)` functions;
- only the algorithms `gaussian`, `coordinate`, and `cauchy`;
- no imports or `from ... import ...` statements;
- no classes, lambdas, generators, async functions, `with`, `try`, `raise`, `delete`, or dynamic assignment constructs;
- no private/reflection attributes;
- no arbitrary function calls;
- no arbitrary attribute access;
- restricted subscripting and assignment;
- finite numeric values and bounded proposal vectors;
- an execution namespace with empty `__builtins__` and only explicitly supplied helpers.

This is a language restriction, not a proof that Python itself is a secure sandbox. The project therefore adds OS-level isolation as a second boundary.

## Sandbox and containment

`source_rsi/sandbox.py` launches candidates with Linux `unshare` using separate:

- user namespace;
- mount namespace;
- PID namespace;
- network namespace.

The candidate receives:

- a read-only Python runtime;
- read-only trusted worker files;
- read-only candidate source;
- an isolated `/proc`;
- a temporary filesystem for scratch space.

The process receives a scrubbed environment and no inherited stdin. CPU time, virtual memory, process count, and wall-clock execution are bounded. If `unshare` is unavailable, the launcher **refuses to execute the candidate** rather than falling back to unsandboxed host execution.

The candidate has no mounted host home directory, experiment logs, evaluator source, credentials, or network access.

The supplied Docker configuration adds another containment layer: no network, dropped Linux capabilities, read-only root filesystem, `no-new-privileges`, process/memory/CPU limits, and a restricted tmpfs work directory.

### Important limitation

This is strong containment for the deliberately restricted experiment, **not a general-purpose hostile-code sandbox**. Do not treat the Python validator or the supplied container configuration as equivalent to a formally verified VM or hardened production isolation boundary.

## Trust model

There is intentionally no conventional authentication system in this repository.

There are:

- no user/password login flows;
- no OAuth;
- no JWTs;
- no bearer tokens;
- no session cookies;
- no API-key authentication;
- no network service;
- no deployment credentials.

Instead, the security model is based on **integrity and isolation**.

### Source hashes

Parent and child source files are identified using source hashes. These hashes answer:

> "Is this the exact source artifact we recorded?"

They do **not** answer:

> "Is this user authenticated?"

A hash is therefore an artifact-integrity mechanism, not an authentication token.

### Candidate authority

A candidate has no authority to:

- change the benchmark;
- change the evaluator;
- choose its own score;
- change the promotion threshold;
- access experiment logs;
- modify the parent-side process;
- promote itself;
- access host credentials;
- access the network.

The candidate emits only optimization point traces. The parent-side evaluator independently recomputes objective costs from those points and owns the resulting score.

## Evaluation flow

Each candidate is evaluated against fixed numerical objectives. The evaluator verifies:

1. the trace corresponds to the requested function and seed;
2. the trace has exactly the required number of calls;
3. every point has the correct dimensionality;
4. every value is finite and within the allowed domain;
5. objective costs are recomputed independently;
6. the resulting mean score is calculated by the trusted evaluator.

The source-level benchmark uses Sphere, Rastrigin, Ackley, and Rosenbrock objectives with a fixed budget and deterministic seed splits. Training ranks candidates, validation controls promotion, and audit is report-only.

## Promotion policy

The engine does not promote the best-looking training result directly.

```text
candidate population
       |
       v
train evaluation
       |
       v
train survivors
       |
       v
validation evaluation
       |
       v
best valid candidate
       |
       +---- validation improvement >= threshold? ----+
       |                                               |
      YES                                             NO
       |                                               |
       v                                               v
   promote                                         retain parent
```

The default validation improvement threshold is `0.002`.

For the source-level experiment, the logs additionally record whether a promoted candidate changed an algorithm body or only a numeric constant. This distinction matters because a constant tweak is hyperparameter optimization, while an algorithm-body rewrite is the minimum interesting event for the narrow source-level RSI definition.

## Reproducibility

The experiment is designed to be inspectable rather than to manufacture an improvement claim.

Every run can retain:

- parent and child hashes;
- exact unified diffs;
- changed fields;
- candidate source files;
- train metrics;
- validation metrics;
- audit metrics;
- promotion decisions;
- errors;
- elapsed execution time;
- cumulative validation improvement.

A run with zero promotions is a valid result. The repository does not ship with fabricated performance claims.

## Running the project

### JSON-policy prototype

```bash
python3 -m unittest discover -s tests -v
python3 run_experiment.py --generations 5 --candidates 12 --output logs/demo
```

### Source-level experiment

```bash
python3 -m unittest discover -s tests -v
python3 run_source_rsi.py \
  --generations 4 \
  --candidates 6 \
  --train-survivors 2 \
  --output source_rsi/source_runs/my-source-run
```

### Docker containment

Build only from a trusted, locally available Python base image if the environment has no network access:

```bash
docker build -t local-rsi-prototype .
docker run --rm \
  --network none \
  --read-only \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --pids-limit 64 \
  --memory 256m \
  --cpus 1 \
  --tmpfs /work:rw,noexec,nosuid,size=64m \
  local-rsi-prototype \
  --generations 5 \
  --candidates 12 \
  --output /work/run
```

## Repository layout

```text
RSI_test/
├── rsi/                         JSON-policy experiment
├── source_rsi/                  source-level experiment
│   ├── artifacts/               trusted baseline source
│   ├── trusted/                 validator, worker, benchmark
│   ├── engine.py                experiment control loop
│   ├── evaluator.py             independent evaluator
│   ├── sandbox.py               Linux namespace launcher
│   ├── templates.py             bounded source synthesizer
│   └── source_runs/             generated experiment outputs
├── artifacts/                   JSON baseline artifact
├── tests/                       offline tests
├── logs/                        generated JSON-policy runs
├── Dockerfile                   optional container boundary
├── run_experiment.py            JSON-policy entry point
└── run_source_rsi.py            source-level entry point
```

## Failure modes and research limitations

### Benchmark overfitting

Repeated validation can eventually overfit a fixed benchmark. A serious study should reserve a genuinely untouched final test set and use broader task distributions.

### Stochastic selection

Fixed seeds improve reproducibility but do not establish statistical significance. Larger seed sets and confidence intervals are needed for stronger claims.

### Generator stagnation

The source synthesizer searches a deliberately small grammar. It cannot discover arbitrary new programming techniques.

### Evaluation cost

Reliable independent evaluation is the main computational bottleneck. A system that can cheaply generate thousands of candidates but cannot evaluate them independently is not particularly useful.

### Containment

The included isolation mechanisms are designed around this restricted DSL. Arbitrary native code, kernel vulnerabilities, malicious dependencies, or a compromised host require stronger isolation assumptions.

## What this project does *not* show

This project does not demonstrate:

- AGI;
- consciousness or self-awareness;
- autonomous goals;
- self-preservation;
- unrestricted self-modification;
- modification of its own evaluator or objective;
- modification of its own sandbox;
- unrestricted resource acquisition;
- deployment autonomy;
- intelligence explosion.

The system is a human-invoked benchmark optimization loop with a deliberately constrained mutable artifact.

## Design principle

The central principle is **separation of capability, objective, and authority**.

A candidate can be capable of producing an optimizer proposal without being authorized to decide whether that proposal is correct. A candidate can execute computation without receiving access to the evaluator that judges it. A promoted program can become the next parent without gaining control over the machinery that generates, evaluates, or contains its descendants.

That separation is the core research value of the prototype.
