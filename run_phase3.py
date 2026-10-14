# run_phase3.py
import pandas as pd
import matplotlib.pyplot as plt
from core.payloads import build_payload
from core.reference import ideal_distribution, fidelity
from core.noise import make_noise_model
from core.run import run_hand
from core.handchecks import candidate_checks, apply_checks, compatible
from core.score import estimation_error

N_QUBITS, DEPTH, SEED = 4, 4, 7
SCREEN_SHOTS, SHOTS = 1000, 8192
MAX_CHECKS = 4
T_INSERTS = [0, 1, 2, 4]               # total non-Clifford gates = 2x
NOISE_LEVELS = [0.01, 0.03]            # two-qubit error rate p2
SHOT_BUDGETS = [100, 1000, 10000]

rows, cand_rows = [], []
for p2 in NOISE_LEVELS:
    noise = make_noise_model(p1=p2 / 10, p2=p2, p_meas=0.01, p_t=p2 / 2)
    for n_t in T_INSERTS:
        payload = build_payload(N_QUBITS, DEPTH, n_t, SEED)
        ideal, _ = ideal_distribution(payload)

        # 1. every valid single check; the rest are blocked by T walls
        cands, rejected = candidate_checks(payload)
        cand_rows.append({"p2": p2, "t_gates": 2 * n_t,
                          "valid_checks": len(cands), "blocked_by_T": rejected})

        # 2. screen each candidate alone with a few shots
        screened = []
        for c in cands:
            counts, keep = run_hand(apply_checks(payload, [c]), noise, SCREEN_SHOTS)
            if counts:
                screened.append((fidelity(ideal, counts), c))
        screened.sort(key=lambda x: -x[0])

        # 3. greedy: add the best candidate that commutes with those already chosen
        chosen = []
        configs = [[]]
        for _, c in screened:
            if len(chosen) >= MAX_CHECKS:
                break
            if compatible(payload, chosen + [c]):
                chosen.append(c)
                configs.append(list(chosen))

        # 4. full-shot run of each configuration (0..MAX_CHECKS checks)
        for checks in configs:
            circ = apply_checks(payload, checks)
            counts, keep = run_hand(circ, noise, SHOTS)
            f_ps = fidelity(ideal, counts) if counts else float("nan")
            row = {"p2": p2, "t_gates": 2 * n_t, "n_checks": len(checks),
                   "F_postselected": round(f_ps, 4), "keep_fraction": round(keep, 4),
                   "added_2q": circ.count_ops().get("cx", 0) + circ.count_ops().get("cz", 0)
                               - payload.count_ops().get("cx", 0),
                   "checks": "; ".join(f"{c.pauli_in}@{c.start}-{c.end}" for c in checks)}
            for N in SHOT_BUDGETS:
                row[f"err_N{N}"] = round(estimation_error(f_ps, keep, N), 4)
            rows.append(row)
        print(f"done p2={p2} T={2*n_t}: {len(cands)} valid, {rejected} blocked")

df = pd.DataFrame(rows)
cand_df = pd.DataFrame(cand_rows)
df.to_csv("results/phase3_sweep.csv", index=False)
cand_df.to_csv("results/phase3_candidates.csv", index=False)
print(cand_df.to_string(index=False))
print(df.drop(columns="checks").to_string(index=False))

# ---- best configuration per (noise, T, shot budget) ----
best = []
for (p2, t), g in df.groupby(["p2", "t_gates"]):
    for N in SHOT_BUDGETS:
        r = g.loc[g[f"err_N{N}"].idxmin()]
        best.append({"p2": p2, "t_gates": t, "shot_budget": N,
                     "best_n_checks": int(r.n_checks), "F_ps": r.F_postselected,
                     "keep": r.keep_fraction, "error": r[f"err_N{N}"]})
best_df = pd.DataFrame(best)
best_df.to_csv("results/phase3_best.csv", index=False)
print(best_df.to_string(index=False))

# ---- figures ----
for p2 in NOISE_LEVELS:
    sub = df[df.p2 == p2]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for t, g in sub.groupby("t_gates"):
        axes[0].plot(g.n_checks, g.F_postselected, "o-", label=f"{t} T gates")
        axes[1].plot(g.keep_fraction, g.F_postselected, "o-", label=f"{t} T gates")
    axes[0].set_xlabel("Number of checks"); axes[0].set_ylabel("Post-selected fidelity")
    axes[1].set_xlabel("Kept-shot fraction"); axes[1].set_ylabel("Post-selected fidelity")
    axes[1].invert_xaxis()
    for ax in axes:
        ax.legend(fontsize=8)
    fig.suptitle(f"Checks vs T count (p2 = {p2})")
    fig.savefig(f"results/phase3_tradeoff_p2_{p2}.png", dpi=150, bbox_inches="tight")

    fig, axes = plt.subplots(1, len(SHOT_BUDGETS), figsize=(15, 4.2))
    for ax, N in zip(axes, SHOT_BUDGETS):
        for t, g in sub.groupby("t_gates"):
            ax.plot(g.n_checks, g[f"err_N{N}"], "o-", label=f"{t} T")
        ax.set_title(f"Shot budget N = {N}")
        ax.set_xlabel("Number of checks"); ax.set_ylabel("Estimation error (lower is better)")
        ax.legend(fontsize=8)
    fig.suptitle(f"Sweet spot: estimation error vs checks (p2 = {p2})")
    fig.savefig(f"results/phase3_sweetspot_p2_{p2}.png", dpi=150, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(6, 4))
for p2, g in cand_df.groupby("p2"):
    ax.plot(g.t_gates, g.valid_checks, "o-", label=f"p2={p2}")
ax.set_xlabel("Number of T gates"); ax.set_ylabel("Valid check placements")
ax.set_title("T walls shrink the space of valid checks")
fig.savefig("results/phase3_t_walls.png", dpi=150, bbox_inches="tight")
print("Saved results/phase3_*.csv and results/phase3_*.png")