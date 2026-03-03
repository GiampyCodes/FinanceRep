import pandas as pd
from edgar import *

# 1. IDENTITY
set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format

# 2. DATA FETCH
ticker = "AAPL"
company = Company(ticker)
filing = company.get_filings(form="10-K").latest()

print(f"--- Apple 10-K Segments ({filing.filing_date}) ---")

# 3. THE REVENUE HUNT — using XBRL facts directly (most reliable)
try:
    # Access XBRL data at the filing level (not tenk.obj level)
    xbrl = filing.xbrl()

    # ---- APPROACH A: Search statements by name ----
    all_statements = xbrl.statements
    print("Available statements:")
    for s in all_statements:
        print(f"  - {s.name}")

    # Try to find disaggregated revenue table
    keywords = ["Disaggregated", "Segment", "Revenue", "Net Sales"]
    target = None
    for keyword in keywords:
        target = next((s for s in all_statements if keyword.lower() in s.name.lower()), None)
        if target:
            print(f"\nUsing statement: '{target.name}'")
            break

    if target:
        # Try both .to_dataframe() and .to_pandas()
        try:
            df = target.to_dataframe()
        except AttributeError:
            try:
                df = target.to_pandas()
            except AttributeError:
                df = pd.DataFrame(target.data)

        products = ['iPhone', 'Mac', 'iPad', 'Wearables', 'Services']
        mask = df.index.astype(str).str.contains('|'.join(products), case=False, na=False)
        df_final = df[mask]

        # Sort columns newest first
        df_final = df_final.reindex(sorted(df_final.columns, reverse=True), axis=1)
        print(df_final)

    else:
        # ---- APPROACH B: Fallback — query XBRL facts directly ----
        print("\nNo matching statement found. Trying direct XBRL facts...")
        facts = xbrl.facts

        # Apple uses us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax
        revenue_concepts = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet"
        ]
        for concept in revenue_concepts:
            df = facts.query(f"concept == '{concept}'")
            if not df.empty:
                print(f"\nFound data for concept: {concept}")
                print(df[['label', 'value', 'period', 'segment']].dropna(subset=['segment']))
                break

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()