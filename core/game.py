# core/game.py
"""Game engine: levels, check placement on a layer grid, scoring from Qiskit runs."""
import json, os, random, re
import qiskit
import qiskit_aer
from .payloads import build_payload
from .reference import ideal_distribution, fidelity
from .noise import make_noise_model
from .run import run_hand
from .handchecks import make_check, apply_checks, compatible
from .score import estimation_error

N_QUBITS, DEPTH, SEED = 4, 4, 7
P2 = 0.02                      # replace with the organizers' noise model when announced
RUN_SHOTS, RUN_SEED = 4096, 1234
CACHE_PATH = os.path.join("results", "game_cache.json")

LEVELS = {
    1: {"name": "Clean circuit",   "t_inserts": 0, "budget": 3},
    2: {"name": "First impurity",  "t_inserts": 1, "budget": 3},
    3: {"name": "T walls",         "t_inserts": 2, "budget": 3},
    4: {"name": "Magic overload",  "t_inserts": 4, "budget": 3},
}


def noise_model():
    return make_noise_model(p1=P2 / 10, p2=P2, p_meas=0.01, p_t=P2 / 2)


# ---------------- circuit -> grid ----------------
def instruction_layers(payload):
    """ASAP layer (time column) for every instruction."""
    free = [0] * payload.num_qubits
    layers = []
    for inst in payload.data:
        qs = [payload.find_bit(q).index for q in inst.qubits]
        layer = max(free[q] for q in qs)
        layers.append(layer)
        for q in qs:
            free[q] = layer + 1
    return layers


def grid(payload):
    layers = instruction_layers(payload)
    gates = []
    for idx, (inst, layer) in enumerate(zip(payload.data, layers)):
        gates.append({"index": idx, "layer": layer, "name": inst.operation.name,
                      "qubits": [payload.find_bit(q).index for q in inst.qubits]})
    return {"n_qubits": payload.num_qubits,
            "n_layers": (max(layers) + 1) if layers else 0,
            "gates": gates}


def layer_to_index(payload, layer):
    """A check boundary at the start of `layer` = first instruction in that layer or later."""
    for idx, l in enumerate(instruction_layers(payload)):
        if l >= layer:
            return idx
    return len(payload.data)


