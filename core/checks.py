# core/checks.py
from qiskit_paulice import add_pauli_checks, NoiseModel as PauliceNoise


def paulice_noise(p2=0.01, p_meas=0.01):
    """Noise model qiskit-paulice uses to choose where checks go.
    Keep it consistent with the Aer model used to run the circuits."""
    return PauliceNoise(gate_noise=p2, readout_noise=p_meas)


def checked_family(payload, target_qubits, p2=0.01, p_meas=0.01, seed=1):
    """Return [0 checks, 1 check, ..., len(target_qubits) checks] as CheckedCircuit objects."""
    qc = payload.copy()
    qc.measure_all()                        # add-on requires terminal measurements
    return add_pauli_checks(
        qc,
        target_qubits=list(target_qubits),
        noise_model=paulice_noise(p2, p_meas),
        cost="gamma",
        method="windowed",                  # windowed + gamma + seed = fully deterministic
        seed=seed,
    )


def two_qubit_count(circuit):
    ops = circuit.count_ops()
    return ops.get("cx", 0) + ops.get("cz", 0)


def overhead(checked, bare):
    """Extra cost of the checks compared with the bare measured payload."""
    return {
        "ancillas": len(checked.check_qubits or ()),
        "added_2q": two_qubit_count(checked.circuit) - two_qubit_count(bare.circuit),
        "added_depth": checked.circuit.depth() - bare.circuit.depth(),
    }