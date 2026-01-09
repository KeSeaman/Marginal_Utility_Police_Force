# The Marginal Utility of Force: Analysis Report
## Executive Summary
This report investigates the causal impact of police spending on violent crime rates using Propensity Score Matching (PSM). comparing High Investment (Top Quartile) vs Low Investment (Bottom Quartile) cities in 2019.

## 1. Data Overview
| Dataset | Source | Description |
|---|---|---|
| FiSC | Lincoln Inst. | 218 cities (Spending) |
| FiSC | Lincoln Inst. | 218 cities (Spending) |
| FBI UCR | Table 8 | 2015 & 2019 (Crime Trends) |
| ACS | Census | 29318 locations (Demographics) |

**Total Analyzed Sample**: 148 cities (after merging and filtering).

## 2. Methodology
- **Design**: Difference-in-Differences (DiD) with Propensity Score Matching.
- **Treatment**: Top Quartile Police Spending per Capita (2019).
- **Control**: Bottom Quartile Police Spending per Capita (2019).
- **Outcome**: Change in Violent Crime Rate (2019 - 2015).
- **Covariates**: population_density, median_income, poverty_rate, male_15_24

## 3. Matching Statistics
- **Treated Units**: 72
- **Control Units**: 72
- **Matched Pairs**: 58

## 4. Causal Estimates
### Average Treatment Effect on the Treated (ATT)
**Estimate**: `262.1900`
Interpretation: High police spending is associated with this *change* in violent crime rate (2015-2019) relative to low-spending cities. A negative value would indicate a deterrent effect.

### Bias-Adjusted Regression (Doubly Robust)
```
======================================================================================
                         coef    std err          t      P>|t|      [0.025      0.975]
--------------------------------------------------------------------------------------
Intercept            183.3550    451.411      0.406      0.686    -716.305    1083.015
treatment            343.9988    185.264      1.857      0.067     -25.231     713.229
population_density     0.0002      0.001      0.120      0.905      -0.003       0.003
median_income         -0.0063      0.005     -1.172      0.245      -0.017       0.004
poverty_rate         769.9788   1762.672      0.437      0.664   -2743.021    4282.979
male_15_24         -2781.8783   2025.243     -1.374      0.174   -6818.182    1254.425
======================================================================================
```

#### Analysis of Regression Results (Doubly Robust)
This table presents the causal analysis of the *change* in violent crime (2015-2019).
- **Intercept**: Represents the baseline trend for the reference group (Control) when all other covariates are zero (theoretical baseline).
- **treatment**: The main causal estimator (DiD). A coefficient of 344.00 means high-spending cities saw this much more (or less) crime growth than low-spending cities.
- **population_density**: Controls for whether denser cities had different crime trends than sparse ones.
- **median_income**: Controls for whether wealthier cities were on a different crime trajectory.
- **poverty_rate**: Adjusts for the trend differential in high-poverty areas.
- **male_15_24**: Adjusts for trends driven by demographic shifts (young male population share).

> **Result**: The coefficient remains positive, suggesting no deterrent effect (or persistent reverse causality).

## 5. Sensitivity Analysis
- **Placebo Test (Change in Property Crime)**: `1181.8379`
  > **Interpretation**: Tests if the treatment also affects property crime trends. A significant effect here might suggest broad unobserved confounding (e.g., gentrification) rather than specific policing effects on violence.
- **Rosenbaum Bounds (Gamma=1.5)**: p-value < `0.4359`
  > **[WARNING]** The result may be sensitive to hidden bias at Gamma=1.5.
