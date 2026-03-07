import pandas as pd
from itertools import combinations
from datetime import date
from edgar import *

# ── CONFIG ───────────────────────────────────────────────────────────────────
set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format

TICKER     = input("Enter ticker symbol (e.g. AAPL, MSFT, GOOGL): ").strip().upper()
START_DATE = date(2018, 1, 1)
MAX_YEARS  = 8
TOLERANCE  = 0.03

# ── ROLE PATTERNS ─────────────────────────────────────────────────────────────
PRODUCT_ROLE_PATTERNS = [
    "RevenuesRevenuebyTypeDetails",
    "RevenuesRevenuebySegmentDetails",
    "RevenuesRevenueBySegmentDetails",
    "InformationAboutSegmentsAndGeographicAreasRevenueBySegmentDetails",
    "InformationaboutSegmentsandGeographicAreasRevenueBySegmentDetails",
    "RevenueDisaggregatedNetSales",
    "RevenueNetSalesDisaggregatedbySignificantProducts",
    "RevenueRecognitionNetSalesDisaggregatedbySignificant",
    "RevenueRecognitionNetSalesDisaggregatedBySignificant",
    "SegmentInformationAndGeographicDataNetSalesByProduct",
    "DisaggregationOfRevenue",
    "RevenueByProductDetails",
    "RevenueBySegmentDetails",
    "DisaggregationOfRevenueDetails",
    "SegmentRevenueDetails",
]

GEO_ROLE_PATTERNS = [
    "RevenuesRevenuebyGeographicLocationDetails",
    "RevenuesRevenueByGeographicLocationDetails",
    "InformationAboutSegmentsAndGeographicAreasNetSalesDetails",
    "InformationaboutSegmentsandGeographicAreasNetSalesDetails",
    "SegmentInformationandGeographicDataNetSalesDetails",
    "SegmentInformationAndGeographicDataNetSalesDetails",
    "GeographicAreasRevenueFromExternalCustomers",
    "RevenueFromExternalCustomersByGeographicAreas",
    "RevenueByGeographicLocationDetails",
    "GeographicInformationDetails",
    "RevenueByGeographyDetails",
]

IS_ROLE_PATTERNS = [
    "CONSOLIDATEDSTATEMENTSOFINCOME",
    "ConsolidatedStatementsOfIncome",
    "CONSOLIDATEDSTATEMENTSOFOPERATIONS",
    "ConsolidatedStatementsOfOperations",
    "StatementsOfIncome",
    "StatementsOfOperations",
]

EXCLUDE_ROW_PATTERNS = [
    'hedging', 'hedge', 'foreign exchange contract', 'reclassification',
    'aoci', 'unrealized', 'cash flow hedge', 'fair value hedge',
    'effect of', 'impact of', 'accounting standard', 'topic 606',
]