# ---------------- the engine ----------------
class Game:
    def __init__(self):
        self.noise = noise_model()
        self.payloads = {lv: build_payload(N_QUBITS, DEPTH, cfg["t_inserts"], SEED)
                         for lv, cfg in LEVELS.items()}
        self.ideals = {lv: ideal_distribution(p)[0] for lv, p in self.payloads.items()}
        self.cache = {}
        if os.path.exists(CACHE_PATH):
            with open(CACHE_PATH) as f:
                self.cache = json.load(f)

    def save(self):
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(self.cache, f)

    def provenance(self):
        return {"qiskit": qiskit.__version__, "qiskit_aer": qiskit_aer.__version__,
                "p2": P2, "shots": RUN_SHOTS, "seed": RUN_SEED}

    def build_check(self, level, qubit, pauli, start_layer, end_layer):
        """Player's check in grid terms -> HandCheck (valid or with a reason)."""
        payload = self.payloads[level]
        n = payload.num_qubits
        if pauli not in ("X", "Y", "Z") or not 0 <= qubit < n or end_layer <= start_layer:
            return None, "check needs a qubit, a Pauli X/Y/Z and end after start"
        label = ["I"] * n
        label[n - 1 - qubit] = pauli
        check = make_check(payload, layer_to_index(payload, start_layer),
                           layer_to_index(payload, end_layer), "".join(label))
        if not check.valid:   # report the T wall in grid terms (layer), not instruction index
            m = re.search(r"instruction (\d+)", check.reason)
            if m:
                layer = instruction_layers(payload)[int(m.group(1))]
                check.reason = check.reason.replace(m.group(0), f"layer {layer}")
        return check, ("" if check.valid else check.reason)

    def evaluate(self, level, specs, shot_budget=1000):
        """specs: list of dicts {qubit, pauli, start_layer, end_layer}."""
        cfg, payload = LEVELS[level], self.payloads[level]
        if len(specs) > cfg["budget"]:
            return {"ok": False, "error": f"ancilla budget is {cfg['budget']}"}
        checks = []
        for s in specs:
            c, reason = self.build_check(level, s["qubit"], s["pauli"],
                                         s["start_layer"], s["end_layer"])
            if c is None or not c.valid:
                return {"ok": False, "error": reason, "spec": s}
            checks.append(c)
        if not compatible(payload, checks):
            return {"ok": False, "error": "overlapping checks must commute"}

        key = f"{level}|" + "|".join(sorted(f"{c.pauli_in}@{c.start}-{c.end}" for c in checks))
        if key not in self.cache:
            circ = apply_checks(payload, checks)
            counts, keep = run_hand(circ, self.noise, RUN_SHOTS, RUN_SEED)
            f_ps = fidelity(self.ideals[level], counts) if counts else 0.0
            ops = circ.count_ops()
            self.cache[key] = {
                "F_postselected": f_ps, "keep_fraction": keep,
                "ancillas": len(checks),
                "added_2q": ops.get("cx", 0) + ops.get("cz", 0) - payload.count_ops().get("cx", 0),
                "added_depth": circ.depth() - payload.depth() - 1,
                "checks": [{"pauli_in": c.pauli_in, "pauli_out": c.pauli_out,
                            "start": c.start, "end": c.end} for c in checks],
            }
        r = dict(self.cache[key])
        base = self.baseline(level)
        err = estimation_error(r["F_postselected"], r["keep_fraction"], shot_budget)
        kept_shots = round(shot_budget * r["keep_fraction"])
        r.update({
            "ok": True, "level": level, "shot_budget": shot_budget,
            "F_no_checks": base["F_postselected"],
            "estimation_error": err,
            "bias_term": 1 - r["F_postselected"],
            "statistical_term": err - (1 - r["F_postselected"]),
            "shots_kept": kept_shots, "shots_discarded": shot_budget - kept_shots,
            "provenance": self.provenance(),
        })
        return r

    def baseline(self, level):
        return self.evaluate_raw(level)

    def evaluate_raw(self, level):
        key = f"{level}|"
        if key not in self.cache:
            payload = self.payloads[level]
            counts, keep = run_hand(apply_checks(payload, []), self.noise, RUN_SHOTS, RUN_SEED)
            self.cache[key] = {"F_postselected": fidelity(self.ideals[level], counts),
                               "keep_fraction": keep, "ancillas": 0, "added_2q": 0,
                               "added_depth": 0, "checks": []}
        return self.cache[key]

    # ------------- precomputed Pareto data -------------
    def explore(self, level, n_samples=60, seed=0):
        """Random valid configurations -> points for the Pareto chart."""
        rng = random.Random(seed)
        payload, cfg = self.payloads[level], LEVELS[level]
        n_layers = grid(payload)["n_layers"]
        specs_pool = []
        for q in range(payload.num_qubits):
            for P in "XYZ":
                for s in range(0, n_layers, 2):
                    for e in range(s + 2, n_layers + 1, 2):
                        c, _ = self.build_check(level, q, P, s, e)
                        if c is not None and c.valid:
                            specs_pool.append({"qubit": q, "pauli": P,
                                               "start_layer": s, "end_layer": e})
        points = [self.evaluate(level, [])]
        tries = 0
        while len(points) < n_samples and tries < n_samples * 20 and specs_pool:
            tries += 1
            k = rng.randint(1, cfg["budget"])
            r = self.evaluate(level, rng.sample(specs_pool, min(k, len(specs_pool))))
            if r["ok"]:
                points.append(r)
        return points, len(specs_pool)


def pareto_front(points):
    """Points not beaten on both fidelity and kept fraction."""
    front = []
    for p in points:
        if not any(q["F_postselected"] >= p["F_postselected"] and
                   q["keep_fraction"] >= p["keep_fraction"] and q is not p and
                   (q["F_postselected"] > p["F_postselected"] or
                    q["keep_fraction"] > p["keep_fraction"]) for q in points):
            front.append(p)
    return sorted(front, key=lambda p: -p["keep_fraction"])