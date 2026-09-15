# Sandboxed Recursive Self-Improvement Prototype

> **A sleep-deprived research project about letting code improve code, while very specifically not letting the code become root.**
>
> Written at an hour when sensible people are asleep and computers are making suspicious noises.

## What is this?

This is a deliberately constrained experiment in **recursive self-improvement (RSI)**.

The basic idea is stupidly simple:

```text
program
  ↓
make a slightly different program
  ↓
run it
  ↓
see if it is actually better
  ↓
keep it if it is
  ↓
use THAT program to make the next one
  ↓
repeat until either it works or the laws of thermodynamics win
```

Except there is one fairly important detail:

**the thing being improved does not get to redesign the laboratory.**

It cannot rewrite the evaluator, change the benchmark, escape the sandbox, acquire networking, rummage through credentials, or decide that it has promoted itself because it feels particularly intelligent today.

This is not AGI. It is not consciousness. It is not an intelligence explosion. It is a small optimizer being repeatedly modified under a bunch of deliberately boring restrictions.

The boring restrictions are the interesting part.

---

## What the project actually contains

There are two experiments because apparently one experiment was not enough paperwork.

### `rsi/` — the original JSON-policy experiment

The optimizer is represented as restricted JSON data.

This is the simpler version. It demonstrates the basic loop without allowing candidates to generate arbitrary Python source.

### `source_rsi/` — the source-level experiment

This is the more interesting version.

The mutable artifact is an actual Python module, `baseline_optimizer.py`.

Candidates can therefore change real program logic, subject to a tiny allowed source grammar. A candidate is accepted only if it survives validation, runs inside the containment boundary, produces valid behavior, and improves on an independently evaluated validation suite.

So yes, it technically modifies code.

No, it does not get to rewrite `sudo`.

---

# The whole thing in one picture

```text
                    HUMAN
                      |
                      v
              +---------------+
              |   RSI ENGINE  |
              | trusted stuff |
              +-------+-------+
                      |
                current source
                      |
                      v
              +---------------+
              | SourceMutation |
              |      AI        |
              | bounded search |
              +-------+-------+
                      |
                child Python
                      |
                      v
              +---------------+
              |    VALIDATOR   |
              | AST + grammar  |
              +-------+-------+
                      |
                 "looks legal"
                      |
                      v
              +---------------+
              |    SANDBOX     |
              | user / mount / |
              | PID / network  |
              |    namespaces  |
              +-------+-------+
                      |
                 point traces
                      |
                      v
              +---------------+
              |   EVALUATOR    |
              | calculates the |
              | score itself    |
              +-------+-------+
                      |
                      v
              +---------------+
              | PROMOTION GATE |
              | better enough? |
              +-------+-------+
                      |
                 +----+----+
                 |         |
              promote    reject
                 |         |
                 +----+----+
                      |
                      v
                 next parent
```

The candidate gets the computational equivalent of a tiny apartment with no doors to the outside world.

The evaluator lives elsewhere.

This is intentional.

---

# The RSI loop

The source-level experiment is basically:

```text
parent source
     |
     v
SourceMutationAI
     |
     +----> candidate source
     |
     v
AST/source validation
     |
     v
train evaluation
     |
     v
keep the best few
     |
     v
validation evaluation
     |
     v
"did this actually improve?"
     |
   +---+---+
   |       |
  YES      NO
   |       |
   v       v
promote   keep parent
   |
   +---+---+
       |
       v
     audit
       |
       v
 next generation
```

The generator does not get to decide whether its child is good.

The child does not get to decide whether its score is good.

The evaluator does not get to rewrite the child.

The benchmark does not get to mysteriously change because the candidate discovered that Rastrigin is annoying.

Separation of duties. Revolutionary concept. Apparently humans eventually invented it.

---

# So... does it authenticate anything?

No.

There is **no conventional authentication system** in this repository.

There is no:

- username/password login
- OAuth
- JWT
- bearer token
- session cookie
- API key
- login endpoint
- authentication header
- refresh token
- secret-management service
- network API

Because there is no network service to authenticate against.

The security model here is **integrity + isolation**, not authentication.

### Source hashes

Parent and child programs are identified by hashes.

A hash answers:

> "Is this the exact source artifact we recorded?"

It does **not** answer:

> "Is Shanky logged in?"

Those are different questions. Cryptography unfortunately cannot solve every problem merely by appearing in a sentence.

