import pandas as pd
from edgar import *

# 1. IDENTITY (Must be Name <email>)
set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format 

# 2. DATA FETCH
ticker = "AAPL"
company = Company(ticker)
# Get the latest 10-K and jump straight to the data
filing = company.get_filings(form="10-K").latest()
tenk = filing.obj()

print(f"--- Apple 10-K Segments ({filing.filing_date}) ---")

# 3. THE REVENUE HUNT
try:
    # Use the .xbrl() property - it's the most stable door to the data
    xbrl_data = tenk.xbrl()
    
    # We want to find the 'Statement' or 'Report' for Revenue
    # This one-liner searches all tables for the word 'Disaggregated'
    target_report = next((r for r in xbrl_data.statements if "Disaggregated" in r.name), None)

    if target_report:
        print(f"Found: {target_report.name}\n")
        df = target_report.to_pandas()
        
        # Filter for Apple's big 5 categories
        products = ['iPhone', 'Mac', 'iPad', 'Wearables', 'Services']
        df_final = df[df.index.str.contains('|'.join(products), case=False, na=False)]
        
        # Newest Year First
        df_final = df_final.reindex(sorted(df_final.columns, reverse=True), axis=1)
        print(df_final)
    else:
        print("Table not found. Printing all available tables to help you pick:")
        for r in xbrl_data.statements:
            print(f"- {r.name}")

except Exception as e:
    print(f"Connection/Version Error: {e}")