import pandas as pd
from datetime import date
from edgar import *

# ── CONFIG ───────────────────────────────────────────────────────────────────
set_identity("Giampaolo Sacco giampysacco16@gmail.com")
pd.options.display.float_format = '{:,.0f}'.format

TICKER     = input("Enter ticker symbol (e.g. AAPL, MSFT, GOOGL): ").strip().upper()
START_DATE = date(2018, 1, 1)
MAX_YEARS  = 8
TOLERANCE  = 0.03

# ── INCOME STATEMENT PATTERNS (for revenue anchor) ────────────────────────────
IS_ROLE_PATTERNS = [
    "CONSOLIDATEDSTATEMENTSOFINCOME",
    "ConsolidatedStatementsOfIncome",
    "CONSOLIDATEDSTATEMENTSOFOPERATIONS",
    "ConsolidatedStatementsOfOperations",
    "StatementsOfIncome",
    "StatementsOfOperations",
    "INCOMESTATEMENTS",
    "StatementINCOMESTATEMENTS",
]

IS_REVENUE_EXACT = [
    'revenues', 'revenue', 'net sales', 'total revenues',
    'total revenue', 'net revenue',
]

EXCLUDE_ROW_PATTERNS = [
    'foreign exchange contract', 'reclassification', 'aoci',
    'cash flow hedge', 'fair value hedge', 'effect of',
    'impact of', 'accounting standard', 'topic 606',
]

# ── DYNAMIC DISCOVERY FILTERS ────────────────────────────────────────────────
# Statement role keywords that indicate definitely-NOT a revenue segment table
SKIP_STMT_KEYWORDS = [
    'balancesheet', 'cashflow', 'stockholder', 'shareowner', 'equity',
    'parenthetical', 'supplemental', 'lease', 'debt', 'goodwill',
    'intangible', 'property', 'derivative', 'incometax',
    'compensation', 'earningpershare', 'pershare', 'unearnedrevenue',
    'backlog', 'commitment', 'contingenc', 'pension', 'restructur',
    'warranty', 'inventori', 'acquisit', 'comprehensiveincome',
    'othercomprehensive', 'accumulated',
    # Debt / borrowing / investment tables — can coincidentally sum near revenue
    'borrow', 'seniornote', 'termloan', 'creditfacility', 'principalpayment',
    'longtermdebt', 'debtmaturity', 'futureprincipal',
    'marketablesecuriti', 'cashequivalent', 'amortizedcost',
    'unrealizedloss', 'unrealizedgain', 'fairvalue',
    # Non-revenue segment disclosure tables
    'longlivedasset', 'totalasset', 'employeecount',
    'scheduleii', 'valuationandqualifying',
    'auditinformation', 'coverpage',
]

# Row-label keywords that indicate non-revenue rows inside a candidate table
SKIP_ROW_KEYWORDS = [
    'cost of', 'gross profit', 'operating income', 'operating expense',
    'net income', 'interest', 'depreciation', 'amortization',
    'income before', 'provision for', 'earnings per', 'diluted',
    'basic', 'weighted',
]

# Label fragments that signal geographic rows (for geo vs product classification)
GEO_LABEL_KEYWORDS = [
    'united states', 'americas', 'emea', 'apac', 'europe', 'asia pacific',
    'asia-pacific', 'china', 'japan', 'taiwan', 'korea', 'india',
    'rest of world', 'other countries', 'other geograph',
    'international', 'domestic', 'foreign', 'north america',
    'latin america', 'middle east', 'africa',
]

# ── HARDCODED ROLE PATTERNS (fast path for known companies) ───────────────────
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
    "SegmentRevenueCostOfRevenueOperatingExpensesAndOperatingIncomeDetail",
    "RevenueClassifiedBySignificantProductAndServiceOfferingsDetail",
    # NVDA
    "SegmentInformationScheduleofRevenuebyMarketDetails",
    "ScheduleofRevenuebyMarketDetails",
    # AVGO
    "RevenuebyEndMarketDetails",
    "DisaggregationofRevenueDetails",
    "RevenueDisaggregationDetails",
    "NetRevenuebyEndMarketDetails",
    # Generic segment detail suffixes
    "RevenuebyMarketDetails",
    "RevenuebySegmentDetails",
    "SegmentRevenueDetails",
    "DisaggregationOfRevenueDetails",
]

