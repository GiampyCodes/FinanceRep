import tkinter as tk
from tkinter import ttk, messagebox
import yfinance as yf
import pandas as pd

class FinancialDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Pro Financial Explorer")
        self.root.geometry("900x450")
        
        # 1. Apply Professional Styling & Colors
        self.root.configure(bg="#f4f6f9")
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.style.configure("TFrame", background="#f4f6f9")
        self.style.configure("TLabel", background="#f4f6f9", font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 22, "bold"), foreground="#2c3e50")
        self.style.configure("Action.TButton", font=("Segoe UI", 10, "bold"), padding=5)
        
        # Style the Data Table (Treeview)
        self.style.configure("Treeview.Heading", font=("Segoe UI", 11, "bold"), background="#e1e8ed", foreground="#2c3e50")
        self.style.configure("Treeview", font=("Consolas", 11), rowheight=35, background="#ffffff")
        
        self.setup_ui()

    def setup_ui(self):
        """Builds the user interface."""
        main_frame = ttk.Frame(self.root, padding="25")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Label(main_frame, text="Financial Data Explorer", style="Header.TLabel")
        header.pack(anchor=tk.W, pady=(0, 15))

        # Search Bar Area
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(search_frame, text="Enter Ticker Symbol:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.ticker_entry = ttk.Entry(search_frame, font=("Segoe UI", 12), width=15)
        self.ticker_entry.insert(0, "AAPL") # Default value
        self.ticker_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Bind the Enter key to the search button
        self.root.bind('<Return>', lambda event: self.load_data())

        self.search_btn = ttk.Button(search_frame, text="Fetch Data", style="Action.TButton", command=self.load_data)
        self.search_btn.pack(side=tk.LEFT)
        
        self.status_label = ttk.Label(search_frame, text="", foreground="#7f8c8d")
        self.status_label.pack(side=tk.LEFT, padx=(15, 0))

        # Data Table (Treeview) Area
        table_frame = ttk.Frame(main_frame)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollbar for the table
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree = ttk.Treeview(table_frame, yscrollcommand=scrollbar.set, selectmode="none")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tree.yview)

    def load_data(self):
        """Fetches data from yfinance and populates the table."""
        ticker = self.ticker_entry.get().strip().upper()
        if not ticker:
            messagebox.showwarning("Input Error", "Please enter a ticker symbol.")
            return

        self.status_label.config(text=f"Fetching data for {ticker}...")
        self.root.update() # Force UI to update the status text
        
        try:
            company = yf.Ticker(ticker)
            income_stmt = company.income_stmt
            
            desired_rows = ['Total Revenue', 'Operating Income', 'Net Income']
            available_rows = [row for row in desired_rows if row in income_stmt.index]
            
            if not available_rows:
                messagebox.showinfo("No Data", f"Financial metrics not found for {ticker}.")
                self.status_label.config(text="")
                return

            # Clean and sort the data
            clean_data = income_stmt.loc[available_rows]
            clean_data = clean_data.reindex(sorted(clean_data.columns, reverse=True), axis=1)
            
            self.update_table(clean_data)
            self.status_label.config(text=f"Successfully loaded {ticker}.")
            
        except Exception as e:
            self.status_label.config(text="")
            messagebox.showerror("Error", f"Failed to fetch data.\n\nDetails: {e}")

    def update_table(self, df):
        """Clears the old table and inserts the new Pandas DataFrame."""
        # 1. Clear existing data
        self.tree.delete(*self.tree.get_children())
        
        # 2. Extract column names (Convert timestamps to Year-Strings if applicable)
        # Using string formatting so we just get "2023" instead of "2023-09-30 00:00:00"
        date_columns = [col.strftime('%Y-%m-%d') if hasattr(col, 'strftime') else str(col) for col in df.columns]
        columns = ["Metric"] + date_columns
        
        self.tree["columns"] = columns
        self.tree["show"] = "headings" # Hide the default blank first column

        # 3. Set up column headers and widths
        self.tree.heading("Metric", text="Financial Metric", anchor=tk.W)
        self.tree.column("Metric", width=200, anchor=tk.W)
        
        for col in date_columns:
            self.tree.heading(col, text=col, anchor=tk.E)
            self.tree.column(col, width=120, anchor=tk.E)

        # 4. Insert the rows
        for index, row in df.iterrows():
            # Format numbers to include commas and remove decimals
            formatted_values = [f"{val:,.0f}" if pd.notnull(val) else "N/A" for val in row.values]
            
            # Combine the metric name (index) with the formatted values
            row_data = [index] + formatted_values
            self.tree.insert("", tk.END, values=row_data)

def main():
    root = tk.Tk()
    app = FinancialDashboard(root)
    root.mainloop()

if __name__ == "__main__":
    main()