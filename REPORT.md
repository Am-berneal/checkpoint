Checkpoint: a puzzle game about where to place error-detection checks
Qiskit Fall Fest 2026 Hackathon — Advanced Track Team: Dhurander

Summary
Checkpoint is a puzzle game in which the player protects a quantum circuit from noise by placing coherent Pauli checks on it. The circuit is drawn as a spacetime grid (qubits as rows, gate layers as columns), the player has a budget of ancilla qubits, and every move is scored by running the checked circuit in Qiskit Aer and post-selecting on the check outcomes. No score in the game is set by hand.

The physics behind the game gave three findings:

T gates shrink the space of valid checks. A check may cross a T gate only if it acts as I or Z on that qubit. On our 4-qubit payload, the number of valid single-check placements falls from 252 with no T gates to 139 with eight, a 45% reduction.
More T gates lower the fidelity that checks can reach. At a two-qubit error rate of 1%, the best post-selected fidelity falls from 0.937 (Clifford) to 0.878 (eight T gates), because the checks that survive the T walls cannot cover the regions next to them.
"More checks" is not always better, and the best number moves. With 1% two-qubit error the fourth check never improves fidelity, because its own gates add about as much error as it removes. With 3% error, three or four checks are best. With eight T gates and a small shot budget (N = 100), a single check is optimal. The best strategy depends on the noise level, the T count and the shot budget together, and the game makes the player find it.

1. The problem
Noise corrupts the output of every circuit on today's hardware. There are three broad responses:

Approach	What it does	Cost
Detection (this project)	Extra ancilla qubits check the computation; shots where a check fires are discarded	Discarded shots, extra gates
Mitigation	The hardware stays noisy; the estimate is corrected afterwards with extra circuits	Extra circuits and shots
Correction	Errors are decoded and undone during the computation	Many physical qubits per logical qubit
Detection never repairs a state. It buys fidelity by throwing shots away, so a post-selected fidelity means nothing on its own: a strategy that keeps 2% of shots cannot be compared with one that keeps 80%. Throughout this report and the game, post-selected fidelity is always reported with its kept-shot fraction.

A coherent Pauli check works as follows. An ancilla is prepared in |+⟩. Before a segment U of the circuit it applies a controlled Pauli P; after the segment it applies a controlled P′ = U P U†, and it is finally read in the X basis. With no errors, P′ U P = U, so the ancilla returns to |+⟩ and reads 0. An error inside the segment that anti-commutes with the propagated check flips the ancilla to |−⟩ and the shot is discarded.

The qiskit-paulice add-on finds good checks automatically, but only for Clifford circuits. Real algorithms also need non-Clifford gates such as T. A check can still be placed across a T gate if its Pauli acts as I or Z on that qubit at that point, because T is diagonal and commutes with Z. An X or Y there would change the computation. In the game this rule becomes a T wall.

2. Method
2.1 Payload circuits
We use a 4-qubit mirror circuit: a random Clifford block V (4 brickwork layers of random single-qubit Cliffords followed by CX gates on alternating pairs, seed 7), with T gates inserted after randomly chosen gates, followed by its exact inverse V†.

Why a mirror circuit. Every circuit in the family has the same ideal output, |0000⟩. A first version undid only the Clifford part, so the T gates spread the ideal output over 2–8 bitstrings. Noise then appeared to raise fidelity as T gates were added, because a spread-out ideal distribution is barely changed by noise. Mirroring the T gates too (T → T†) removes this artifact: the only thing that changes across the family is the number of noisy gates, while the middle of each circuit is still a genuine non-Clifford state.
Nested T positions. The T positions are taken from one fixed random permutation, so the 2-T circuit contains the 1-T circuit's T gate, and so on. The family differs only in T count.
Family. 1, 2 and 4 T insertions give 2, 4 and 8 non-Clifford gates (each T plus its mirrored T†). All circuits have 12 CX gates and depth 16–20.
2.2 Ideal reference and fidelity
The ideal output is computed with the stabilizer simulator for the Clifford circuit and with statevector simulation for the T-doped ones. As a check, noiseless sampling of every payload gives fidelity 1.000 (Table 1).

