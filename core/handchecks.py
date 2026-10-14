# core/handchecks.py
"""Hand-made coherent Pauli checks that also work on T-doped circuits.

A check is (start, end, P_in). The ancilla starts in |+>, applies controlled-P_in
before instruction `start`, the payload runs, then controlled-P_out before
instruction `end`, where P_out = U P_in U^dagger is P_in propagated through the
payload segment. With no errors the ancilla returns to |+> and reads 0.
"""
from dataclasses import dataclass
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.quantum_info import Pauli

DIAGONAL_NON_CLIFFORD = {"t", "tdg"}


@dataclass
class HandCheck:
    start: int
    end: int
    pauli_in: str
    pauli_out: str = ""
    valid: bool = False
    reason: str = ""


def propagate(payload, start, end, label):
    """Push a Pauli through payload.data[start:end]. Returns (Pauli or None, reason)."""
    p = Pauli(label)
    for idx in range(start, end):
        inst = payload.data[idx]
        qs = [payload.find_bit(q).index for q in inst.qubits]
        name = inst.operation.name
        if name in DIAGONAL_NON_CLIFFORD:
            q = qs[0]
            if p.x[q]:   # X or Y on this qubit -> does not commute with T
                return None, f"X/Y on qubit {q} crosses {name} at instruction {idx}"
            continue     # I or Z commutes with T: Pauli unchanged
        p = p.evolve(inst.operation, qargs=qs, frame="s")
    return p, ""


def make_check(payload, start, end, label):
    p_out, reason = propagate(payload, start, end, label)
    if p_out is None:
        return HandCheck(start, end, label, valid=False, reason=reason)
    return HandCheck(start, end, label, pauli_out=p_out.to_label(), valid=True)


def frame_at(payload, check, t):
    p, _ = propagate(payload, check.start, t, check.pauli_in)
    return p


def compatible(payload, checks):
    """Checks that overlap in time must commute, or they disturb each other."""
    for a in checks:
        for b in checks:
            if a is b:
                continue
            for t, lab in ((b.start, b.pauli_in), (b.end, b.pauli_out)):
                if a.start <= t <= a.end:
                    fa = frame_at(payload, a, t)
                    if fa is None or not fa.commutes(Pauli(lab)):
                        return False
    return True


def _controlled_pauli(qc, anc, label, data):
    sign = label.startswith("-")
    lab = label.lstrip("-")
    for q, ch in enumerate(reversed(lab)):      # Qiskit labels: rightmost = qubit 0
        if ch == "X":
            qc.cx(anc, data[q])
        elif ch == "Z":
            qc.cz(anc, data[q])
        elif ch == "Y":                         # CY = Sdg . CX . S on target
            qc.sdg(data[q]); qc.cx(anc, data[q]); qc.s(data[q])
    if sign:
        qc.z(anc)                               # controlled(-I) = Z on the control


def apply_checks(payload, checks):
    """Build the measured circuit: payload + hand checks + ancilla X-basis readout."""
    n = payload.num_qubits
    data = QuantumRegister(n, "q")
    meas = ClassicalRegister(n, "meas")
    regs = [data]
    if checks:
        anc = QuantumRegister(len(checks), "checks_q")
        regs.append(anc)
    regs.append(meas)
    if checks:
        creg = ClassicalRegister(len(checks), "checks_c")
        regs.append(creg)
    qc = QuantumCircuit(*regs)

    opens, closes = {}, {}
    for k, c in enumerate(checks):
        opens.setdefault(c.start, []).append(k)
        closes.setdefault(c.end, []).append(k)

    for k in range(len(checks)):
        qc.h(anc[k])
    for idx in range(len(payload.data) + 1):
        for k in closes.get(idx, []):
            _controlled_pauli(qc, anc[k], checks[k].pauli_out, data)
        for k in opens.get(idx, []):
            _controlled_pauli(qc, anc[k], checks[k].pauli_in, data)
        if idx < len(payload.data):
            inst = payload.data[idx]
            qc.append(inst.operation, [data[payload.find_bit(q).index] for q in inst.qubits])
    for k in range(len(checks)):
        qc.h(anc[k])
    qc.measure(data, meas)
    if checks:
        qc.measure(anc, creg)
    return qc


def candidate_checks(payload, n_windows=6):
    """All valid weight-1 starting checks over a grid of time windows."""
    n, L = payload.num_qubits, len(payload.data)
    step = max(1, L // n_windows)
    valid, rejected = [], 0
    for q in range(n):
        for P in "XYZ":
            lab = ["I"] * n
            lab[n - 1 - q] = P
            lab = "".join(lab)
            for s in range(0, L, step):
                for e in range(s + step, L + 1, step):
                    c = make_check(payload, s, e, lab)
                    if c.valid:
                        valid.append(c)
                    else:
                        rejected += 1
    return valid, rejected