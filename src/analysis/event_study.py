"""
Event-Study / Pre-Trends Analysis for DiD Validation

This module implements a leads-and-lags regression to test the parallel trends
assumption required for valid Difference-in-Differences inference.

Reference:
- Angrist & Pischke (2009) "Mostly Harmless Econometrics"
- Autor (2003) "Outsourcing at Will"
"""

import modin.pandas as pd
import numpy as np
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt
from typing import Dict, List, Optional
import sys


def create_event_time_indicators(df: pd.DataFrame, 
                                  treatment_year: int = 2015,
                                  year_col: str = 'year',
                                  treatment_col: str = 'treatment') -> pd.DataFrame:
    """
    Creates event-time interaction dummies for leads-and-lags regression.
    Omits the treatment year (t=0) as reference.
    
    Parameters:
        df: Panel dataframe with year and treatment columns
        treatment_year: The year treatment begins (omitted as reference)
        year_col: Name of year column
        treatment_col: Name of treatment indicator column
    
    Returns:
        DataFrame with added event-time dummy columns
    """
    df = df.copy()
    df['event_time'] = df[year_col] - treatment_year
    
    # Create interaction dummies (exclude t=0)
    event_times = sorted(df['event_time'].unique())
    for t in event_times:
        if t != 0:  # Omit reference period
            col_name = f'treat_x_t{t:+d}'.replace('+', 'p').replace('-', 'm')
            df[col_name] = ((df[treatment_col] == 1) & (df['event_time'] == t)).astype(int)
    
    return df


def run_event_study(df: pd.DataFrame,
                    outcome: str = 'violent_crime_rate',
                    treatment_year: int = 2015,
                    covariates: Optional[List[str]] = None,
                    cluster_var: str = 'city') -> Dict:
    """
    Runs leads-and-lags event-study regression with city and year fixed effects.
    
    Uses the Two-Way Fixed Effects (TWFE) specification:
    Y_it = α_i + λ_t + Σ_k β_k × (Treated_i × I(t=k)) + X_it'γ + ε_it
    
    Parameters:
        df: Panel dataframe with city-year observations
        outcome: Outcome variable name
        treatment_year: Reference year (omitted)
        covariates: List of covariate names to include
        cluster_var: Variable to cluster standard errors on
    
    Returns:
        dict with 'model', 'coefficients', 'pre_trends_p_value'
    """
    df = create_event_time_indicators(df, treatment_year)
    
    # Get event-time variable names
    event_vars = [c for c in df.columns if c.startswith('treat_x_t')]
    
    if len(event_vars) == 0:
        print("Warning: No event-time variables created. Check data.", file=sys.stderr)
        return {'model': None, 'coefficients': pd.DataFrame(), 'pre_trends_p_value': None}
    
    # Sort for consistent ordering
    event_vars = sorted(event_vars, key=lambda x: int(x.replace('treat_x_t', '').replace('p', '+').replace('m', '-')))
    
    # Build formula
    fe_formula = f"{outcome} ~ " + " + ".join(event_vars)
    
    if covariates:
        # Only include covariates that exist in df
        valid_covariates = [c for c in covariates if c in df.columns]
        if valid_covariates:
            fe_formula += " + " + " + ".join(valid_covariates)
    
    # Add fixed effects using C() notation for categorical
    # Create city_id for fixed effects (city+state unique combo)
    df['city_id'] = df['city'] + '_' + df['state']
    fe_formula += " + C(city_id) + C(year)"
    
    print(f"Estimating event-study model...", file=sys.stderr)
    print(f"Formula: {fe_formula[:100]}...", file=sys.stderr)
    
    # Estimate with clustered standard errors
    try:
        model = smf.ols(fe_formula, data=df).fit(
            cov_type='cluster', 
            cov_kwds={'groups': df[cluster_var]}
        )
    except Exception as e:
        print(f"Error fitting model: {e}", file=sys.stderr)
        # Fallback to robust SE
        model = smf.ols(fe_formula, data=df).fit(cov_type='HC1')
    
    # Extract pre-period variables for F-test
    pre_vars = [v for v in event_vars if 'm' in v]  # 'm' indicates negative (pre) period
    
    # F-test for pre-trends (joint F-test that all pre-period coeffs = 0)
    pre_trends_p = None
    if len(pre_vars) > 1:
        try:
            # Construct hypothesis string: "var1 = var2 = ... = 0"
            hypothesis = " = ".join(pre_vars) + " = 0"
            f_test = model.f_test(hypothesis)
            pre_trends_p = float(f_test.pvalue)
        except Exception as e:
            print(f"F-test failed: {e}", file=sys.stderr)
            # Alternative: Check if all pre-period CIs include 0
            all_include_zero = True
            for var in pre_vars:
                if var in model.params:
                    ci = model.conf_int().loc[var]
                    if not (ci[0] <= 0 <= ci[1]):
                        all_include_zero = False
            pre_trends_p = 0.5 if all_include_zero else 0.05  # Rough indicator
    
    # Build coefficient table
    coef_records = []
    
    for var in event_vars:
        # Parse event time from variable name
        t_str = var.replace('treat_x_t', '').replace('p', '+').replace('m', '-')
        t = int(t_str)
        
        if var in model.params:
            coef_records.append({
                'event_time': t,
                'coefficient': model.params[var],
                'std_error': model.bse[var],
                'ci_lower': model.conf_int().loc[var, 0],
                'ci_upper': model.conf_int().loc[var, 1],
                'p_value': model.pvalues[var]
            })
    
    # Add reference period (t=0)
    coef_records.append({
        'event_time': 0,
        'coefficient': 0.0,
        'std_error': 0.0,
        'ci_lower': 0.0,
        'ci_upper': 0.0,
        'p_value': np.nan
    })
    
    coef_df = pd.DataFrame(coef_records).sort_values('event_time').reset_index(drop=True)
    
    return {
        'model': model,
        'coefficients': coef_df,
        'pre_trends_p_value': pre_trends_p,
        'n_obs': int(model.nobs),
        'n_cities': df['city_id'].nunique()
    }


