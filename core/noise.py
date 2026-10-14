# core/noise.py
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

CLIFF_1Q = ["h", "s", "sdg", "sx", "sxdg", "x", "z", "rz"]


def make_noise_model(p1=0.001, p2=0.01, p_meas=0.01, p_t=None):
    p_t = p1 if p_t is None else p_t
    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), CLIFF_1Q)
    nm.add_all_qubit_quantum_error(depolarizing_error(p_t, 1), ["t", "tdg"])
    nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), ["cx", "cz"])
    nm.add_all_qubit_readout_error(ReadoutError([[1 - p_meas, p_meas], [p_meas, 1 - p_meas]]))
    return nm