IS_REVENUE_EXACT = [
    'revenues', 'revenue', 'net sales', 'total revenues',
    'total revenue', 'net revenue',
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def find_statement_by_role(statements, role_patterns):
    for pattern in role_patterns:
        for s in statements:
            role = s.role_or_type.replace(" ","").replace("-","").replace("_","")
            if pattern.lower() in role.lower():
                return s
    return None

def get_revenue_anchor(xbrl):
    result = {}
    for s in xbrl.statements:
        role = s.role_or_type.replace(" ","").replace("-","").replace("_","")
        if not any(p.lower() in role.lower() for p in IS_ROLE_PATTERNS):
            continue
        if any(x in role.lower() for x in ['parenthetical','comprehensive','supplemental']):
            continue
        try:
            df = s.to_dataframe()
            if 'label' not in df.columns:
                continue
            year_cols = [c for c in df.columns if str(c)[:2] in ['19','20'] and len(str(c)) >= 7]
            if not year_cols:
                continue
            labels_lower = df['label'].astype(str).str.lower().str.strip()
            exact_mask = labels_lower.isin(IS_REVENUE_EXACT)
            if exact_mask.any():
                rev_row = df[exact_mask].iloc[0]
            else:
                fuzzy_mask = (
                    labels_lower.str.contains('revenue|net sales', na=False) &
                    ~labels_lower.str.contains(
                        'cost|other|advertising|search|youtube|cloud|network|'
                        'service|product|segment|geographic|deferred|recognized', na=False
                    )
                )
                if not fuzzy_mask.any():
                    continue
                rev_row = df[fuzzy_mask].iloc[0]
            for col in year_cols:
                yr = col[:4]
                val = pd.to_numeric(rev_row[col], errors='coerce')
                if pd.notna(val) and val > 1e9:
                    result[yr] = val / 1_000_000
            if result:
                return result
        except Exception:
            continue
    return result

def extract_df(statement, clean_prefix=None):
    try:
        df = statement.to_dataframe()
        df = df.drop_duplicates(subset=['label'])
        year_cols = [c for c in df.columns if str(c)[:2] in ['19','20'] and len(str(c)) >= 7]
        if not year_cols:
            return None, []
        df = df[['label'] + year_cols].copy()
        for col in year_cols:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',','').str.strip(), errors='coerce'
            ) / 1_000_000
        df.columns = ['label'] + [c[:4] for c in sorted(year_cols, reverse=True)]
        year_cols_short = [c[:4] for c in sorted(year_cols, reverse=True)]
        if clean_prefix:
            df['label'] = df['label'].str.replace(clean_prefix, '', regex=False).str.strip()
        df = df[df['label'].astype(str).str.strip() != '']
        return df, year_cols_short
    except Exception:
        return None, []

def remove_noise_rows(df):
    pattern = '|'.join(EXCLUDE_ROW_PATTERNS)
    return df[~df['label'].astype(str).str.lower().str.contains(pattern, na=False)]

def remove_total_rows(df, year_cols, total_revenues, tolerance=TOLERANCE):
    def is_total(row):
        for yr in year_cols:
            if yr not in total_revenues or not total_revenues[yr]:
                continue
            val = pd.to_numeric(row.get(yr), errors='coerce')
            if pd.notna(val) and val > 0:
                if abs(val - total_revenues[yr]) / total_revenues[yr] <= tolerance:
                    return True
        return False
    return df[~df.apply(is_total, axis=1)]

def remove_subtotal_rows(df, year_cols, tolerance=0.01):
    """
    Remove rows that are subtotals — i.e. their value equals the sum of
    any subset of other rows in the same table for the most populated year.

    Strategy:
    1. Use the year with the most non-null values as the reference column.
    2. For each row, check if its value equals the sum of any combination
       of 2+ other rows. If yes → it's a subtotal, remove it.
    3. Also catch rows that equal the sum of ALL other rows (grand subtotal).
    """
    if df.empty or not year_cols:
        return df

    # Pick the reference year: most non-null positive values
    ref_year = max(
        year_cols,
        key=lambda yr: pd.to_numeric(df[yr], errors='coerce').gt(0).sum()
        if yr in df.columns else 0
    )

    values = pd.to_numeric(df[ref_year], errors='coerce').fillna(0)
    values.index = df.index
    pos_values = values[values > 0]

    if len(pos_values) < 3:
        return df  # Not enough rows to detect subtotals

    subtotal_indices = set()

    # Check every row against sums of combinations of other rows
    for idx in pos_values.index:
        candidate = pos_values[idx]
        others = pos_values.drop(index=idx)

        if others.empty:
            continue

        # Check: does candidate equal sum of ALL others? (grand subtotal / parent row)
        if abs(others.sum() - candidate) / candidate <= tolerance:
            subtotal_indices.add(idx)
            continue

        # Check: does candidate equal sum of any 2-5 row subset?
        # Limit combinations to avoid O(n!) for large tables
        other_list = list(others.items())
        max_combo = min(len(other_list), 6)
        found = False
        for r in range(2, max_combo + 1):
            for combo in combinations(other_list, r):
                combo_sum = sum(v for _, v in combo)
                if combo_sum > 0 and abs(combo_sum - candidate) / candidate <= tolerance:
                    subtotal_indices.add(idx)
                    found = True
                    break
            if found:
                break

    kept = df[~df.index.isin(subtotal_indices)].copy()

    # Log what was removed
    removed = df[df.index.isin(subtotal_indices)]
    if not removed.empty:
        for _, row in removed.iterrows():
            print(f"      [subtotal removed] '{row['label']}' = {pos_values.get(row.name, 'N/A'):,.0f}M")

    return kept

