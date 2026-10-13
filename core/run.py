# core/run.py
from qiskit_aer.primitives import SamplerV2


def run_counts(qc, noise_model=None, shots=8192, seed=1234):
    """Measure all qubits and sample with Aer's SamplerV2. Returns a counts dict."""
    circ = qc.copy()
    circ.measure_all()
    backend_options = {"noise_model": noise_model} if noise_model is not None else {}
    sampler = SamplerV2(default_shots=shots, seed=seed,
                        options={"backend_options": backend_options})
    result = sampler.run([circ]).result()
    return result[0].data.meas.get_counts()