We use the Hellinger fidelity between the ideal and measured output distributions (qiskit.quantum_info.hellinger_fidelity), because the game's observable is the measured bitstring and post-selection acts on shot counts. Since the ideal output is a single bitstring, the Hellinger fidelity here equals the probability of measuring the correct answer, which makes it easy to interpret.

2.3 Noise model
Unless stated otherwise we use a depolarizing model in Qiskit Aer:

Parameter	Value
Two-qubit gate error p2 (CX, CZ)	1% (also 2% in the game and 3% in the high-noise sweep)
Single-qubit Clifford error	p2 / 10
T / T† error	p2 / 2 (0.5% in Phases 1–2)
Readout error	1%
The noise model is pluggable (core/noise.py), so an organizer-supplied model or a fake-backend model can replace it in one place. The same model is passed to qiskit-paulice when it chooses checks.

All sampling uses the SamplerV2 primitive from qiskit-aer with fixed seeds (simulation seed 1234, 8192 shots in the analysis, 4096 per game run). Every result can be regenerated from the scripts in the repository.

2.4 Checks on the Clifford circuit (qiskit-paulice)
For the Clifford payload, add_pauli_checks (cost gamma, method windowed, seed 1) returns one circuit per number of checks, from 0 up to one check per target qubit. We varied the target qubits and their order. Post-selection uses the add-on's own get_postselection_method(), because a check's syndrome can combine ancilla bits and data-qubit bits.

We confirmed that the add-on rejects all T-doped circuits (it raises an error naming the unsupported t and tdg gates).

2.5 Hand-made checks on the T-doped circuits
For the T-doped circuits we built our own checks (core/handchecks.py):

A check is defined by a start instruction, an end instruction and a weight-1 Pauli P on one qubit.
P is propagated gate by gate through the segment using Qiskit's Pauli.evolve. If, on reaching a T or T† gate, the propagated Pauli has an X or Y component on that qubit, the check is rejected (the T wall). Otherwise it passes unchanged, since T commutes with I and Z.
The propagated Pauli P′ gives the closing controlled operation. Signs (for example −IIIY) are handled with a Z on the ancilla.
Checks that overlap in time must commute at each other's start and end points; otherwise one check disturbs the other's syndrome.
Every hand-made check circuit was verified noiselessly: with no noise, no check ever fires. (An early version produced false alarms when two overlapping checks anti-commuted; the commutation test in step 4 fixed this.)

Candidate checks were enumerated on a grid of 6 time windows × 4 qubits × 3 Paulis. Each valid candidate was screened alone (1000 shots), and a greedy search then added the best candidate compatible with those already chosen, up to 4 checks. Each configuration was finally run with 8192 shots.

2.6 The score: estimation error at a fixed shot budget
We score a configuration by the total error of estimating the circuit's output with a fixed budget of N shots:

ε = (1 − F_post-selected) + 1 / √(N · kept fraction)

The first term is the bias left by errors the checks did not catch.
The second term is the statistical error from the shots that survive post-selection. It uses a scale constant of 1, a conservative upper bound on the binomial standard error (which is at most 1/(2√n)).
The two terms pull in opposite directions: more checks lower the bias but discard shots, which raises the statistical error. The checks' own gates also add noise. ε therefore has a minimum, the sweet spot, and this is what the game asks the player to find.

3. Results
3.1 Baseline (Phase 1)
Table 1. Payload family under the 1% noise model (8192 shots).

T gates	Depth	CX	Reference method	Ideal support	F (noiseless)	F (noisy)
0	16	12	stabilizer	1	1.000	0.854
2	18	12	statevector	1	1.000	0.848
4	18	12	statevector	1	1.000	0.845
8	20	12	statevector	1	1.000	0.835
Fidelity falls steadily as T gates are added, as it should once the reference artifact (Section 2.1) is removed.

