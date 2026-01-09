# The Marginal Utility of Force: Causal Analysis of Police Spending

![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)
![Type](https://img.shields.io/badge/Analysis-Causal_Inference-green.svg)
![Status](https://img.shields.io/badge/Status-Complete-success.svg)

> **Does specific investment in police funding causally reduce violent crime?**
> This project leverages Propensity Score Matching (PSM) and Doubly Robust Estimation to isolate the effect of "High Police Spending" on violent crime rates across 2,624 US cities.

---

## 📊 Executive Summary

**The Verdict (DiD Analysis 2015-2019)**: 
Using a **Difference-in-Differences** design, we find that cities with high police spending ($>\$440$/capita) experienced a **greater increase in violent crime** (+344 incidents/100k) from 2015 to 2019 compared to similar low-spending cities.

> **Result**: We find **no evidence of a deterrent effect** in this time period. The positive coefficient suggests that increased spending may be a *reaction* to rising crime trends (reverse causality) or that other structural factors outweigh police presence.

| Metric | Estimate | Significance | Interpretation |
|---|---|---|---|
| **DiD Estimator** | `+343.99` | `p < 0.10` | Causal effect on *change* in crime. |
| **Trend Direction** | Positive | - | Spending correlated with worsening trends. |

---

## 🔬 Methodology

We implement a **Longitudinal Causal Inference Pipeline** to control for time-invariant confounders (culture, geography).

```mermaid
graph LR
    A[Panel Data 2015 & 2019] --> B(Calculate Delta Y);
    B --> C{Propensity Score};
    C --> D[Match on 2019 Covariates];
    D --> E[Compare Trends];
    E --> F[Diff-in-Diff Estimator];
```

### 1. Design: Difference-in-Differences (DiD)
Instead of comparing raw crime rates, we compare the **change in crime** ($\Delta Y = Y_{2019} - Y_{2015}$) between treated and control cities.
```math
ATT = \Delta Y_{\text{Treated}} - \Delta Y_{\text{Control}}
```
This removes biases from cities that naturally have high baseline crime rates.

### 2. Assumptions & Limitations
> [!IMPORTANT]
> The validity of these results rests on the following key assumptions:

1.  **Parallel Trends**: We assume that, in the absence of the treatment (high spending), the crime rates in the Treated and Control groups would have evolved in parallel. *Limitation: If high-spending cities were already on a sharper upward trajectory pre-2015, this estimator is biased.*
2.  **No Anticipatory Effects**: We assume cities did not ramp up spending in 2019 in anticipation of a crime spike that had not yet occurred.
3.  **SUTVA (No Spillovers)**: Policing in one city is assumed not to displace crime to a neighboring control city.
4.  **Stable Composition**: We match based on 2019 characteristics, assuming the structural similarity holds back to 2015.

### 3. Matching Engine
We utilize **Scikit-Learn's NearestNeighbors** algorithm with a tight caliper to pair cities with similar *trends* potential based on demographics.

---

## 📂 Project Structure

Verified, clean, and functional architecture.

```
├── src/
│   ├── data/
│   │   ├── ingest.py       # Longitudinal data loaders (FiSC, FBI 2015/19)
│   │   └── preprocess.py   # Delta Calculation & Panel Merge
│   ├── models/
│   │   ├── psm.py          # Logistics Regression for Propensity Scores
│   │   └── matching.py     # Nearest Neighbor Matching Implementation
│   ├── main.py             # DiD Pipeline Orchestrator
├── data/raw/               # Input datasets (gitignored)
├── outputs/                # Final Reports (results.md)
└── requirements.txt        # Dependencies
```

---

## 🚀 Getting Started

This analysis uses **Modin** and **Ray** for parallelized data processing and **Statsmodels** for econometric analysis.

### Prerequisites
- Python 3.12+
- `uv` (recommended for fast environment management)

### Installation
```bash
# 1. Create Environment
uv venv --python 3.12
source .venv/bin/activate

# 2. Install Dependencies
uv pip install -r requirements.txt
```

### Running the Analysis
The pipeline is fully automated. It handles ingestion, matching, and report generation in one step.

```bash
export PYTHONPATH=$PYTHONPATH:.
python src/main.py
```

*Results will be generated in `outputs/results.md`.*

---

## 📈 Key Regression Insights

Our bias-adjusted DiD model components:

| Feature | Coefficient | Impact |
|---|---|---|
| **Treatment (High Spending)** | **+344.00** | **Positive Trend Divergence** |
| Population Density | +0.0002 | Negligible impact on trend |
| Median Income | -0.006 | Wealthier cities had better trends |
| Young Male Population | -2781.88 | Negative correlation with trend (Surprising) |

> **Analyst Note**: The negative coefficient for young males on the *trend* (Delta) suggests that while young populations predict high *levels* of crime, cities with high youth populations essentially "mean reverted" or improved more than others during this period, or that the demographic shift 2015-2019 was different. The primary finding remains that **police spending did not bend the crime curve downward** relative to the control group.