def keep_positive_rows(df, year_cols):
    mask = df[year_cols].apply(
        lambda col: pd.to_numeric(col, errors='coerce') > 0
    ).any(axis=1)
    return df[mask]

def clean_segment_rows(df, year_cols, total_revenues):
    df = remove_noise_rows(df)
    df = remove_total_rows(df, year_cols, total_revenues)
    df = keep_positive_rows(df, year_cols)
    df = remove_subtotal_rows(df, year_cols)  # <-- new step
    df = keep_positive_rows(df, year_cols)    # re-run after subtotal removal
    return df

def validate_table(data_dict, total_revenues, tolerance=TOLERANCE):
    results = {}
    if not data_dict:
        return results
    df = pd.DataFrame(data_dict)
    for yr in sorted(df.columns, reverse=True):
        if yr not in total_revenues or not total_revenues[yr]:
            continue
        expected = total_revenues[yr]
        actual = pd.to_numeric(df[yr], errors='coerce').dropna()
        actual = actual[actual > 0].sum()
        pct_diff = abs(actual - expected) / expected if expected else 1
        results[yr] = {
            'actual': actual,
            'expected': expected,
            'pct_diff': pct_diff,
            'valid': pct_diff <= tolerance,
        }
    return results

def build_table(data_dict):
    if not data_dict:
        return None
    df = pd.DataFrame(data_dict)
    df = df.reindex(sorted(df.columns, reverse=True), axis=1)
    df = df.dropna(how='all')
    df = df[(df.abs() > 0.01).any(axis=1)]
    df.loc['Total'] = df.sum()
    return df

def build_yoy_growth(df):
    has_total = 'Total' in df.index
    seg_df = df.drop(index='Total') if has_total else df.copy()
    year_cols = list(seg_df.columns)
    growth_data = {}
    for i in range(len(year_cols) - 1):
        curr, prev = year_cols[i], year_cols[i+1]
        growth_data[f"{curr} vs {prev}"] = (
            (seg_df[curr] - seg_df[prev]) / seg_df[prev].abs() * 100
        ).round(1)
    if not growth_data:
        return None
    gdf = pd.DataFrame(growth_data, index=seg_df.index)
    if has_total:
        tg = {}
        for col in gdf.columns:
            c, p = col.split(' vs ')
            cv, pv = df.loc['Total', c], df.loc['Total', p]
            tg[col] = round((cv - pv) / abs(pv) * 100, 1) if pv else None
        gdf.loc['Total'] = tg
    return gdf

def format_growth(gdf):
    fmt = gdf.copy().astype(object)
    for col in gdf.columns:
        for idx in gdf.index:
            val = gdf.loc[idx, col]
            fmt.loc[idx, col] = 'N/A' if pd.isna(val) else f"{'+'if val>0 else ''}{val:.1f}%"
    return fmt

def print_section(title, df, growth_df=None, width=95):
    print(f"\n{'='*width}\n  {title}\n{'='*width}")
    print(df.to_string())
    if growth_df is not None:
        print(f"\n{'-'*width}\n  {title} — YoY GROWTH\n{'-'*width}")
        print(format_growth(growth_df).to_string())

def print_validation(label, validation):
    if not validation:
        return
    print(f"\n  ── {label} ──")
    for yr, v in sorted(validation.items(), reverse=True):
        status = "✓" if v['valid'] else "✗"
        print(f"    {status} {yr}: segments=${v['actual']:,.0f}M  |  anchor=${v['expected']:,.0f}M  |  diff={v['pct_diff']*100:.1f}%")

