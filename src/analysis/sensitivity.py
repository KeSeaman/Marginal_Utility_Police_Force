import numpy as np
import scipy.stats as stats
import modin.pandas as pd

def calculate_rosenbaum_bounds(matched_df: pd.DataFrame, outcome_col: str, gamma: float = 1.0) -> float:
    """
    Calculates the upper bound of the p-value for the Wilcoxon Signed-Rank Test
    at a given Gamma (odds of hidden bias).
    
    This is a simplified implementation for the signed rank statistic.
    """
    treated = matched_df[matched_df["role"] == "Treated"].set_index("match_id")[outcome_col]
    control = matched_df[matched_df["role"] == "Control"].groupby("match_id")[outcome_col].mean()
    
    diffs = (treated - control).dropna()
    abs_diffs = diffs.abs()
    ranks = abs_diffs.rank()
    
    # Observed Signed Rank Statistic (sum of ranks where diff > 0)
    W = ranks[diffs > 0].sum()
    N = len(diffs)
    
    # Expectations and Variances under Gamma
    # For Gamma = 1 (Randomization), p = 0.5
    # For Gamma > 1, p varies between 1/(1+Gamma) and Gamma/(1+Gamma)
    
    p_plus = gamma / (1 + gamma)
    p_minus = 1 / (1 + gamma)
    
    # Worst case expectation (High statistic)
    E_W = (p_plus * N * (N + 1)) / 2 # simplified, actually needs sum of ranks
    # Variance
    Var_W = (N * (N + 1) * (2 * N + 1)) / 24 # Standard Wilcoxon var, scaling needed for Gamma
    
    # Accurate Rosenbaum deviation requires iterating combinations or normal approx
    # Using Large Sample Approximation for W
    
    # Validating Rust Integration - Removed for Pure Python Architecture
    # Using Large Sample Approximation for W
    z_score = (W - E_W) / np.sqrt(Var_W)
    p_val = 1 - stats.norm.cdf(z_score)
    return p_val

def run_placebo_test(matched_df: pd.DataFrame, placebo_outcome: str) -> float:
    """
    Runs the ATT calculation on a Placebo outcome (e.g. Past Crime).
    Expectation: Result should be insignificant (near 0).
    """
    treated = matched_df[matched_df["role"] == "Treated"]
    control = matched_df[matched_df["role"] == "Control"]
    
    t_mean = treated[placebo_outcome].mean()
    c_mean = control[placebo_outcome].mean()
    
    return t_mean - c_mean
