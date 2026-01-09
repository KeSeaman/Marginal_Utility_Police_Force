import pandas as pd
import os
import sys
import numpy as np
import re

# US State Abbreviation Mapping
us_state_abbrev = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
    'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
    'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
    'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS',
    'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH',
    'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
    'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
    'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN',
    'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA',
    'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
    'District of Columbia': 'DC'
}

def clean_city_name(name):
    """
    Standardizes city names:
    - Removes ' city', ' town', ' village' suffixes (common in ACS).
    - Removes formatting footnotes like '3' in FBI data.
    """
    name = str(name).strip()
    # Remove footnotes (digits at end)
    name = re.sub(r'\d+$', '', name).strip()
    
    # Remove common suffixes (case insensitive)
    lower_name = name.lower()
    if lower_name.endswith(" city"):
        name = name[:-5]
    elif lower_name.endswith(" town"):
        name = name[:-5]
    elif lower_name.endswith(" village"):
        name = name[:-8]
        
    return name.strip()

def load_raw_data():
    """
    Loads and normalizes raw datasets.
    Returns DataFrames with columns: ['city', 'state', 'year', ...]
    """
    # 1. Load FiSC
    fisc_path = "data/raw/FiSC_Full_Dataset_2022_Update.xlsx"
    if not os.path.exists(fisc_path):
         raise FileNotFoundError(f"FiSC data not found at {fisc_path}")

    # Load Full Excel (Robust Sheet/Header Search)
    print("Loading FiSC...", file=sys.stderr)
    xl = pd.ExcelFile(fisc_path, engine='openpyxl')
    
    # Sheet Selection
    target_sheet = xl.sheet_names[0]
    for s in xl.sheet_names:
        if "data" in s.lower() or "estimates" in s.lower():
            target_sheet = s
            break
    if target_sheet == xl.sheet_names[0] and len(xl.sheet_names) > 1 and "about" in target_sheet.lower():
        target_sheet = xl.sheet_names[1]
    
    # Header Search
    df_head = pd.read_excel(fisc_path, sheet_name=target_sheet, engine='openpyxl', header=None, nrows=20)
    header_idx = 0
    found_header = False
    for i, row in df_head.iterrows():
        row_vals = [str(v).lower() for v in row.values]
        if "city" in row_vals and "year" in row_vals:
            header_idx = i
            found_header = True
            break
            
    if not found_header:
        header_idx = 0 # Fallback
        
    fisc_raw = pd.read_excel(fisc_path, sheet_name=target_sheet, engine='openpyxl', header=header_idx)
    
    # Normalize Columns
    fisc_raw.columns = [str(c).lower().strip().replace(' ', '_') for c in fisc_raw.columns]
    
    # Filter 2019
    if 'year' in fisc_raw.columns:
        fisc = fisc_raw[fisc_raw['year'] == 2019].copy()
    else:
        # Try finding year column
        year_cols = [c for c in fisc_raw.columns if 'year' in c]
        if year_cols:
            fisc = fisc_raw[fisc_raw[year_cols[0]] == 2019].copy()
            fisc = fisc.rename(columns={year_cols[0]: 'year'})
        else:
            fisc = fisc_raw

    # Map City/State
    # FiSC City format: "AK: Anchorage"
    # Find the city column
    city_col = next((c for c in fisc.columns if 'city' in c and 'name' in c), None) or \
               next((c for c in fisc.columns if 'fisc' in c and 'name' in c), None) or 'city'
               
    if city_col not in fisc.columns:
        raise ValueError(f"Could not find city column in FiSC. Cols: {fisc.columns}")

    # Split "AK: Anchorage"
    def split_fisc_place(val):
        s = str(val)
        if ':' in s:
            parts = s.split(':')
            return parts[0].strip(), clean_city_name(parts[1])
        return None, clean_city_name(s)

    fisc[['state', 'city']] = fisc[city_col].apply(lambda x: pd.Series(split_fisc_place(x)))
    
    # Map Police Spending
    police_cols = [c for c in fisc.columns if 'police' in c]
    # Prefer 'police' -> 'police_spending'
    target_pol = 'police' if 'police' in fisc.columns else (police_cols[0] if police_cols else None)
    if target_pol:
        fisc = fisc.rename(columns={target_pol: 'police_spending'})
    else:
        raise ValueError("No police column in FiSC")

    # Select columns
    fisc = fisc[['city', 'state', 'year', 'police_spending']]

    # 2. Load FBI CIUS (Multi-Year)
    def load_fbi_year(path, year):
        if not os.path.exists(path):
            return pd.DataFrame()
            
        print(f"Loading FBI {year}...", file=sys.stderr)
        try:
             # Header=3 works for 2015 and 2019 usually
            fbi = pd.read_excel(path, header=3, engine='xlrd') 
        except:
             fbi = pd.read_excel(path, header=3, engine='openpyxl')

        # Cleanup Columns
        # 2015/2019 Table 8 structure is similar: State, City, Pop, Violent, Property...
        cols = fbi.columns.tolist()
        new_cols = cols.copy()
        new_cols[0] = 'raw_state'
        new_cols[1] = 'city'
        fbi.columns = new_cols
        
        fbi['raw_state'] = fbi['raw_state'].fillna(method='ffill')
        
        # Standardize Cols
        fbi.columns = [str(c).lower().strip().replace('\n', ' ').replace(' ', '_') for c in fbi.columns]
        
        # Map State
        def map_state(val):
            val = str(val).title().strip()
            val = re.sub(r'\d+$', '', val).strip()
            return us_state_abbrev.get(val, None)
            
        fbi['state'] = fbi['raw_state'].apply(map_state)
        fbi['city'] = fbi['city'].apply(clean_city_name)
        fbi['year'] = year
        
        # Rename Outcome
        # 2015 might match 2019 names, but let's be robust
        # Look for 'violent_crime' and 'property_crime' partials
        viol_col = next((c for c in fbi.columns if 'violent' in c and 'crime' in c and 'rate' not in c), None) 
        prop_col = next((c for c in fbi.columns if 'property' in c and 'crime' in c and 'rate' not in c), None)
        pop_col = next((c for c in fbi.columns if 'population' in c), None)
        
        if viol_col and pop_col:
            fbi['violent_crime'] = pd.to_numeric(fbi[viol_col], errors='coerce')
            fbi['population'] = pd.to_numeric(fbi[pop_col], errors='coerce')
            # Rate per 100k
            fbi['violent_crime_rate'] = (fbi['violent_crime'] / fbi['population']) * 100000
            
        if prop_col and pop_col and 'population' in fbi.columns:
             fbi['property_crime'] = pd.to_numeric(fbi[prop_col], errors='coerce')
             fbi['property_crime_rate'] = (fbi['property_crime'] / fbi['population']) * 100000
        else:
             # Fallback if already calculated or missing
             pass
            
        fbi = fbi.dropna(subset=['state', 'city', 'violent_crime_rate'])
        
        # Ensure property_crime_rate exists (fill with NaN if missing so merge doesn't break, but ideally we have it)
        if 'property_crime_rate' not in fbi.columns:
             fbi['property_crime_rate'] = np.nan
             
        return fbi[['city', 'state', 'year', 'violent_crime_rate', 'property_crime_rate']]

    fbi_2019 = load_fbi_year("data/raw/FBI_CIUS_2019_Table8.xls", 2019)
    if not os.path.exists("data/raw/FBI_CIUS_2019_Table8.xls"):
         fbi_2019 = load_fbi_year("data/raw/FBI_CIUS_Table8.xls", 2019)
         
    fbi_2015 = load_fbi_year("data/raw/FBI_CIUS_2015_Table8.xls", 2015)
    
    fbi = pd.concat([fbi_2019, fbi_2015])

    # 3. Load ACS
    acs_path = "data/raw/ACS_Demographics_2019.csv"
    print("Loading ACS...", file=sys.stderr)
    acs = pd.read_csv(acs_path)
    
    # Columns: city_raw, population_density, median_income...
    # Parse city_raw: "Frazee city, Minnesota"
    def parse_acs_place(val):
        if ',' in str(val):
            parts = val.split(',')
            city_part = parts[0].strip() # "Frazee city"
            state_part = parts[1].strip() # "Minnesota"
            return clean_city_name(city_part), us_state_abbrev.get(state_part, None)
        return clean_city_name(val), None

    acs[['city', 'state']] = acs['city_raw'].apply(lambda x: pd.Series(parse_acs_place(x)))
    
    # Dropna
    acs = acs.dropna(subset=['city', 'state'])
    
    # Select cols (keep covariates)
    # columns are: city_raw, population_density, median_income, poverty_rate, male_15_24, city, year
    acs = acs[['city', 'state', 'year', 'population_density', 'median_income', 'poverty_rate', 'male_15_24']]
    
    return fisc, fbi, acs