# ── Main fetch loop ───────────────────────────────────────────────────────────
print(f"\nFetching 10-K filings for {TICKER}...\n")
company = Company(TICKER)
filings = company.get_filings(form="10-K", amendments=False)

all_products   = {}
all_geo        = {}
total_revenues = {}

for filing in filings:
    if filing.filing_date < START_DATE:
        break
    if len(all_products) >= MAX_YEARS and len(all_geo) >= MAX_YEARS:
        break

    print(f"  Processing {filing.filing_date}...")
    try:
        xbrl = filing.xbrl()
        if xbrl is None:
            continue
        statements = xbrl.statements

        # Step 1: revenue anchor
        filing_revenues = get_revenue_anchor(xbrl)
        if not filing_revenues:
            print(f"    [!] No revenue anchor — skipping")
            continue
        for yr, rev in filing_revenues.items():
            if yr not in total_revenues:
                total_revenues[yr] = rev
        print(f"    Anchors: { {k: f'${v:,.0f}M' for k,v in sorted(filing_revenues.items(), reverse=True)} }")

        # Step 2: product statement
        prod_stmt = find_statement_by_role(statements, PRODUCT_ROLE_PATTERNS)
        if prod_stmt:
            df, year_cols = extract_df(prod_stmt, clean_prefix="Operating segments - ")
            if df is not None:
                df_clean = clean_segment_rows(df, year_cols, total_revenues)
                df_set = df_clean.set_index('label')
                added = []
                for yr in year_cols:
                    if yr not in all_products and yr in total_revenues:
                        col = pd.to_numeric(df_set[yr], errors='coerce').dropna()
                        col = col[col > 0]
                        if not col.empty:
                            all_products[yr] = col
                            added.append(yr)
                if added:
                    print(f"    [product] {prod_stmt.role_or_type.split('/')[-1]} → {added}")
        else:
            print(f"    [!] No product statement found")

        # Step 3: geo statement
        geo_stmt = find_statement_by_role(statements, GEO_ROLE_PATTERNS)
        if geo_stmt:
            df, year_cols = extract_df(geo_stmt, clean_prefix="Operating segments - ")
            if df is not None:
                df_clean = clean_segment_rows(df, year_cols, total_revenues)
                df_set = df_clean.set_index('label')
                added = []
                for yr in year_cols:
                    if yr not in all_geo and yr in total_revenues:
                        col = pd.to_numeric(df_set[yr], errors='coerce').dropna()
                        col = col[col > 0]
                        if not col.empty:
                            all_geo[yr] = col
                            added.append(yr)
                if added:
                    print(f"    [geo]     {geo_stmt.role_or_type.split('/')[-1]} → {added}")
        else:
            print(f"    [!] No geo statement found")

    except Exception as e:
        print(f"  Skipping {filing.filing_date}: {e}")

# ── Build and validate ────────────────────────────────────────────────────────
df_prod = build_table(all_products)
df_geo  = build_table(all_geo)

prod_validation = validate_table(all_products, total_revenues)
geo_validation  = validate_table(all_geo, total_revenues)

print(f"\n{'─'*95}")
print(f"  {TICKER} — Revenue Anchor Validation")
print(f"{'─'*95}")
print_validation("Product / Segment table", prod_validation)
print_validation("Geographic table", geo_validation)

# ── Print output ──────────────────────────────────────────────────────────────
print(f"\n{'─'*95}")
print(f"  {TICKER} — 10-K Revenue Segments ($ millions)")
print(f"{'─'*95}")

if df_prod is not None:
    print_section(f"{TICKER} PRODUCT / SEGMENT REVENUE ($ millions)", df_prod, build_yoy_growth(df_prod))
else:
    print(f"\n  [!] Could not extract product segments for {TICKER}.")

if df_geo is not None:
    print_section(f"{TICKER} GEOGRAPHIC REVENUE ($ millions)", df_geo, build_yoy_growth(df_geo))
else:
    print(f"\n  [!] Could not extract geographic segments for {TICKER}.")