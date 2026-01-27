# Analysis Results: Marginal Utility of Police Force

## 1. Main DiD Analysis (2015 vs 2019)

### 1.1 Estimator: Doubly Robust (PSM + Regression)
**Specification**: ΔCrime ~ Treatment + Density + Income + Poverty + Youth (+ PSM weights)

| Variable | Coefficient | Std. Error | p-value | 95% CI |
|----------|-------------|------------|---------|--------|
| **Treatment** | **+343.99** | 185.26 | **0.067** | [-25.2, 713.2] |
| Intercept | +183.36 | 451.41 | 0.406 | [-716.3, 1083.0] |

**Interpretation**:
- **Positive Coefficient**: High spending cities saw *more* crime growth than low spending cities (+344 per 100k).
- **Significance**: Marginally significant (p < 0.10).
- **Conclusion**: No evidence of deterrent effect in this window. Likely reverse causality.

### 1.2 Sensitivity Analysis

| Check | Result | Interpretation |
|-------|--------|----------------|
| **Placebo (Property Crime)** | **+1181.84** | Strong positive effect suggests broad confounding (omitted variable causing all crime to rise). |
| **Rosenbaum Bounds** | **Γ = 1.5 (p=0.436)** | Results are sensitive to moderate hidden bias. A confounder increasing treatment odds by 50% could explain the result. |

---

## 2. Event-Study Analysis (2011 - 2019)

### 2.1 Specification
**Model**: Panel Fixed Effects (City + Year) with Leads and Lags.
**Reference Year**: 2015 (t=0)

### 2.2 Raw Coefficients

| Period | Year | Beta | Std.Err | P-value | Sig |
|--------|------|------|---------|---------|-----|
| t-4 | 2011 | -33.80 | 42.87 | 0.431 | |
| t-3 | 2012 | 9.07 | 44.67 | 0.839 | |
| t-2 | 2013 | -31.29 | 38.36 | 0.415 | |
| t-1 | 2014 | **-47.16** | 22.44 | **0.036** | * |
| t+0 | 2015 | REF | — | — | |
| t+1 | 2016 | -19.21 | 19.03 | 0.313 | |
| t+2 | 2017 | -25.57 | 31.21 | 0.413 | |
| t+3 | 2018 | **-89.31** | 34.46 | **0.010** | ** |
| t+4 | 2019 | **-85.46** | 33.12 | **0.010** | ** |

### 2.3 Interpretations

**Pre-Trends (Validity Check)**:
- **Violation in 2014**: The significant coefficient at t-1 (-47.16) indicates that high-spending cities were *already* deviating from the trend before 2015.
- **Implication**: The parallel trends assumption is marginally violated (F-test p=0.049). Causal claims should be cautious.

**Dynamic Effects (Post-Treatment)**:
- **Delayed Reduction**: In 2018 and 2019, coefficients turn significantly negative (~ -85 to -89).
- **Contrast**: This contradicts the simple 2015-2019 DiD (which found a positive effect). The Event Study controls for year-specific shocks better.
- **Conclusion**: There might be a long-run deterrent effect, but the pre-trend violation makes strict causal attribution difficult.

---

## 3. Summary Verdict

1. **Short Term (DiD)**: High spending correlates with *rising* crime (Reverse Causality likely).
2. **Robustness**: Results are fragile (fail Rosenbaum & Placebo tests).
3. **Long Term (Event Study)**: Potential reduction in later years, but validity is threatened by pre-treatment differences.