def plot_event_study(coef_df: pd.DataFrame, 
                     output_path: str = 'outputs/event_study_plot.png',
                     title: str = 'Event-Study Coefficients',
                     treatment_year: int = 2015) -> None:
    """
    Generates the classic event-study coefficient plot with confidence intervals.
    
    Parameters:
        coef_df: DataFrame from run_event_study with coefficient estimates
        output_path: Path to save the plot
        title: Plot title
        treatment_year: Year of treatment (for labeling)
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Reference lines
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.6, linewidth=1)
    ax.axvline(x=0, color='#e11d48', linestyle=':', alpha=0.8, linewidth=2, 
               label=f'Treatment Year ({treatment_year})')
    
    # Shade pre-treatment region
    ax.axvspan(coef_df['event_time'].min() - 0.5, -0.5, alpha=0.1, color='#3b82f6', 
               label='Pre-Treatment')
    
    # Plot coefficients with CI
    ax.errorbar(coef_df['event_time'], 
                coef_df['coefficient'],
                yerr=[coef_df['coefficient'] - coef_df['ci_lower'],
                      coef_df['ci_upper'] - coef_df['coefficient']],
                fmt='o', capsize=5, capthick=2, markersize=10, 
                color='#2563eb', ecolor='#93c5fd', markeredgecolor='white',
                markeredgewidth=1.5, linewidth=2)
    
    # Fill CI area
    ax.fill_between(coef_df['event_time'], 
                     coef_df['ci_lower'], 
                     coef_df['ci_upper'],
                     alpha=0.15, color='#2563eb', step='mid')
    
    # Styling
    ax.set_xlabel('Event Time (Years Relative to Treatment)', fontsize=12, fontweight='medium')
    ax.set_ylabel('Treatment Effect\n(Violent Crime Rate per 100k)', fontsize=12, fontweight='medium')
    ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
    ax.legend(loc='upper left', framealpha=0.9)
    ax.grid(alpha=0.3, linestyle='-', linewidth=0.5)
    
    # X-axis labels
    ax.set_xticks(coef_df['event_time'].values)
    x_labels = []
    for t in coef_df['event_time']:
        year = treatment_year + int(t)
        x_labels.append(f"t{int(t):+d}\n({year})")
    ax.set_xticklabels(x_labels, fontsize=9)
    
    # Mark reference point
    ax.scatter([0], [0], s=150, color='#e11d48', marker='D', zorder=10, 
               label='Reference (t=0)', edgecolor='white', linewidth=2)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"Event-study plot saved to {output_path}", file=sys.stderr)


def format_event_study_table(coef_df: pd.DataFrame, treatment_year: int = 2015) -> str:
    """
    Formats coefficient table as markdown for report.
    
    Parameters:
        coef_df: DataFrame with coefficient estimates
        treatment_year: Reference year for calculating actual years
    
    Returns:
        Markdown-formatted table string
    """
    lines = [
        "| Event Time | Year | Coefficient | Std. Error | 95% CI | p-value |",
        "|:-----------|:----:|------------:|-----------:|:------:|:-------:|"
    ]
    
    for _, row in coef_df.iterrows():
        t = int(row['event_time'])
        year = treatment_year + t
        
        # Format values
        coef = f"{row['coefficient']:.2f}"
        se = f"{row['std_error']:.2f}"
        ci = f"[{row['ci_lower']:.1f}, {row['ci_upper']:.1f}]"
        
        if np.isnan(row['p_value']):
            pval = "(ref)"
        else:
            pval = f"{row['p_value']:.3f}"
            # Add significance stars
            if row['p_value'] < 0.01:
                pval += "***"
            elif row['p_value'] < 0.05:
                pval += "**"
            elif row['p_value'] < 0.10:
                pval += "*"
        
        # Highlight pre-trend periods (should be ~0)
        if t < 0:
            # Bold pre-period for emphasis
            lines.append(f"| **t{t:+d}** | **{year}** | **{coef}** | {se} | {ci} | {pval} |")
        elif t == 0:
            lines.append(f"| t{t:+d} | {year} | {coef} | — | — | {pval} |")
        else:
            lines.append(f"| t{t:+d} | {year} | {coef} | {se} | {ci} | {pval} |")
    
    return "\n".join(lines)


def summarize_pre_trends(coef_df: pd.DataFrame, pre_trends_p: Optional[float]) -> str:
    """
    Generates a textual summary of the pre-trends test results.
    
    Parameters:
        coef_df: Coefficient dataframe
        pre_trends_p: P-value from joint F-test
    
    Returns:
        Markdown-formatted summary string
    """
    pre_coefs = coef_df[coef_df['event_time'] < 0]
    
    if len(pre_coefs) == 0:
        return "> **Note**: No pre-treatment periods available for pre-trends test."
    
    # Check if all CIs include zero
    all_include_zero = True
    for _, row in pre_coefs.iterrows():
        if not (row['ci_lower'] <= 0 <= row['ci_upper']):
            all_include_zero = False
            break
    
    lines = []
    
    if pre_trends_p is not None:
        lines.append(f"**Pre-Trends Joint F-Test**: p = {pre_trends_p:.3f}")
        lines.append("")
        
        if pre_trends_p > 0.10:
            lines.append("> ✓ **PASS**: Cannot reject the null hypothesis of no differential pre-trends (p > 0.10).")
            lines.append("> This provides empirical support for the parallel trends assumption required for valid DiD inference.")
        else:
            lines.append("> ⚠ **WARNING**: Pre-trends test suggests possible violations (p < 0.10).")
            lines.append("> Consider investigating which periods drive this result and whether it affects causal interpretation.")
    else:
        lines.append("**Pre-Trends Visual Assessment**:")
        lines.append("")
        
        if all_include_zero:
            lines.append("> ✓ **PASS**: All pre-treatment confidence intervals include zero.")
            lines.append("> Visual evidence supports the parallel trends assumption.")
        else:
            lines.append("> ⚠ **CAUTION**: Some pre-treatment coefficients are significantly different from zero.")
    
    return "\n".join(lines)
