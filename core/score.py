# core/score.py
import numpy as np


def estimation_error(f_ps, keep, shot_budget):
    """Total error of estimating with a fixed shot budget N:
    bias left by undetected errors + statistical error from the shots kept."""
    if keep <= 0 or np.isnan(f_ps):
        return float("inf")
    return (1.0 - f_ps) + 1.0 / np.sqrt(shot_budget * keep)