GEO_ROLE_PATTERNS = [
    "RevenuesRevenuebyGeographicLocationDetails",
    "RevenuesRevenueByGeographicLocationDetails",
    "InformationAboutSegmentsAndGeographicAreasNetSalesDetails",
    "InformationaboutSegmentsandGeographicAreasNetSalesDetails",
    "SegmentInformationandGeographicDataNetSalesDetails",
    "SegmentInformationAndGeographicDataNetSalesDetails",
    "RevenueClassifiedByMajorGeographicAreasDetail",
    # NVDA
    "SegmentInformationRevenueandLonglivedAssetsbyRegionDetails",
    "RevenueandLonglivedAssetsbyRegionDetails",
    # AVGO
    "RevenuebyGeographyDetails",
    "NetRevenuebyGeographyDetails",
    "RevenuebyGeographicAreaDetails",
    # Generic
    "RevenueFromExternalCustomersByGeographicAreas",
    "GeographicAreasRevenueFromExternalCustomers",
    "RevenueByGeographicLocationDetails",
    "GeographicInformationDetails",
]

# ── TICKER-SPECIFIC ROW ALLOWLISTS ────────────────────────────────────────────
# For companies that pack multiple breakdown types into one XBRL table (e.g.
# MSFT puts segments + product/service + geo in a single statement). Generic
# row-cleaning can't disentangle them, so we hard-code which rows to keep.
TICKER_PRODUCT_ROWS = {
    'MSFT': [
        'productivity and business processes',
        'intelligent cloud',
        'more personal computing',
    ],
    'NVDA': [
        # Current segments (FY2024+)
        'compute & networking',
        'graphics',
        # Legacy segments (FY2023 and earlier)
        'data center',
        'gaming',
        'professional visualization',
        'automotive',
        'oem & ip',
        'oem and ip',
        'oem & other',
    ],
    'AVGO': [
        'semiconductor solutions',
        'infrastructure software',
        # Legacy
        'networking',
        'wireless',
        'enterprise storage',
        'broadband',
        'industrial & other',
        'industrial and other',
    ],
}

TICKER_GEO_ROWS = {
    'MSFT': [
        'united states',
        'other countries',
    ],
    'NVDA': [
        'united states',
        'taiwan',
        'china',
        'other asia pacific',
        'europe',
        'other countries',
        'singapore',
        'hong kong',
        'south korea',
        'india',
    ],
    'AVGO': [
        'united states',
        'asia pacific',
        'europe',
        'other',
        'americas',
    ],
}

# ── Revenue anchor ────────────────────────────────────────────────────────────
def get_revenue_anchor(xbrl):
    result = {}
    for s in xbrl.statements:
        role = s.role_or_type.replace(" ", "").replace("-", "").replace("_", "")
        if not any(p.lower() in role.lower() for p in IS_ROLE_PATTERNS):
            continue
        if any(x in role.lower() for x in ['parenthetical', 'comprehensive', 'supplemental']):
            continue
        try:
            df = s.to_dataframe()
            if 'label' not in df.columns:
                continue
            year_cols = [c for c in df.columns if str(c)[:2] in ['19', '20'] and len(str(c)) >= 7]
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


# ── Statement utilities ───────────────────────────────────────────────────────
def extract_df(statement, clean_prefix=None):
    try:
        df = statement.to_dataframe()
        df = df.drop_duplicates(subset=['label'])
        year_cols = [c for c in df.columns if str(c)[:2] in ['19', '20'] and len(str(c)) >= 7]
        if not year_cols:
            return None, []
        df = df[['label'] + year_cols].copy()
        for col in year_cols:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(',', '').str.strip(), errors='coerce'
            ) / 1_000_000
        df.columns = ['label'] + [c[:4] for c in sorted(year_cols, reverse=True)]
        year_cols_short = [c[:4] for c in sorted(year_cols, reverse=True)]
        if clean_prefix:
            df['label'] = df['label'].str.replace(clean_prefix, '', regex=False).str.strip()
        df = df[df['label'].astype(str).str.strip() != '']
        return df.reset_index(drop=True), year_cols_short
    except Exception:
        return None, []


