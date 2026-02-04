# Analysis Results: Marginal Utility of Police Force

## 1. Main DiD Analysis (2015 vs 2019)

### 1.1 Estimator: Doubly Robust (PSM + Regression)
**Specification**: ΔCrime ~ Treatment + Density + Income + Poverty + Youth (+ PSM weights)

| Variable | Coefficient | Std. Error | p-value | 95% CI |
|----------|-------------|------------|---------|--------|
| **Treatment** | **+343.99** | 185.26 | **0.067** | [-25.2, 713.2] |
| Intercept | +183.36 | 451.41 | 0.406 | [-716.3, 1083.0] |

**Interpretation**:
- **Positive Coefficient**: High spending cities saw *more* crime growth (+344 per 100k).
- **Likely Confounder**: Reverse causality or economic booms.

### 1.2 Sensitivity Analysis

| Check | Result | Interpretation |
|-------|--------|----------------|
| **Placebo (Property Crime)** | **+1181.84** | Large positive effect suggests **Gentrification/Economic Boom** confounding. New wealth funds police but also attracts theft. |
| **Rosenbaum Bounds** | **Γ = 1.5 (p=0.436)** | Results are sensitive to moderate hidden bias. |

---

## 2. Event-Study Analysis (2011 - 2019)

### 2.1 Raw Coefficients (Reference 2015)

| Period | Year | Beta | Std.Err | Sig |
|--------|------|------|---------|-----|
| t-4 | 2011 | -33.80 | 42.87 | |
| t-3 | 2012 | 9.07 | 44.67 | |
| t-2 | 2013 | -31.29 | 38.36 | |
| t-1 | 2014 | **-47.16** | 22.44 | * |
| t+0 | 2015 | REF | — | |
| t+1 | 2016 | -19.21 | 19.03 | |
| t+2 | 2017 | -25.57 | 31.21 | |
| t+3 | 2018 | **-89.31** | 34.46 | ** |
| t+4 | 2019 | **-85.46** | 33.12 | ** |

### 2.2 Short Interpretations
1.  **Pre-Trends**: Violation in 2014 suggests high-spending cities were already on a different trajectory.
2.  **Long-Term**: 2018/19 coefficients are negative, hinting at delayed benefits, but confounding makes this uncertain.

---

## 3. Summary Verdict
**Findings are likely confounded by Gentrification.** The massive placebo effect on property crime implies that "High Spending" cities are simply wealthier/booming cities, which experience naturally higher property crime rates and police budgets simultaneously. Without controlling for property values, causal claims remain weak.
