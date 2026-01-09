import modin.pandas as pd
import pandas as pandas_std # For some sklearn compatibility if needed
import numpy as np
from sklearn.neighbors import NearestNeighbors
from typing import List, Dict, Any

class CausalMatcher:
    def __init__(self, caliper: float = 0.2):
        self.caliper = caliper
        self.matched_df = None
        
    def match_nearest_neighbor(self, df: pd.DataFrame, treatment_col: str, ps_col: str, n_neighbors: int = 1) -> pd.DataFrame:
        """
        Performs Nearest Neighbor matching on the Propensity Score (Logit scale advised).
        """
        # Convert PS to Logit scale for better matching properties
        # epsilon to avoid inf
        epsilon = 1e-10
        df["ps_logit"] = np.log((df[ps_col] + epsilon) / (1 - df[ps_col] + epsilon))
        
        treated = df[df[treatment_col] == 1].copy()
        control = df[df[treatment_col] == 0].copy()
        
        if self.matched_df is not None:
             return self.matched_df

        # Use Sklearn for Nearest Neighbor Matching
        # Logit Propensity Score matching with Caliper
        
        # We use sklearn NearestNeighbors with Euclidean distance on the 1D Logit PS
        # This is equivalent to Mahalanobis on 1D.
        
        nn = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
        nn.fit(control[["ps_logit"]])
        distances, indices = nn.kneighbors(treated[["ps_logit"]])
            
        
        # Filter by Caliper... (Rest of logic remains same)
        
        # Filter by Caliper (standard deviation of the propensity score)
        # Standard definition of caliper is 0.2 * SD of PS Logit
        caliper_val = self.caliper * df["ps_logit"].std()
        
        matched_data = []
        
        for i, (dist, idx) in enumerate(zip(distances, indices)):
            # If within caliper
            if dist[0] <= caliper_val:
                # Add Treated Unit
                t_row = treated.iloc[i].to_dict()
                t_row["match_id"] = i
                t_row["role"] = "Treated"
                matched_data.append(t_row)
                
                # Add Control Unit(s)
                # Note: indices are relative to the control dataframe
                for matched_idx in idx:
                    c_row = control.iloc[matched_idx].to_dict()
                    c_row["match_id"] = i
                    c_row["role"] = "Control"
                    matched_data.append(c_row)
                    
        self.matched_df = pd.DataFrame(matched_data)
        return self.matched_df

    def calculate_att(self, outcome_col: str) -> float:
        """
        Calculates simple ATT from matched data.
        """
        if self.matched_df is None or self.matched_df.empty:
            return np.nan
            
        treated = self.matched_df[self.matched_df["role"] == "Treated"]
        control = self.matched_df[self.matched_df["role"] == "Control"]
        
        # Group by match_id to handle potential many-to-one (though current logic is 1:1 if n=1)
        # Average control outcome per match
        control_means = control.groupby("match_id")[outcome_col].mean()
        treated_means = treated.set_index("match_id")[outcome_col]
        
        diffs = treated_means - control_means
        return diffs.mean()

    def bias_adjustment(self, formula: str, outcome_col: str) -> float:
        """
        Implements regression adjustment on the matched sample.
        Run E[Y|X, D=1] - E[Y|X, D=0] using the matched pairs.
        """
        import statsmodels.formula.api as smf
        
        if self.matched_df is None or self.matched_df.empty:
            return np.nan
        
        # Simple Bias Adjustment: Regress Outcome on Treatment + Covariates in the matched set
        # The coefficient on Treatment is the bias-adjusted ATT
        
        model = smf.ols(formula=formula, data=self.matched_df).fit()
        
        # Extract coefficient for treatment (assumed to be named 'treatment' or similar in formula)
        # We need to parse the treatment variable name from the formula or pass it
        # Assuming the treatment column name used in matching is present
        # Ideally, we return the whole summary, but for now just the param
        return model
