# core/noise.py
from qiskit_aer.noise import NoiseModel, depolarizing_error, ReadoutError

ONE_Q = ["h", "s", "sdg", "sx", "sxdg", "x", "z", "t", "tdg", "rz"]


def make_noise_model(p1=0.001, p2=0.01, p_meas=0.01):
    nm = NoiseModel()
    nm.add_all_qubit_quantum_error(depolarizing_error(p1, 1), ONE_Q)
    nm.add_all_qubit_quantum_error(depolarizing_error(p2, 2), ["cx", "cz"])
    nm.add_all_qubit_readout_error(ReadoutError([[1 - p_meas, p_meas], [p_meas, 1 - p_meas]]))
    return nm