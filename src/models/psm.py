import modin.pandas as pd
import numpy as np
import statsmodels.api as sm
from typing import List, Tuple

def estimate_propensity_score(df: pd.DataFrame, treatment: str, covariates: List[str]) -> pd.DataFrame:
    """
    Estimates the propensity score P(D=1|X) using Logistic Regression.
    Adds 'propensity_score' column to the dataframe.
    """
    # Define X and y
    # Add constant for intercept
    X = df[covariates]
    X = sm.add_constant(X)
    y = df[treatment]
    
    # Fit Logistic Regression
    model = sm.Logit(y, X).fit(disp=0)
    
    # Predict
    df["propensity_score"] = model.predict(X)
    
    return df

def trim_common_support(df: pd.DataFrame, threshold: float = 0.05) -> pd.DataFrame:
    """
    Removes observations with extreme propensity scores to ensure positivity.
    Keeps rows where threshold < PS < (1 - threshold).
    """
    mask = (df["propensity_score"] > threshold) & (df["propensity_score"] < (1 - threshold))
    return df[mask].copy()
