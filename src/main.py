import modin.pandas as pd
import ray
from src.data.preprocess import preprocess_pipeline, prepare_event_study_panel
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
        print(f"| FBI UCR | Table 8 | {cius['year'].nunique()} years (Crime Trends) |")
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
        
        # ============================================================
        # Section 6: Event-Study Analysis (Pre-Trends Validation)
        # ============================================================
        print("\n## 6. Event-Study Analysis (Pre-Trends Validation)")
        print("\n### Validating the Parallel Trends Assumption")
        print("\nThe DiD design assumes that treated and control cities would have followed parallel crime trajectories in the absence of the treatment. We test this by examining pre-treatment (pre-2015) trends.")
        
        try:
            from src.analysis.event_study import run_event_study, plot_event_study, format_event_study_table, summarize_pre_trends
            
            # Prepare full panel for event-study
            panel = prepare_event_study_panel(fisc, cius, acs)
            
            # Save processed data
            os.makedirs("data/processed", exist_ok=True)
            panel.to_csv("data/processed/event_study_panel.csv", index=False)
            print("Saved processed panel to data/processed/event_study_panel.csv")
            
            if not panel.empty and panel['year'].nunique() >= 2:
                avail_years = sorted(panel['year'].unique())
                print(f"\n**Panel Data**: {len(panel)} city-year observations")
                print(f"**Years Available**: {avail_years}")
                print(f"**Cities in Panel**: {panel['city'].nunique()}")
                
                # Check if we have pre-treatment periods
                pre_2015 = [y for y in avail_years if y < 2015]
                post_2015 = [y for y in avail_years if y > 2015]
                
                if len(pre_2015) >= 1:
                    print(f"\n**Pre-Treatment Years**: {pre_2015} (for testing parallel trends)")
                    print(f"**Post-Treatment Years**: {post_2015} (for dynamic effects)")
                    
                    # Run event-study regression
                    results = run_event_study(
                        panel, 
                        outcome='violent_crime_rate', 
                        treatment_year=2015, 
                        covariates=covariates
                    )
                    
                    if results['model'] is not None:
                        print("\n### Event-Study Coefficients")
                        print("\n*Coefficients show difference in violent crime rate between treated and control cities relative to the treatment year (2015). Pre-treatment coefficients should be ≈ 0 if parallel trends hold.*\n")
                        print(format_event_study_table(results['coefficients']))
                        
                        print(f"\n**Observations**: {results['n_obs']}")
                        print(f"**Cities**: {results['n_cities']}")
                        
                        print("\n### Pre-Trends Test")
                        print(summarize_pre_trends(results['coefficients'], results['pre_trends_p_value']))
                        
                        # Generate and embed the plot
                        plot_event_study(
                            results['coefficients'], 
                            output_path='outputs/event_study_plot.png',
                            title='Event-Study: Police Spending and Violent Crime',
                            treatment_year=2015
                        )
                        print("\n### Event-Study Coefficient Plot")
                        print("\n![Event-Study Coefficients](event_study_plot.png)")
                        print("\n*Figure shows treatment effect coefficients by event time. Pre-2015 coefficients test the parallel trends assumption. Confidence intervals crossing zero indicate no significant differential trend.*")
                    else:
                        print("\n> **Note**: Event-study model could not be estimated. Check data requirements.")
                else:
                    print("\n> **Note**: No pre-treatment years (before 2015) available in the data.")
                    print("> To run the pre-trends test, download FBI UCR Table 8 data for 2011-2014 and place in `data/raw/`.")
                    print("\n**Available years**: " + ", ".join(map(str, avail_years)))
            else:
                print("\n> **Note**: Insufficient panel data for event-study analysis.")
                print("> Ensure FBI crime data for multiple years is available in `data/raw/`.")
                
        except Exception as e:
            import traceback
            print(f"\n> **Error in event-study analysis**: {str(e)}")
            print(f"> Traceback: {traceback.format_exc()}", file=sys.stderr)

if __name__ == "__main__":
    main()