def _stmt_role_clean(s):
    return s.role_or_type.replace(" ", "").replace("-", "").replace("_", "").lower()


def _is_income_statement(s):
    role = _stmt_role_clean(s)
    return any(p.lower() in role for p in IS_ROLE_PATTERNS)

# ── Dynamic segment discovery ─────────────────────────────────────────────────

# Standardised XBRL concept tags used by ALL public companies for revenue.
# These are US-GAAP taxonomy names — universal regardless of company or year.
# Matching any of these guarantees a row IS a revenue line item.
_REVENUE_CONCEPTS = {
    'revenuefromcontractwithcustomerexcludingassessedtax',
    'revenuefromcontractwithcustomerincludingassessedtax',
    'revenues',
    'revenuefrommcontractwithcustomer',
    'salesrevenuenet',
    'salesrevenuegodsnet',
    'salesrevenueservicesnet',
    'revenuenotfromcontractwithcustomer',
    'revenuesnetofinterestexpense',
    'interestincomenet',
    'netsales',
    'netsalesrevenues',
    'revenuenet',
}

# Label-based fallback filter (used when no concept column is available)
_DISCOVERY_SKIP_ROW_LABELS = [
    'cost of', 'gross profit', 'gross margin', 'operating income',
    'operating expense', 'operating margin', 'net income', 'interest',
    'depreciation', 'amortization', 'income before', 'provision for',
    'earnings per', 'diluted', 'basic', 'weighted', 'total segment',
    'reconcil', 'unallocated', 'corporate', 'stock-based', 'adjustment',
    'long-lived', 'total assets', 'property, plant', 'charges',
    'restructur', 'impairment', 'research and development',
    'sales, general', 'selling, general', 'other income', 'other expense',
    'tax', 'cash and cash', 'marketable', 'fair value', 'level ',
    'due in', 'less than', 'allocated', 'share-based', 'capital expenditure',
    'accounts receivable', 'inventory', 'deferred', 'accrued',
]


def _normalise_concept(concept_str):
    """Strip namespace prefix and underscores, lowercase."""
    c = str(concept_str).lower()
    for sep in (':', '_', '-', ' '):
        c = c.replace(sep, '')
    # Strip common namespace prefixes
    for ns in ('usgaap', 'ifrs', 'dei', 'srt'):
        if c.startswith(ns):
            c = c[len(ns):]
    return c


def _filter_by_concept(df_raw, col, target, tolerance=0.05):
    """
    If df_raw has a 'concept' column, keep only rows whose concept tag
    matches a known revenue concept AND whose value is below total revenue.
    Returns filtered DataFrame or None if concept column absent / no match.
    """
    if 'concept' not in df_raw.columns:
        return None

    normalised = df_raw['concept'].apply(_normalise_concept)
    revenue_mask = normalised.isin(_REVENUE_CONCEPTS)

    if not revenue_mask.any():
        return None

    df_rev = df_raw[revenue_mask].copy()
    # Drop grand-total rows (value ≈ full revenue)
    df_rev = df_rev[~df_rev[col].apply(
        lambda v: pd.notna(v) and v > 0 and abs(v - target) / target <= tolerance
    )]
    pos = df_rev[pd.to_numeric(df_rev[col], errors='coerce') > 0]
    if len(pos) >= 2:
        return pos
    return None


