import pandas as pd
from edgar import *

set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format

ticker = "AAPL"
company = Company(ticker)
filing = company.get_filings(form="10-K").latest()

print(f"--- Apple 10-K Revenue Segments ({filing.filing_date}) ---\n")

xbrl = filing.xbrl()

target = next(s for s in xbrl.statements if "RevenueDisaggregated" in s.role_or_type)
df = target.to_dataframe()

# --- DEBUG: see what we're working with ---
print("Shape:", df.shape)
print("\nColumns:", df.columns.tolist())
print("\nIndex (first 20):", df.index[:20].tolist())
print("\nSample data (label + year columns):")
year_cols = [c for c in df.columns if '20' in str(c)]
print(df[['label'] + year_cols].to_string())