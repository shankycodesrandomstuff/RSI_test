# Candidate optimizer module. It is data-free source code in a restricted interface.
POPULATION = 4
INITIAL_SAMPLES = 8
STEP_SCALE = 3.2
MIN_SCALE = 0.8
COOLING = 0.992
RESTART_RATE = 0.12
ELITE_BIAS = 0.7
ALGORITHM = "gaussian"


def select_parent(state, rng):
    if rng.random() < ELITE_BIAS:
        return 0
    return rng.randrange(len(state["population"]))


def propose(state, rng):
    parent = state["population"][state["parent_index"]]
    scale = state["scale"]
    return clip([value + rng.gauss(0.0, scale) for value in parent])