def _filter_by_label(df_work, col, target, tolerance=0.05):
    """
    Label-based row filter (fallback when no concept column).
    Removes rows that are clearly non-revenue (cost, gross profit, etc.)
    then removes grand-total rows.
    """
    skip_pat = '|'.join(_DISCOVERY_SKIP_ROW_LABELS)
    df_f = df_work[~df_work['label'].str.lower().str.contains(skip_pat, na=False)].copy()
    df_f = df_f[~df_f[col].apply(
        lambda v: pd.notna(v) and v > 0 and abs(v - target) / target <= tolerance
    )]
    return df_f[pd.to_numeric(df_f[col], errors='coerce') > 0].copy()


def _check_sum(pos, col, target, tolerance=0.05):
    """Return (matches, ratio) — matches=True if sum within tolerance."""
    if pos is None or len(pos) < 2:
        return False, 0
    row_sum = pd.to_numeric(pos[col], errors='coerce').fillna(0).sum()
    ratio = row_sum / target if target else 0
    return abs(ratio - 1.0) <= tolerance, ratio


def _find_revenue_subset(pos, col, target, tolerance=0.05):
    """
    When rows don't directly sum to revenue, search for the subset that does.
    Used when a table mixes multiple metrics (revenue + cost + gross profit)
    per segment row — e.g. NVDA.

    Strategies (in order):
      1. Dedup by label, keep first occurrence — in mixed-metric tables XBRL
         ordering puts revenue first, so first-per-label == revenue rows.
      2. Combination search across up to 15 largest candidates.
    """
    from itertools import combinations
    vals = pd.to_numeric(pos[col], errors='coerce').fillna(0)

    # Strategy 1: first-occurrence dedup
    pos_dedup = pos.drop_duplicates(subset=['label'], keep='first').copy()
    vals_dedup = pd.to_numeric(pos_dedup[col], errors='coerce').fillna(0)
    pos_dedup = pos_dedup[vals_dedup.apply(lambda v: 0 < v < target * 0.99)]
    if len(pos_dedup) >= 2:
        if abs(pd.to_numeric(pos_dedup[col], errors='coerce').fillna(0).sum() - target) / target <= tolerance:
            return pos_dedup

    # Strategy 2: combination search
    candidates = sorted(
        [(idx, vals[idx]) for idx in pos.index if 0 < vals[idx] < target * 0.99],
        key=lambda x: -x[1]
    )[:15]
    if len(candidates) < 2:
        return None
    for size in range(2, min(len(candidates) + 1, 11)):
        for combo in combinations(candidates, size):
            if abs(sum(v for _, v in combo) - target) / target <= tolerance:
                return pos.loc[[i for i, _ in combo]]
    return None


def _score_candidate(df_raw, df_work, year_cols_s, total_revenues, ref_yr):
    """
    Score a single candidate statement.
    Returns (score, winning_rows_df).  score==0 → reject.

    Three-pass strategy, highest confidence first:
      Pass A — concept-tag filter: keep only rows tagged with revenue concepts.
               Universally correct regardless of label language or table layout.
      Pass B — label filter direct: rows after label-based cleaning sum ±5%.
      Pass C — label filter + subset search: table has mixed metrics per segment
               (e.g. NVDA); find the revenue subset by dedup or combination.
    """
    target = total_revenues.get(ref_yr)
    if not target:
        return 0, df_work

    col = ref_yr
    if col not in df_work.columns:
        return 0, df_work

    # ── Pass A: concept-tag filter (universal) ───────────────────────────────
    concept_rows = _filter_by_concept(df_raw, col, target)
    if concept_rows is not None:
        # Remap to normalised value column
        pos = df_work.loc[df_work.index.isin(concept_rows.index)].copy()
        match, ratio = _check_sum(pos, col, target)
        if match:
            n = len(pos)
            score = 70  # highest confidence — concept tags are unambiguous
            score += 20 if 2 <= n <= 8 else (10 if n <= 15 else 0)
            return score, pos
        # Even if sum is off, try subset on concept-filtered rows
        if ratio > 1.05:
            subset = _find_revenue_subset(pos, col, target)
            if subset is not None:
                n2 = len(subset)
                score = 60
                score += 20 if 2 <= n2 <= 8 else (10 if n2 <= 15 else 0)
                return score, subset

    # ── Pass B: label filter, direct sum ────────────────────────────────────
    pos_label = _filter_by_label(df_work, col, target)
    match, ratio = _check_sum(pos_label, col, target)
    if match:
        n = len(pos_label)
        score = 50
        score += 20 if 0.97 <= ratio <= 1.03 else 0
        score += 20 if 2 <= n <= 8 else (10 if n <= 15 else 0)
        return score, pos_label

    # ── Pass C: label filter + subset search ────────────────────────────────
    if pos_label is not None and len(pos_label) >= 2 and ratio > 1.05:
        subset = _find_revenue_subset(pos_label, col, target)
        if subset is not None:
            n2 = len(subset)
            score = 40
            score += 20 if 2 <= n2 <= 8 else (10 if n2 <= 15 else 0)
            return score, subset

    return 0, df_work


