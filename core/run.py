# core/run.py
from qiskit_aer.primitives import SamplerV2
import numpy as np

def run_counts(qc, noise_model=None, shots=8192, seed=1234):
    """Measure all qubits and sample with Aer's SamplerV2. Returns a counts dict."""
    circ = qc.copy()
    circ.measure_all()
    backend_options = {"noise_model": noise_model} if noise_model is not None else {}
    sampler = SamplerV2(default_shots=shots, seed=seed,
                        options={"backend_options": backend_options})
    result = sampler.run([circ]).result()
    return result[0].data.meas.get_counts()

def run_checked(checked, noise_model=None, shots=8192, seed=1234):
    """Run a CheckedCircuit, discard shots with a non-trivial syndrome.
    Returns (counts of kept data bits, kept-shot fraction)."""
    backend_options = {"noise_model": noise_model} if noise_model is not None else {}
    sampler = SamplerV2(default_shots=shots, seed=seed,
                        options={"backend_options": backend_options})
    res = sampler.run([checked.circuit]).result()[0]

    data_bits = res.data.meas.get_bitstrings()          # payload qubits only
    if checked.check_qubits:
        syndrome = checked.get_postselection_method()
        full_bits = res.join_data().get_bitstrings()    # every classical bit, same shot order
        kept = [d for d, b in zip(data_bits, full_bits) if not np.any(syndrome(b))]
    else:
        kept = data_bits

    counts = {}
    for b in kept:
        counts[b] = counts.get(b, 0) + 1
    return counts, len(kept) / len(data_bits)

def run_hand(circuit, noise_model=None, shots=8192, seed=1234):
    """Run a circuit built by apply_checks; keep shots whose check bits are all 0."""
    backend_options = {"noise_model": noise_model} if noise_model is not None else {}
    sampler = SamplerV2(default_shots=shots, seed=seed,
                        options={"backend_options": backend_options})
    res = sampler.run([circuit]).result()[0]
    data_bits = res.data.meas.get_bitstrings()
    if "checks_c" in [c.name for c in circuit.cregs]:
        check_bits = res.data.checks_c.get_bitstrings()
        kept = [d for d, a in zip(data_bits, check_bits) if "1" not in a]
    else:
        kept = data_bits
    counts = {}
    for b in kept:
        counts[b] = counts.get(b, 0) + 1
    return counts, len(kept) / len(data_bits)