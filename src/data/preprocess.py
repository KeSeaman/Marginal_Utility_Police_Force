import modin.pandas as pd
import numpy as np
import sys
from typing import Optional, List
from src.data.functional import pipe

def load_and_merge(fisc: pd.DataFrame, cius: pd.DataFrame, acs: pd.DataFrame) -> pd.DataFrame:
    """
    Merges the three datasets on matching City and Year.
    """
    # Functional merge pipeline
    # 1. Merge FiSC and FBI (Longitudinal)
    # We need both 2015 and 2019 to exist for a city to do DiD.
    # Inner join on city/year will give us rows for both years if they exist in both.
    df_panel = fisc.merge(cius, on=["city", "year"], how="inner")
    
    # 2. Calculate Delta Crime (2019 - 2015)
    # Pivot or Self-Join
    # Let's filter for just the years we care about to simplify
    df_panel = df_panel[df_panel['year'].isin([2015, 2019])].copy()
    
    # Check if we have enough data
    counts = df_panel['city'].value_counts()
    valid_cities = counts[counts == 2].index # Cities present in BOTH years
    df_panel = df_panel[df_panel['city'].isin(valid_cities)]
    
    if df_panel.empty:
        # Fallback for 2019 only if no historical matches (e.g. if 2015 load failed)
        print("WARNING: No overlapping cities 2015-2019. DiD impossible. Reverting to Cross-Section.", file=sys.stderr)
        merged_1 = fisc.merge(cius, on=["city", "year"], how="inner")
        merged = merged_1.merge(acs, on=["city", "year"], how="inner")
        # Add dummy delta
        if not 'violent_crime_rate' in merged.columns:
             # handle case where merge failed
             return pd.DataFrame()
        merged['delta_violent_crime'] = 0 
        return merged

    # Compute Delta
    # Sort and Shift
    df_panel = df_panel.sort_values(by=['city', 'year'])
    df_panel['violent_crime_lag'] = df_panel.groupby('city')['violent_crime_rate'].shift(1) # 2015 value shifts to 2019 row
    df_panel['delta_violent_crime'] = df_panel['violent_crime_rate'] - df_panel['violent_crime_lag']
    
    # Add Property Delta (Placebo)
    df_panel['property_crime_lag'] = df_panel.groupby('city')['property_crime_rate'].shift(1)
    df_panel['delta_property_crime'] = df_panel['property_crime_rate'] - df_panel['property_crime_lag']
    
    # Keep only 2019 rows (which now have the Delta)
    df_2019 = df_panel[df_panel['year'] == 2019].copy()
    
    # 3. Merge ACS (2019 only)
    merged = df_2019.merge(acs, on=["city", "year"], how="inner")
    
    return merged

def create_lagged_variables(df: pd.DataFrame, lag_vars: List[str], lags: int = 1) -> pd.DataFrame:
    """
    Creates lagged versions of specified variables by City.
    """
    # Ensure ordered by year
    df = df.sort_values(by=["city", "year"])
    
    for var in lag_vars:
        df[f"{var}_lag_{lags}"] = df.groupby("city")[var].shift(lags)
        
    return df.dropna() # Drop rows without valid lags

def binarize_treatment(df: pd.DataFrame, treatment_col: str = "police_spending") -> pd.DataFrame:
    """
    Converts continuous spending into Binary Treatment groups (Top vs Bottom Quartile).
    Drops middle quartiles.
    """
    q1 = df[treatment_col].quantile(0.25)
    q4 = df[treatment_col].quantile(0.75)
    
    def assign_group(val):
        if val >= q4:
            return 1 # High Investment
        elif val <= q1:
            return 0 # Low Investment
        else:
            return -1 # Middle (Exclude)
            
    # Apply logic
    df["treatment"] = df[treatment_col].apply(assign_group)
    
    # Filter
    final_df = df[df["treatment"] != -1].copy()
    return final_df
    