def find_segment_statements_dynamic(xbrl, total_revenues):
    """
    Universally find product-segment and geographic-segment statements for
    ANY ticker by:
      1. Skipping irrelevant statements (balance sheet, tax, leases, etc.)
      2. Scoring each candidate via concept-tag or label-based revenue matching
      3. Classifying winners as geo vs product by label content
    No hardcoded company names or role strings needed.
    """
    if not total_revenues:
        return None, None

    ref_yr = sorted(total_revenues.keys(), reverse=True)[0]
    prod_best = (0, None)
    geo_best  = (0, None)

    for s in xbrl.statements:
        if _is_income_statement(s):
            continue
        role = _stmt_role_clean(s)
        if any(kw in role for kw in SKIP_STMT_KEYWORDS):
            continue

        try:
            df_raw = s.to_dataframe()
            if 'label' not in df_raw.columns:
                continue
            year_cols = [c for c in df_raw.columns
                         if str(c)[:2] in ['19', '20'] and len(str(c)) >= 7]
            if not year_cols:
                continue

            # Build normalised numeric df (values in $M)
            df_work = df_raw[['label'] + year_cols].copy()
            for col in year_cols:
                df_work[col] = pd.to_numeric(
                    df_work[col].astype(str).str.replace(',', '').str.strip(),
                    errors='coerce'
                ) / 1_000_000
            df_work.columns = ['label'] + [c[:4] for c in sorted(year_cols, reverse=True)]
            year_cols_s = [c[:4] for c in sorted(year_cols, reverse=True)]

            # Pass df_raw too so concept column is accessible
            df_raw_aligned = df_raw.copy()
            df_raw_aligned.index = df_work.index

            score, pos_rows = _score_candidate(
                df_raw_aligned, df_work, year_cols_s, total_revenues, ref_yr
            )
            if score == 0:
                continue

            # Bonus: role name contains segment/revenue/disaggregat keywords
            ROLE_BONUS_KEYWORDS = [
                'segment', 'disaggregat', 'revenuebymarket', 'revenuebyproduct',
                'revenuebygeo', 'revenuebyregion', 'revenuebygeograph',
                'netrevenue', 'netsales',
            ]
            if any(kw in role for kw in ROLE_BONUS_KEYWORDS):
                score += 30  # strongly prefer tables explicitly named as segment/revenue

            # Classify: geo vs product by label content
            labels_lower = pos_rows['label'].str.lower().str.strip()
            geo_hits = labels_lower.str.contains(
                '|'.join(GEO_LABEL_KEYWORDS), na=False
            ).sum()
            geo_fraction = geo_hits / len(pos_rows) if len(pos_rows) > 0 else 0

            if geo_fraction >= 0.4:
                if score > geo_best[0]:
                    geo_best = (score, s)
            else:
                if score > prod_best[0]:
                    prod_best = (score, s)

        except Exception:
            continue

    return prod_best[1], geo_best[1]