3.2 Checks from qiskit-paulice on the Clifford circuit (Phase 2)
Table 2. Selected configurations (1% noise, 8192 shots). Unchecked fidelity: 0.847.

Targets (in order)	Checks	F post-selected	Kept	Added 2-qubit gates	Added depth
q0,q1,q2,q3	1	0.885	91.3%	3	13
q0,q1,q2,q3	2	0.900	87.2%	5	13
q0,q1,q2,q3	4	0.942	75.7%	11	20
q3,q2,q1,q0	3	0.947	78.4%	9	20
q3,q2,q1,q0	4	0.951	75.0%	12	20
q1,q2	2	0.929	84.8%	5	14
q2 only	1	0.918	87.4%	4	18
Show Image

Observations:

Checks lift fidelity from 0.847 to 0.951 while keeping 75% of shots.
Target order matters. The add-on commits checks one target at a time, so the same set of qubits in reverse order gives different checks: 0.947 with three checks in order q3→q0, against 0.922 in order q0→q3.
Where you check matters more than how many. A single check on q2 (0.918 at 87% kept) beats two checks on q0 and q1 (0.900 at 87% kept).
Checks are not free: each adds 3–4 two-qubit gates and up to 20 layers of depth.
3.3 Hand-made checks across T gates (Phase 3)
Finding 1: T walls shrink the check space.

Table 3. Valid single-check placements on the candidate grid.

T gates	Valid	Blocked by a T wall
0	252	0
2	190	62
4	176	76
8	139	113
Show Image

A check is blocked not only when it starts as X or Y next to a T gate. A Z check can be turned into an X or Y by the Clifford gates in between, before it reaches a wall. The game shows this directly: a Z check on q2 is rejected because the circuit carries it onto q1 as an X before a T gate.

Finding 2: more T gates lower the reachable fidelity.

Table 4. Unchecked and best post-selected fidelity (greedy search, up to 4 checks).

T gates	p2 = 1%: unchecked → best	p2 = 3%: unchecked → best
0	0.854 → 0.937 (3 checks, 84.6% kept)	0.675 → 0.878 (3 checks, 64.4% kept)
2	0.848 → 0.909 (2 checks, 88.0% kept)	0.661 → 0.809 (4 checks, 60.9% kept)
4	0.845 → 0.914 (3 checks, 85.1% kept)	0.650 → 0.813 (4 checks, 60.1% kept)
8	0.835 → 0.878 (2 checks, 89.5% kept)	0.626 → 0.753 (4 checks, 62.7% kept)
At 1% noise, checks recover 83 thousandths of fidelity on the Clifford circuit but only 43 on the 8-T circuit. The checks that remain valid cannot reach the CX gates next to the T walls.

Show Image

Finding 3: the sweet spot moves.

Table 5. Number of checks that minimises ε.

T gates	p2 = 1%, N = 100	p2 = 1%, N = 10 000	p2 = 3%, N = 100	p2 = 3%, N = 10 000
0	3	3	3	3
2	2	2	3	4
4	3	3	4	4
8	1	2	4	4
Show Image Show Image

Low noise saturates early. At 1% error the fourth check never helps and usually hurts: on the 2-T circuit fidelity peaks at 0.909 with two checks and drops to 0.898 with four. Each extra check adds two-qubit gates that create about as many errors as it catches.
High noise rewards more checks. At 3% error there are many more errors to catch, so three or four checks are best in every case.
A small shot budget favours fewer checks. With eight T gates at 1% noise, the optimum drops from two checks to one when N falls from 10 000 to 100, because each discarded shot then costs more statistical error than the second check saves in bias.
In this regime the noise level moves the optimum more than the shot budget does, because the kept fraction stays above 60%. The shot-budget effect appears where the fidelity gains are smallest, which is exactly the heavily T-doped case.

3.4 What the game data shows
The game uses p2 = 2% and evaluates 60 random valid configurations per level to draw its Pareto chart (Results Lab).

