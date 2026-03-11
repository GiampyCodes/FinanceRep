import os
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TICKERS_FILE = os.path.join(BASE_DIR, "tickers.csv")
OUTPUT_FILE  = os.path.join(BASE_DIR, "historical_data.xlsx")

# ── Date range: last 5 years ──────────────────────────────────────────────────
end_date   = datetime.today()
start_date = end_date - timedelta(days=5 * 365)

# ── Column layout ─────────────────────────────────────────────────────────────
# A=date  B=open  C=high  D=low  E=close  F=volume
# G=Long Range   H=Short Range
# I=Long N       J=Short N
# K=20 Day Low   L=20 Day High
# M=20 Day Low (High) 120D

HEADERS = {
    "G": "Long Range",
    "H": "Short Range",
    "I": "Long N",
    "J": "Short N",
    "K": "20 Day Low",
    "L": "20 Day High",
    "M": "20 Day Low (High) 120D",
}

# ── Read tickers ──────────────────────────────────────────────────────────────
tickers_df = pd.read_csv(TICKERS_FILE, header=None, names=["ticker"])
tickers    = tickers_df["ticker"].str.strip().tolist()
print(f"Tickers loaded: {tickers}")

# ── Helpers ───────────────────────────────────────────────────────────────────
def cap(row, offset, last_row):
    """Return the capped end row so formulas never exceed the data range."""
    return min(row + offset, last_row)


def build_formulas(r, last_row):
    """
    Return a dict of column → Excel formula string for data row at Excel row r.

    Windows (data sorted descending → older rows sit further DOWN the sheet):
      Long Range  : MAX(high, 20 rows) - MIN(low, 40 rows)
      Short Range : MAX(high, 120 rows) - MIN(low, 20 rows)
      Long N      : Long Range / 5
      Short N     : Short Range / 5
      20 Day Low  : MIN(low, 20 rows)
      20 Day High : MAX(high, 20 rows)
      20DL High120D: MAX(20-Day-Low column, 120 rows)
    """
    h20  = cap(r, 19,  last_row)   # 20-row  high window end
    h120 = cap(r, 119, last_row)   # 120-row high window end
    l20  = cap(r, 19,  last_row)   # 20-row  low window end
    l40  = cap(r, 39,  last_row)   # 40-row  low window end

    return {
        "G": f"=MAX(C{r}:C{h20})-MIN(D{r}:D{l40})",
        "H": f"=MAX(C{r}:C{h120})-MIN(D{r}:D{l20})",
        "I": f"=G{r}/5",
        "J": f"=H{r}/5",
        "K": f"=MIN(D{r}:D{l20})",
        "L": f"=MAX(C{r}:C{h20})",
        "M": f"=MAX(K{r}:K{cap(r, 119, last_row)})",
    }


# ── Fetch, write OHLC + Volume, inject live Excel formulas ───────────────────
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
    for ticker in tickers:
        print(f"Fetching {ticker}...")
        try:
            raw = yf.download(
                ticker,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                auto_adjust=True,
                progress=False,
            )

            if raw.empty:
                print(f"  WARNING: No data for {ticker}, skipping.")
                continue

            # ── Build OHLCV frame, newest date first ───────────────────────
            df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = ["open", "high", "low", "close", "volume"]
            df.index.name = "date"
            df.reset_index(inplace=True)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            df.sort_values("date", ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)

            # ── Write OHLCV to sheet ───────────────────────────────────────
            df.to_excel(writer, sheet_name=ticker, index=False, float_format="%.4f")

            ws       = writer.sheets[ticker]
            n        = len(df)
            LAST_ROW = n + 1        # Excel row of the last data row (row 1 = header)

            # ── Write formula column headers ───────────────────────────────
            for col_letter, label in HEADERS.items():
                ws[f"{col_letter}1"] = label

            # ── Write live formulas row by row ─────────────────────────────
            for i in range(n):
                r       = i + 2     # Excel row (1=header, 2=first data row)
                formulas = build_formulas(r, LAST_ROW)
                for col_letter, formula in formulas.items():
                    ws[f"{col_letter}{r}"] = formula

            print(f"  {n} rows → sheet '{ticker}' (formulas written)")

        except Exception as e:
            print(f"  ERROR fetching {ticker}: {e}")

print(f"\nDone. Output saved to: {OUTPUT_FILE}")