def get_segment_statements(xbrl, total_revenues):
    """
    Find product and geo segment statements.
    Strategy:
      1. Try hardcoded role patterns (fast path for known companies: AAPL, GOOGL, MSFT)
      2. Fall back to dynamic sum-to-revenue scanner (works for any company)
    """
    statements = xbrl.statements
    prod_stmt = find_statement_by_role(statements, PRODUCT_ROLE_PATTERNS)
    geo_stmt  = find_statement_by_role(statements, GEO_ROLE_PATTERNS)

    if prod_stmt is None or geo_stmt is None:
        dyn_prod, dyn_geo = find_segment_statements_dynamic(xbrl, total_revenues)
        if prod_stmt is None and dyn_prod is not None:
            prod_stmt = dyn_prod
            print(f"      [dynamic] found product: {dyn_prod.role_or_type.split('/')[-1]}")
        if geo_stmt is None and dyn_geo is not None:
            geo_stmt = dyn_geo
            print(f"      [dynamic] found geo:     {dyn_geo.role_or_type.split('/')[-1]}")

    return prod_stmt, geo_stmt


def find_statement_by_role(statements, role_patterns):
    for pattern in role_patterns:
        for s in statements:
            role = s.role_or_type.replace(" ", "").replace("-", "").replace("_", "")
            if pattern.lower() in role.lower():
                return s
    return None

# ── Row cleaning ──────────────────────────────────────────────────────────────
def remove_noise_rows(df):
    pattern = '|'.join(EXCLUDE_ROW_PATTERNS)
    return df[~df['label'].astype(str).str.lower().str.contains(pattern, na=False)].reset_index(drop=True)


def apply_ticker_filter(df, allowlist):
    lower_allow = [r.lower() for r in allowlist]
    mask = df['label'].str.lower().str.strip().isin(lower_allow)
    return df[mask].reset_index(drop=True)


def remove_grand_total_rows(df, year_cols, total_revenues, tolerance=TOLERANCE):
    def is_grand_total(row):
        for yr in year_cols:
            if yr not in total_revenues or not total_revenues[yr]:
                continue
            val = pd.to_numeric(row.get(yr), errors='coerce')
            if pd.notna(val) and val > 0:
                if abs(val - total_revenues[yr]) / total_revenues[yr] <= tolerance:
                    return True
        return False
    return df[~df.apply(is_grand_total, axis=1)].reset_index(drop=True)


def remove_subtotal_rows(df, year_cols, tolerance=0.02):
    if df.empty or not year_cols:
        return df
    ref_year = max(
        (yr for yr in year_cols if yr in df.columns),
        key=lambda yr: pd.to_numeric(df[yr], errors='coerce').gt(0).sum()
    )
    removed_indices = set()
    changed = True
    while changed:
        changed = False
        working = df[~df.index.isin(removed_indices)].copy()
        vals = pd.to_numeric(working[ref_year], errors='coerce').fillna(0)
        rows = list(working.index)
        for i, idx in enumerate(rows):
            candidate_val = vals.get(idx, 0)
            if candidate_val <= 0:
                continue
            preceding = [r for r in rows[:i] if r not in removed_indices]
            if len(preceding) < 2:
                continue
            found = False
            for start in range(len(preceding)):
                window = preceding[start:]
                window_sum = sum(max(vals.get(r, 0), 0) for r in window)
                if window_sum > 0 and abs(window_sum - candidate_val) / candidate_val <= tolerance:
                    label = df.loc[idx, 'label']
                    print(f"      [subtotal removed] '{label}' ({candidate_val:,.0f}M) = sum of {len(window)} preceding rows")
                    removed_indices.add(idx)
                    changed = True
                    found = True
                    break
            if not found and len(preceding) <= 10:
                from itertools import combinations
                for r in range(2, len(preceding) + 1):
                    for combo in combinations(preceding, r):
                        combo_sum = sum(max(vals.get(c, 0), 0) for c in combo)
                        if combo_sum > 0 and abs(combo_sum - candidate_val) / candidate_val <= tolerance:
                            label = df.loc[idx, 'label']
                            print(f"      [subtotal removed] '{label}' ({candidate_val:,.0f}M) = sum of {r} rows")
                            removed_indices.add(idx)
                            changed = True
                            found = True
                            break
                    if found:
                        break
    return df[~df.index.isin(removed_indices)].reset_index(drop=True)


