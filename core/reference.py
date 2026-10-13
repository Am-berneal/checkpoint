# core/reference.py
import numpy as np
from qiskit.quantum_info import StabilizerState, Statevector, hellinger_fidelity
from .payloads import t_count


def ideal_distribution(qc, tol=1e-12):
    """Stabilizer simulation for Clifford circuits, statevector when T gates are present."""
    if t_count(qc) == 0:
        probs = StabilizerState(qc).probabilities_dict()
        method = "stabilizer"
    else:
        probs = Statevector(qc).probabilities_dict()
        method = "statevector"
    probs = {k: float(v) for k, v in probs.items() if v > tol}
    return probs, method


def shannon_entropy(probs):
    p = np.array(list(probs.values()))
    return float(-(p * np.log2(p)).sum())


def fidelity(ideal_probs, counts):
    """Hellinger fidelity between the ideal and measured output distributions."""
    return hellinger_fidelity(ideal_probs, counts)