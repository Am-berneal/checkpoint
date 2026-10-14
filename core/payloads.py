# core/payloads.py
import numpy as np
from qiskit import QuantumCircuit

CLIFF_1Q = ["h", "s", "sdg", "sx", "x", "z"]
PAULICE_GATES = {"cx", "cz", "h", "s", "sdg", "sx", "sxdg", "x", "z", "rz"}


def random_clifford_ops(n_qubits, depth, seed):
    """Brickwork layers: a random 1q Clifford on every qubit, then CX on alternating pairs."""
    rng = np.random.default_rng(seed)
    ops = []
    for layer in range(depth):
        for q in range(n_qubits):
            ops.append((str(rng.choice(CLIFF_1Q)), (q,)))
        for q in range(layer % 2, n_qubits - 1, 2):
            ops.append(("cx", (q, q + 1)))
    return ops


def ops_to_circuit(n_qubits, ops):
    qc = QuantumCircuit(n_qubits)
    for name, qargs in ops:
        getattr(qc, name)(*qargs)
    return qc


def build_payload(n_qubits=4, depth=4, n_t=0, seed=7):
    """Mirror payload: V (Clifford + n_t T gates) followed by V^dagger.
    Ideal output is always |00...0>, so every circuit in the family is compared fairly.
    No measurements are added here."""
    ops = random_clifford_ops(n_qubits, depth, seed)

    # nested T positions: same permutation for every n_t
    perm = np.random.default_rng(seed + 1000).permutation(len(ops))
    t_slots = set(int(i) for i in perm[:n_t])

    fwd_ops = []
    for i, op in enumerate(ops):
        fwd_ops.append(op)
        if i in t_slots:
            fwd_ops.append(("t", (op[1][0],)))   # T on the first qubit of that op

    qc = ops_to_circuit(n_qubits, fwd_ops)
    forward = qc.copy()
    qc.compose(forward.inverse(), inplace=True)   # inverts the T gates too (T -> Tdg)
    qc.name = f"payload_T{n_t}"
    return qc


def t_count(qc):
    """Total non-Clifford gates: T plus Tdg."""
    ops = qc.count_ops()
    return ops.get("t", 0) + ops.get("tdg", 0)


def is_paulice_compatible(qc):
    """True if qiskit-paulice will accept this circuit (Clifford gate set only)."""
    return set(qc.count_ops()) <= PAULICE_GATES


def describe(qc):
    ops = qc.count_ops()
    return {
        "name": qc.name,
        "width": qc.num_qubits,
        "depth": qc.depth(),
        "cx": ops.get("cx", 0),
        "t": t_count(qc),
        "paulice_ok": is_paulice_compatible(qc),
    }