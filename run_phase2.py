# run_phase2.py
import pandas as pd
import matplotlib.pyplot as plt
from core.payloads import build_payload
from core.reference import ideal_distribution, fidelity
from core.noise import make_noise_model
from core.run import run_counts, run_checked
from core.checks import checked_family, overhead

# ---- one shared configuration (change here only) ----
N_QUBITS, DEPTH, SEED, SHOTS = 4, 4, 7, 8192
P1, P2, P_MEAS, P_T = 0.001, 0.01, 0.01, 0.005
noise = make_noise_model(p1=P1, p2=P2, p_meas=P_MEAS, p_t=P_T)

# Which qubits the checks attach to, and in what order (order matters!)
TARGET_SETS = {
    "all 0123": [0, 1, 2, 3],
    "all 3210": [3, 2, 1, 0],
    "middle 12": [1, 2],
    "edges 03": [0, 3],
    "q0": [0], "q1": [1], "q2": [2], "q3": [3],
}

rows = []

# ---- Clifford payload: checks from qiskit-paulice ----
payload = build_payload(N_QUBITS, DEPTH, 0, SEED)
ideal, _ = ideal_distribution(payload)

for label, targets in TARGET_SETS.items():
    family = checked_family(payload, targets, p2=P2, p_meas=P_MEAS, seed=1)
    bare = family[0]
    for checked in family:
        counts, keep = run_checked(checked, noise, SHOTS)
        f_ps = fidelity(ideal, counts) if counts else float("nan")
        rows.append({
            "t_gates": 0, "targets": label,
            "n_checks": len(checked.check_qubits or ()),
            "F_postselected": round(f_ps, 4),
            "keep_fraction": round(keep, 4),
            "gamma_cost": round(checked.cost, 4),
            **overhead(checked, bare),
        })
    print(f"done: {label}")

# ---- T-doped payloads: add-on cannot take them (hand-made checks come in Phase 3) ----
for n_t in [1, 2, 4]:
    tq = build_payload(N_QUBITS, DEPTH, n_t, SEED)
    try:
        checked_family(tq, [0], p2=P2, p_meas=P_MEAS)
        print(f"T{n_t}: unexpectedly accepted")
    except Exception as e:
        print(f"T{n_t}: rejected by qiskit-paulice -> {type(e).__name__}: {str(e)[:80]}")
    t_ideal, _ = ideal_distribution(tq)
    f = fidelity(t_ideal, run_counts(tq, noise, SHOTS))
    rows.append({"t_gates": 2 * n_t, "targets": "none", "n_checks": 0,
                 "F_postselected": round(f, 4), "keep_fraction": 1.0,
                 "gamma_cost": None, "ancillas": 0, "added_2q": 0, "added_depth": 0})

df = pd.DataFrame(rows)
df.to_csv("results/phase2_checks.csv", index=False)
print(df.to_string(index=False))

# ---- quick look at the trade-off ----
clif = df[df.t_gates == 0]
fig, ax = plt.subplots(figsize=(7, 5))
for label, g in clif.groupby("targets"):
    ax.plot(g.keep_fraction, g.F_postselected, "o-", label=label)
ax.set_xlabel("Kept-shot fraction")
ax.set_ylabel("Post-selected fidelity")
ax.set_title("Clifford payload: fidelity vs shots kept")
ax.invert_xaxis()   # more checks -> fewer shots kept -> moves right
ax.legend(fontsize=8)
fig.savefig("results/phase2_tradeoff.png", dpi=150, bbox_inches="tight")
print("Saved results/phase2_checks.csv and results/phase2_tradeoff.png")