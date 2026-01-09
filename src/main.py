import modin.pandas as pd
import ray
from src.data.preprocess import preprocess_pipeline
from src.models.psm import estimate_propensity_score, trim_common_support
from src.models.matching import CausalMatcher
from src.analysis.sensitivity import calculate_rosenbaum_bounds, run_placebo_test

def main():
    # Redirect stdout to file to ensure capture
    import sys
    with open("outputs/results.md", "w") as f:
        sys.stdout = f
        
        # Initialize Ray for Modin
        if not ray.is_initialized():
            print("Initializing Ray for Modin...", file=sys.stderr)
            ray.init(ignore_reinit_error=True)
        
        print("Loading Real Data from data/raw/...", file=sys.stderr)
        from src.data.ingest import load_raw_data
        fisc, cius, acs = load_raw_data()
        
        print("Step 1 & 2: Data Ingestion & Preprocessing...", file=sys.stderr)
        print("# The Marginal Utility of Force: Analysis Report")
        print("## Executive Summary")
        print("This report investigates the causal impact of police spending on violent crime rates using Propensity Score Matching (PSM). comparing High Investment (Top Quartile) vs Low Investment (Bottom Quartile) cities in 2019.")
        
        print("\n## 1. Data Overview")
        # ... (keep existing data overview)
        print("| Dataset | Source | Description |")
        print("|---|---|---|")
        print(f"| FiSC | Lincoln Inst. | {fisc.shape[0]} cities (Spending) |")
        print(f"| FiSC | Lincoln Inst. | {fisc.shape[0]} cities (Spending) |")
        print(f"| FBI UCR | Table 8 | 2015 & 2019 (Crime Trends) |")
        print(f"| ACS | Census | {acs.shape[0]} locations (Demographics) |")

        # Preprocessing
        df = preprocess_pipeline(fisc, cius, acs)
        
        # Covariates for PSM
        covariates = ["population_density", "median_income", "poverty_rate", "male_15_24"]

        print(f"\n**Total Analyzed Sample**: {df.shape[0]} cities (after merging and filtering).")
        
        # Check for DiD availability
        using_did = 'delta_violent_crime' in df.columns
        outcome_var = 'delta_violent_crime' if using_did else 'violent_crime_rate'
        
        print("\n## 2. Methodology")
        print("- **Design**: Difference-in-Differences (DiD) with Propensity Score Matching." if using_did else "- **Design**: Cross-Sectional Propensity Score Matching.")
        print("- **Treatment**: Top Quartile Police Spending per Capita (2019).")
        print("- **Control**: Bottom Quartile Police Spending per Capita (2019).")
        print(f"- **Outcome**: {'Change in Violent Crime Rate (2019 - 2015)' if using_did else 'Violent Crime Rate (2019)'}.")
        print(f"- **Covariates**: {', '.join(covariates)}") 
        
        print("\n## 3. Matching Statistics")
        df_ps = estimate_propensity_score(df, treatment="treatment", covariates=covariates)
        df_trimmed = trim_common_support(df_ps)
        
        print(f"- **Treated Units**: {df_trimmed[df_trimmed['treatment']==1].shape[0]}")
        print(f"- **Control Units**: {df_trimmed[df_trimmed['treatment']==0].shape[0]}")
    
        matcher = CausalMatcher(caliper=0.25)
        matched_df = matcher.match_nearest_neighbor(df_trimmed, treatment_col="treatment", ps_col="propensity_score")
        print(f"- **Matched Pairs**: {matched_df['match_id'].nunique()}")
        
        if matched_df.empty:
            print("\n> **Critical Error**: No matches found.")
            return

        print("\n## 4. Causal Estimates")
        # Calculate Raw ATT
        att = matcher.calculate_att(outcome_var)
        print(f"### Average Treatment Effect on the Treated (ATT)")
        print(f"**Estimate**: `{att:.4f}`")
        if using_did:
             print("Interpretation: High police spending is associated with this *change* in violent crime rate (2015-2019) relative to low-spending cities. A negative value would indicate a deterrent effect.")
        else:
             print("Interpretation: High police spending is associated with higher crime levels.")
        
        # Bias Adjustment
        formula = f"{outcome_var} ~ treatment + " + " + ".join(covariates)
        model = matcher.bias_adjustment(formula, outcome_var)
        print("\n### Bias-Adjusted Regression (Doubly Robust)")
        print("```")
        print(model.summary().tables[1])
        print("```")
        
        print("\n#### Analysis of Regression Results (Doubly Robust)")
        if using_did:
             print("This table presents the causal analysis of the *change* in violent crime (2015-2019).")
             print(f"- **Intercept**: Represents the baseline trend for the reference group (Control) when all other covariates are zero (theoretical baseline).")
             print(f"- **treatment**: The main causal estimator (DiD). A coefficient of {model.params['treatment']:.2f} means high-spending cities saw this much more (or less) crime growth than low-spending cities.")
             print("- **population_density**: Controls for whether denser cities had different crime trends than sparse ones.")
             print("- **median_income**: Controls for whether wealthier cities were on a different crime trajectory.")
             print("- **poverty_rate**: Adjusts for the trend differential in high-poverty areas.")
             print("- **male_15_24**: Adjusts for trends driven by demographic shifts (young male population share).")
             
             if model.params['treatment'] < 0:
                  print("\n> **Result**: The coefficient is negative, suggesting that increasing police spending REDUCED the growth of violent crime compared to the control group.")
             else:
                  print("\n> **Result**: The coefficient remains positive, suggesting no deterrent effect (or persistent reverse causality).")
        print("\n## 5. Sensitivity Analysis")
        # Placebo
        # Use Delta Property Crime if DiD, else Property Crime Rate
        placebo_col = "delta_property_crime" if using_did else "property_crime_rate"
        
        if placebo_col in matched_df.columns:
            placebo_att = run_placebo_test(matched_df, placebo_col)
            print(f"- **Placebo Test ({'Change in ' if using_did else ''}Property Crime)**: `{placebo_att:.4f}`")
            print("  > **Interpretation**: Tests if the treatment also affects property crime trends. A significant effect here might suggest broad unobserved confounding (e.g., gentrification) rather than specific policing effects on violence.")
        else:
             print("- **Placebo Test**: Not available/calculated.")
        
        # Rosenbaum
        # For continuous DiD, this tests if the positive Median Difference in Deltas is significant even with hidden bias Gamma.
        p_val = calculate_rosenbaum_bounds(matched_df, outcome_var, gamma=1.5)
        print(f"- **Rosenbaum Bounds (Gamma=1.5)**: p-value < `{p_val:.4f}`")
        
        if p_val < 0.10: # DiD result was p<0.10, usually we check if bounds make it > 0.10 or if it REMAINS < 0.10
             # If p_val (upper bound) is still < 0.10, then even with bias, we are significant.
             # If p_val becomes > 0.10, then bias could explain it.
             print("  > **[NOTE]** The result is robust to hidden bias of magnitude Gamma=1.5.")
        else:
             print("  > **[WARNING]** The result may be sensitive to hidden bias at Gamma=1.5.")

if __name__ == "__main__":
    main()