The hashes are therefore artifact identity/integrity mechanisms, not authentication tokens.

---

# What can a candidate actually do?

Not much.

And that is the point.

The validator restricts candidates to a tiny subset of Python. It checks the source with the AST before allowing it anywhere near execution.

The allowed optimizer has:

- seven bounded numeric configuration values;
- one of three permitted algorithms: `gaussian`, `coordinate`, or `cauchy`;
- exactly two optimizer functions;
- a fixed function interface;
- bounded four-dimensional proposal vectors.

The validator rejects things such as:

```text
imports
classes
lambdas
generators
async code
with blocks
try/except
raise
delete
dynamic calls
private/reflection attributes
arbitrary attribute access
arbitrary function calls
```

It also limits source size and requires finite numeric values.

The execution namespace has effectively no builtins and only exposes the explicitly approved helpers.

So the candidate cannot simply discover `subprocess` at 3 AM and decide that today is the day it becomes a Linux distribution.

---

# Then comes the actual sandbox

Because saying "we checked the AST" and calling it a day would be an absolutely incredible security strategy.

`source_rsi/sandbox.py` uses Linux `unshare` to create separate:

- **user namespace**
- **mount namespace**
- **PID namespace**
- **network namespace**

The candidate gets a restricted environment containing:

```text
read-only Python runtime
read-only trusted worker files
read-only candidate source
isolated /proc
tmpfs scratch space
```

It does **not** get:

```text
host home directory
experiment logs
evaluator source
host credentials
network access
```

The environment is scrubbed and stdin is disconnected. CPU time, memory, process count, and execution time are bounded.

And there is an important fail-closed behavior:

> If `unshare` is unavailable, the project refuses to run the candidate.

It does not say "security unavailable, but YOLO" and execute it on the host anyway.

---

# The evaluator does not trust the candidate

This is probably the most important part.

The candidate does **not** submit:

```json
{"score": 0.999999}
```

and expect everyone to clap.

Instead, the sandbox worker emits **point traces**.

The parent-side evaluator receives those traces and independently calculates the objective costs.

Conceptually:

```text
candidate
   |
   | "here are the points I tried"
   v
trusted evaluator
   |
   | calculates objective(point)
   v
actual score
```

The evaluator verifies that:

1. the trace belongs to the requested function and seed;
2. the trace has the correct number of calls;
3. every point has the correct dimensions;
4. every value is finite;
5. every value is inside the permitted domain;
6. the objective function is calculated by the evaluator itself.

Therefore a candidate cannot simply announce that it achieved a score of `∞/10` because it has developed an extremely strong relationship with mathematics.

---

# Train → validation → audit

The system deliberately does not promote whatever looks good on the first benchmark.

It uses three conceptual splits:

### Train

Used to rank candidates.

### Validation

Used to decide whether a candidate is actually worth promoting.

### Audit

Used for reporting only.

The default minimum validation improvement is:

```text
0.002
```

So the rough decision is:

```text
candidate beats parent by enough?
          |
      +---+---+
      |       |
     YES      NO
      |       |
      v       v
   PROMOTE   RETAIN
```

The engine also records whether the winning candidate changed an **algorithm body** or merely changed a numeric constant.

That distinction matters because changing `STEP_SCALE = 0.5` is basically hyperparameter optimization.

Changing the actual proposal algorithm is more interesting.

---

# What gets recorded?

The project is intentionally obnoxious about logging.

Each run can retain:

- parent hash;
- child hash;
- exact unified diff;
- changed fields;
- candidate source;
- train metrics;
- validation metrics;
- audit metrics;
- promotion decision;
- errors;
- elapsed time;
- cumulative validation improvement.

The source-level experiment keeps candidate `.py` files and `.diff` files under the generation directory.

The final promoted program is written as:

```text
best_optimizer.py
```

So you can actually inspect what survived instead of being told "trust me bro, generation 17 was really good."

---

# What the candidate cannot change

This is where the experiment draws its actual boundary.

The candidate cannot modify:

- the evaluator;
- the benchmark objectives;
- the validation criterion;
- the promotion threshold;
- the sandbox;
- the proposal generator;
- the allowed language;
- the hardware/resource policy;
- the parent-side control process;
- its own score.

This is deliberate.

If the optimizer were allowed to rewrite the code that determines whether the optimizer improved, we'd have created a slightly more complicated version of:

```text
"I have evaluated myself and I am excellent."
```

which is not exactly the scientific breakthrough people were hoping for.

---

# Why this is called RSI at all

The term is deliberately used narrowly.

A source-level run only qualifies as the interesting version of the RSI experiment if all of these happen:

1. An actual executable child source differs from its parent.
2. An independent evaluator scores the child's behavior.
3. An **algorithmic source rewrite**, not merely a constant tweak, passes validation.
4. That exact promoted source becomes the parent for a later generation.

If those conditions aren't met, the honest description is something like:

> bounded evolutionary search / source-level hyperparameter optimization

rather than waving the letters **RSI** around like a magical spell.

---

# Running it

## JSON-policy experiment

```bash
python3 -m unittest discover -s tests -v
python3 run_experiment.py \
  --generations 5 \
  --candidates 12 \
  --output logs/demo
```

## Source-level experiment

Linux is required because the source-level sandbox uses `unshare`.

```bash
python3 -m unittest discover -s tests -v
python3 run_source_rsi.py \
  --generations 4 \
  --candidates 6 \
  --train-survivors 2 \
  --output source_rsi/source_runs/my-source-run
```

Requirements:

- Python 3.10+
- Linux
- `unshare` for source-level execution
- no third-party Python dependencies

---

# Docker mode

For another layer of containment, the repository includes a Docker configuration.

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

This is defense in depth, not divine intervention.

The container configuration drops capabilities, disables networking, makes the root filesystem read-only, enables `no-new-privileges`, and imposes resource limits.

It is still **not** a formally verified hostile-code sandbox or a replacement for a hardened VM when dealing with genuinely adversarial native code.

---

# Repository layout

```text
RSI_test/
│
├── rsi/
│   └── the original JSON-policy experiment
│
├── source_rsi/
│   ├── artifacts/
│   │   └── trusted baseline optimizer
│   ├── trusted/
│   │   ├── benchmark.py
│   │   ├── candidate_validation.py
│   │   └── worker.py
│   ├── engine.py
│   ├── evaluator.py
│   ├── sandbox.py
│   ├── templates.py
│   └── source_runs/
│
├── artifacts/
│   └── JSON baseline artifact
│
├── tests/
│   └── offline tests
│
├── logs/
│   └── generated JSON-policy runs
│
├── Dockerfile
├── run_experiment.py
└── run_source_rsi.py
```

---

# Known problems, because science

## Benchmark overfitting

The validation set is consulted repeatedly. That means repeated selection can eventually overfit it.

A serious experiment should use larger, genuinely held-out task distributions and an untouched final test suite.

## Small seed sets

Fixed seeds make experiments reproducible, but reproducibility is not statistical significance.

More seeds and confidence intervals would be appropriate for serious claims.

## Tiny search grammar

The synthesizer only searches a deliberately small space of optimizer structures.

It cannot suddenly invent a new branch of mathematics because it got bored.

## Evaluation cost

Generating candidates is cheap compared with evaluating them reliably.

Independent evaluation is therefore one of the main bottlenecks.

## Sandbox limits

The containment model is designed around this restricted experiment. It should not be interpreted as proof that arbitrary malicious native code is safe.

---

# What this absolutely does NOT prove

Despite what a sufficiently caffeinated README might imply, this project does **not** demonstrate:

- AGI;
- consciousness;
- self-awareness;
- autonomous motivation;
- self-preservation;
- unrestricted self-modification;
- unrestricted resource acquisition;
- evaluator modification;
- sandbox modification;
- deployment autonomy;
- an intelligence explosion.

It is a human-invoked optimization loop operating over a deliberately restricted program representation.

That's it.

Well, that's it **plus Linux namespaces, AST validation, source diffs, deterministic benchmarks, independent scoring, and enough logging to make the README this long at 3 AM.**

---

# The actual design philosophy

The central rule is:

> **Capability does not imply authority.**

A candidate can propose an algorithm without being allowed to judge that algorithm.

It can execute computation without being allowed to inspect the evaluator.

It can become the next parent without being allowed to redesign the machinery that creates its descendants.

It can improve the thing it is responsible for without being handed the keys to everything else.

That separation is the actual experiment.

The recursive part is interesting.

The fact that the recursive thing is sitting inside a tiny Linux prison is arguably more interesting.

And yes, this README was probably written when I should have been sleeping.