def preprocess_pipeline(fisc: pd.DataFrame, cius: pd.DataFrame, acs: pd.DataFrame) -> pd.DataFrame:
    """
    Full preprocessing pipeline.
    """
    df = load_and_merge(fisc, cius, acs)
    
    # Calculate lags (e.g. valid data for 2019 relies on 2018/2015 history)
    # Since we only have 2019 data provided by the user, we cannot calculate lags.
    # We will skip lag generation for this run.
    
    # df_lagged = create_lagged_variables(df, ["violent_crime_rate"], lags=1)
    
    # Just take the year we have (2019)
    # latest_year = df["year"].max()
    # df_final_year = df[df["year"] == latest_year].copy()
    
    # Since ingest already filters for 2019, df is already the final cross section
    final_df = binarize_treatment(df)
    return final_df
    

def prepare_event_study_panel(fisc: pd.DataFrame, 
                               cius: pd.DataFrame, 
                               acs: pd.DataFrame) -> pd.DataFrame:
    """
    Prepares full panel data (all available years) for event-study analysis.
    Unlike DiD preprocessing, keeps all years and does city-year merges.
    
    Treatment is assigned based on 2019 spending levels and applied backward
    to all years for the event-study specification.
    
    Parameters:
        fisc: Fiscal data with police spending
        cius: FBI crime data (multi-year panel)
        acs: ACS demographics data
    
    Returns:
        Panel DataFrame ready for event-study regression
    """
    import sys
    
    # 1. Assign treatment based on 2019 spending levels
    fisc_2019 = fisc[fisc['year'] == 2019].copy() if 'year' in fisc.columns else fisc.copy()
    
    if fisc_2019.empty:
        print("Warning: No 2019 FiSC data for treatment assignment", file=sys.stderr)
        return pd.DataFrame()
    
    q1 = fisc_2019['police_spending'].quantile(0.25)
    q4 = fisc_2019['police_spending'].quantile(0.75)
    
    def assign_treatment(val):
        if val >= q4:
            return 1  # High spending
        elif val <= q1:
            return 0  # Low spending
        else:
            return -1  # Exclude (middle 50%)
    
    fisc_2019['treatment'] = fisc_2019['police_spending'].apply(assign_treatment)
    fisc_treat = fisc_2019[fisc_2019['treatment'] != -1][['city', 'state', 'treatment', 'police_spending']].copy()
    
    print(f"Treatment assignment: {(fisc_treat['treatment'] == 1).sum()} treated, {(fisc_treat['treatment'] == 0).sum()} control", file=sys.stderr)
    
    # 2. Merge treatment assignment with full crime panel
    # cius contains all years of crime data
    panel = cius.merge(fisc_treat, on=['city', 'state'], how='inner')
    
    if panel.empty:
        print("Warning: No cities matched between FBI and FiSC data", file=sys.stderr)
        return pd.DataFrame()
    
    print(f"Panel after FBI-FiSC merge: {len(panel)} obs, years: {sorted(panel['year'].unique())}", file=sys.stderr)
    
    # 3. Add demographics (using 2019 as proxy for all years - standard assumption)
    acs_2019 = acs[acs['year'] == 2019].copy() if 'year' in acs.columns else acs.copy()
    
    # Drop year column from ACS before merge to avoid conflict
    acs_cols = ['city', 'state', 'population_density', 'median_income', 'poverty_rate', 'male_15_24']
    acs_merge = acs_2019[[c for c in acs_cols if c in acs_2019.columns]].copy()
    
    panel = panel.merge(acs_merge, on=['city', 'state'], how='inner')
    
    print(f"Panel after ACS merge: {len(panel)} obs across {panel['city'].nunique()} cities", file=sys.stderr)
    
    # 4. Create balanced panel (cities present in all years)
    # This is optional - unbalanced panel is also valid with FE
    year_counts = panel.groupby(['city', 'state'])['year'].nunique()
    max_years = year_counts.max()
    
    # Keep cities with at least 2 years (minimum for panel)
    valid_cities = year_counts[year_counts >= 2].reset_index()[['city', 'state']]
    panel = panel.merge(valid_cities, on=['city', 'state'], how='inner')
    
    print(f"Final panel: {len(panel)} obs, {panel['city'].nunique()} cities, {panel['year'].nunique()} years", file=sys.stderr)
    
    return panel
