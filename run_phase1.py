# run_phase1.py
import pandas as pd
from core.payloads import build_payload, describe
from core.reference import ideal_distribution, shannon_entropy, fidelity
from core.noise import make_noise_model
from core.run import run_counts

N_QUBITS, DEPTH, SEED, SHOTS = 4, 4, 7, 8192
T_COUNTS = [0, 1, 2, 4, 8]
noise = make_noise_model()

rows = []
for n_t in T_COUNTS:
    qc = build_payload(N_QUBITS, DEPTH, n_t, SEED)
    ideal, method = ideal_distribution(qc)
    noiseless = fidelity(ideal, run_counts(qc, None, SHOTS))
    noisy = fidelity(ideal, run_counts(qc, noise, SHOTS))
    rows.append({**describe(qc), "ref_method": method,
                 "ideal_support": len(ideal),
                 "ideal_entropy": round(shannon_entropy(ideal), 3),
                 "F_noiseless": round(noiseless, 4),
                 "F_noisy": round(noisy, 4)})

df = pd.DataFrame(rows)
df.to_csv("results/phase1_baseline.csv", index=False)
print(df.to_string(index=False))

# Save a picture of the 2-T payload for the report
fig = build_payload(N_QUBITS, DEPTH, 2, SEED).draw("mpl")
fig.savefig("results/payload_T2.png", dpi=150, bbox_inches="tight")
print("Saved results/phase1_baseline.csv and results/payload_T2.png")