import yfinance as yf
import pandas as pd

# Formatting Setup
pd.options.display.float_format = '{:,.0f}'.format # ,.0f removes decimals for cleaner Millions/Billions
#:, : Adds a comma every three digits (1,000,000).
#.0f : Shows zero decimal places (since financial statements usually round to the nearest dollar or million). Use .2f if you want cents.

# Pick a company (Ticker symbol)
ticker = "AAPL"
company = yf.Ticker(ticker)
income_stmt = company.financials

# Filter for what you want
desired_rows = ['Total Revenue', 'Operating Income', 'Net Income']
clean_data = income_stmt.loc[desired_rows]

print(f"--- {ticker} Financials (In USD) ---")
print(clean_data)


