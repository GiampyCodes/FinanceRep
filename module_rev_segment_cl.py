import pandas as pd
from datetime import date
from edgar import *

set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format

ticker = "AAPL"
company = Company(ticker)

# ── Role keywords mapped by filing era ──────────────────────────────────────
PRODUCT_ROLES = [
    "RevenueDisaggregatedNetSales",                          # 2023–2025
    "RevenueNetSalesDisaggregatedbySignificantProducts",     # 2022
    "RevenueRecognitionNetSalesDisaggregatedbySignificant",  # 2020–2021
    "RevenueRecognitionNetSalesDisaggregatedBySignificant",  # 2019
    "SegmentInformationAndGeographicDataNetSalesByProduct",  # 2018
]

GEO_ROLES = [
    "SegmentInformationandGeographicDataNetSalesDetails",    # 2020–2022
    "SegmentInformationAndGeographicDataNetSalesDetails",    # 2018–2019
]

def find_statement(statements, role_keywords):
    for keyword in role_keywords:
        match = next((s for s in statements if keyword.lower() in s.role_or_type.lower()), None)
        if match:
            return match
    return None

def extract_df(statement, geo=False):
    """Extract clean year columns from a statement."""
    df = statement.to_dataframe()
    year_cols = [c for c in df.columns if '20' in str(c)]
    if not year_cols:
        return None
    df = df[['label'] + year_cols].copy()
    for col in year_cols:
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce'
        ) / 1_000_000
    df.columns = ['label'] + [c[:4] for c in sorted(year_cols, reverse=True)]
    if geo:
        df['label'] = df['label'].str.replace('Operating segments - ', '', regex=False).str.strip()
    return df

# ── Fetch all 10-K filings ───────────────────────────────────────────────────
print("Fetching 10-K filings...\n")
filings = company.get_filings(form="10-K", amendments=False)

all_products = {}  # year -> series
all_geo = {}

PRODUCT_ROWS = ['iPhone', 'Mac', 'iPad', 'Wearables', 'Services']
GEO_ROWS     = ['Americas', 'Europe', 'Greater China', 'Japan', 'Rest of Asia']

for filing in filings:
    if filing.filing_date < date(2018, 1, 1):
        break  # No XBRL before 2018
    try:
        xbrl = filing.xbrl()
        if xbrl is None:
            continue
        statements = xbrl.statements
        print(f"  Processing {filing.filing_date}...")

        # ── Product segments ────────────────────────────────────────────────
        prod_stmt = find_statement(statements, PRODUCT_ROLES)
        if prod_stmt:
            df = extract_df(prod_stmt)
            if df is not None:
                df_filt = df[df['label'].str.contains('|'.join(PRODUCT_ROWS), case=False, na=False)]
                for yr_col in [c for c in df_filt.columns if c != 'label']:
                    if yr_col not in all_products:
                        all_products[yr_col] = df_filt.set_index('label')[yr_col]

        # ── Geographic segments ─────────────────────────────────────────────
        geo_stmt = find_statement(statements, GEO_ROLES)
        if geo_stmt:
            df = extract_df(geo_stmt, geo=True)
            if df is not None:
                df_filt = df[df['label'].str.contains('|'.join(GEO_ROWS), case=False, na=False)]
                for yr_col in [c for c in df_filt.columns if c != 'label']:
                    if yr_col not in all_geo:
                        all_geo[yr_col] = df_filt.set_index('label')[yr_col]

    except Exception as e:
        print(f"  Skipping {filing.filing_date}: {e}")

# ── Build final tables ───────────────────────────────────────────────────────
def build_table(data_dict, row_order):
    df = pd.DataFrame(data_dict)
    df = df.reindex(sorted(df.columns, reverse=True), axis=1)       # newest first
    df = df.reindex([r for r in row_order if r in df.index])        # enforce row order
    df.loc['Total Net Sales'] = df.sum()
    return df

PRODUCT_ORDER = ['iPhone', 'Mac', 'iPad', 'Wearables, Home and Accessories', 'Services']
GEO_ORDER     = ['Americas', 'Europe', 'Greater China', 'Japan', 'Rest of Asia Pacific']

df_products_final = build_table(all_products, PRODUCT_ORDER)
df_geo_final      = build_table(all_geo, GEO_ORDER)

print(f"\n--- Apple 10-K Revenue Segments (all available years) ---\n")

print("=" * 90)
print("  PRODUCT REVENUE SEGMENTS ($ millions)")
print("=" * 90)
print(df_products_final.to_string())

print("\n" + "=" * 90)
print("  GEOGRAPHIC REVENUE SEGMENTS ($ millions)")
print("=" * 90)
print(df_geo_final.to_string())