Level	T gates	F, no checks	Sweet spot (N = 1000)	ε
1 Clean circuit	0	0.764	1 check, F = 0.837, 86.9% kept	0.197
2 First impurity	2	0.754	1 check, F = 0.788, 91.8% kept	0.246
3 T walls	4	0.748	1 check, F = 0.794, 90.3% kept	0.240
4 Magic overload	8	0.730	2 checks, F = 0.766, 85.7% kept	0.268
Random placements are much weaker than the greedy search above: among random configurations a single well-placed check is usually best, and adding random extra checks makes the score worse. This is the lesson the game is built around: placement beats quantity.

4. The game
Checkpoint is a web game (FastAPI backend, single-page HTML front end) built directly on the code above. Each player action calls the same functions used in the analysis.

Screen	What the player does
Primer	Learns detection vs. mitigation vs. correction
Missions	Four levels with 0, 2, 4 and 8 T gates, each with a 3-ancilla budget
Workbench	Picks an X, Y or Z check, clicks a start and an end cell on a qubit, sees it validated live against the T walls and the commutation rule, then presses Run on Qiskit
Results	Sees fidelity with and without checks, shots kept, overhead, and the score split into bias and statistical error
Results Lab	Compares their run with all computed configurations on the Pareto chart and the error-vs-checks curve, and changes N to watch the sweet spot move
Table 6. How each game rule maps to the physics.

Game rule	Physics
Ancilla budget	Space overhead of the spacetime code: one ancilla per check
Placing a check	Coherent Pauli check: controlled-P before a segment, controlled-U P U† after it, ancilla read in the X basis
Discarded shots	Post-selection on a non-trivial syndrome
T wall	T is diagonal, so only I or Z commute through it
Overlapping checks must commute	Anti-commuting checks disturb each other's syndrome
Shots kept	Sampling overhead = 1 / kept fraction
Score	ε = (1 − F) + 1/√(N · kept); points = 1000 × best ε ÷ player's ε
Every score shown in the game is computed by Qiskit Aer and cached by configuration together with the Qiskit version, noise level, shot count and seed, which the results screen displays.

5. Limitations
Detection does not repair errors. It only removes shots. Errors that commute with every check reach the kept shots undetected, which is why post-selected fidelity stays below 1.
Simulation only. All results come from Qiskit Aer with a synthetic depolarizing model on 4 qubits. Real devices have correlated, non-Markovian and crosstalk noise.
T-gate error is an assumption. On current IBM hardware T is a virtual rz(π/4) with essentially no error. Giving it an error rate models the fault-tolerant setting, where T gates are the expensive ones.
Connectivity is ignored. Checks are placed on an all-to-all device. On real hardware, long-range checks would need SWAP gates; this is the planned "Real hardware" level.
Statistical precision. Each configuration uses one simulation seed and 8192 shots, so differences in fidelity below about 0.01 are within shot noise. The trends above hold across T counts and noise levels, but individual neighbouring values (for example 0.937 vs. 0.935) should not be over-read.
Search is not exhaustive. Hand-made checks are weight-1 at their start and use a greedy search on a coarse time grid; better checks may exist. The game's Pareto data comes from 60 random configurations per level.
Score scale. The statistical term uses a scale constant of 1, a conservative proxy for the binomial standard error rather than a fitted value.
6. Reproducing the results
pip install -r requirements.txt
python run_phase1.py     # Table 1
python run_phase2.py     # Table 2, phase2_tradeoff.png
python run_phase3.py     # Tables 3–5, phase3_*.png
python precompute.py     # game data, Section 3.4
Software: Qiskit 2.5.2, qiskit-aer 0.17.2, qiskit-paulice 0.2.1, Python 3.13. All CSV files and figures are written to results/.

References
qiskit-paulice documentation, add_pauli_checks; and the method it implements: Martiel & Javadi, arXiv:2504.15725 (Supplemental Sec. II–VI).
Qiskit documentation: hellinger_fidelity, Pauli.evolve, Qiskit Aer SamplerV2.

