import yfinance as yf
import pandas as pd

# 1. Setup formatting for clean numbers (No scientific notation)
pd.options.display.float_format = '{:,.0f}'.format 

# 2. Pick a company
ticker = "AAPL"
company = yf.Ticker(ticker)

# 3. Pull the income statement
# Using .income_stmt is the modern, reliable way
income_stmt = company.income_stmt

# 4. Define your Y-Axis (The categories)
desired_rows = ['Total Revenue', 'Operating Income', 'Net Income']

# Filter to only use rows that exist
available_rows = [row for row in desired_rows if row in income_stmt.index]

if available_rows:
    # Select the rows (This keeps categories on the Y-Axis)
    clean_data = income_stmt.loc[available_rows]
    
    # SORT COLUMNS: Newest first (Descending)
    # This ensures 2025/2026 is on the left and 2020 is on the right
    clean_data = clean_data.reindex(sorted(clean_data.columns, reverse=True), axis=1)

    print(f"--- {ticker} Financial History (Newest First) ---")
    print(clean_data)
else:
    print(f"Metrics not found. Available rows: {list(income_stmt.index)}")