def validate_and_trim(df, year_cols, total_revenues, tolerance=TOLERANCE):
    if df.empty:
        return df
    ref_year = max(
        (yr for yr in year_cols if yr in df.columns),
        key=lambda yr: pd.to_numeric(df[yr], errors='coerce').gt(0).sum()
    )
    if ref_year not in total_revenues or not total_revenues[ref_year]:
        return df
    target = total_revenues[ref_year]
    for _ in range(10):
        vals = pd.to_numeric(df[ref_year], errors='coerce').fillna(0)
        current_sum = vals.sum()
        excess = current_sum - target
        if abs(excess) / target <= tolerance:
            break
        if excess <= 0:
            break
        best_idx, best_dist = None, float('inf')
        for idx in df.index:
            v = vals.get(idx, 0)
            if v <= 0:
                continue
            new_sum = current_sum - v
            if new_sum < target * (1 - tolerance):
                continue
            dist = abs(new_sum - target)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        if best_idx is None:
            break
        label = df.loc[best_idx, 'label']
        val = vals[best_idx]
        print(f"      [trim removed] '{label}' ({val:,.0f}M)")
        df = df.drop(index=best_idx).reset_index(drop=True)
    return df


def clean_segment_rows(df, year_cols, total_revenues):
    df = remove_noise_rows(df)
    df = remove_grand_total_rows(df, year_cols, total_revenues)
    df = df[df[year_cols].apply(
        lambda col: pd.to_numeric(col, errors='coerce') > 0
    ).any(axis=1)].reset_index(drop=True)
    if df.empty:
        return df
    df = remove_subtotal_rows(df, year_cols)
    df = validate_and_trim(df, year_cols, total_revenues)
    return df

# ── Table building & output ───────────────────────────────────────────────────
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
            'actual':   actual,
            'expected': expected,
            'pct_diff': pct_diff,
            'valid':    pct_diff <= tolerance,
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
        curr, prev = year_cols[i], year_cols[i + 1]
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
            fmt.loc[idx, col] = 'N/A' if pd.isna(val) else f"{'+'if val > 0 else ''}{val:.1f}%"
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

        filing_revenues = get_revenue_anchor(xbrl)
        if not filing_revenues:
            print(f"    [!] No revenue anchor — skipping")
            continue
        for yr, rev in filing_revenues.items():
            if yr not in total_revenues:
                total_revenues[yr] = rev
        print(f"    Anchors: { {k: f'${v:,.0f}M' for k, v in sorted(filing_revenues.items(), reverse=True)} }")

        prod_stmt, geo_stmt = get_segment_statements(xbrl, filing_revenues)

        # ── Product segments ──
        if prod_stmt:
            df, year_cols = extract_df(prod_stmt, clean_prefix="Operating segments - ")
            if df is not None:
                print(f"    [product] {prod_stmt.role_or_type.split('/')[-1]}")
                prod_allowlist = TICKER_PRODUCT_ROWS.get(TICKER)
                if prod_allowlist:
                    df_clean = apply_ticker_filter(df, prod_allowlist)
                else:
                    df_clean = clean_segment_rows(df, year_cols, filing_revenues)
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
                    print(f"             years added: {added}")
        else:
            print(f"    [!] No product statement found")

        # ── Geographic segments ──
        if geo_stmt:
            df, year_cols = extract_df(geo_stmt, clean_prefix="Operating segments - ")
            if df is not None:
                print(f"    [geo]     {geo_stmt.role_or_type.split('/')[-1]}")
                geo_allowlist = TICKER_GEO_ROWS.get(TICKER)
                if geo_allowlist:
                    df_clean = apply_ticker_filter(df, geo_allowlist)
                else:
                    df_clean = clean_segment_rows(df, year_cols, filing_revenues)
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
                    print(f"             years added: {added}")
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