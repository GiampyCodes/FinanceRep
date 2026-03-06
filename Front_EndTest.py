import tkinter as tk
from tkinter import ttk

def main():
    # 1. Create the main window (the "root")
    root = tk.Tk()
    root.title("Python Code Preview")
    
    # Set the window size (Width x Height)
    root.geometry("600x400")
    
    # 2. Add some styling for a modern look
    style = ttk.Style()
    style.theme_use('clam') # 'clam', 'alt', 'default', or 'classic'

    # 3. Create a Main Frame (Container)
    main_frame = ttk.Frame(root, padding="20")
    main_frame.pack(fill=tk.BOTH, expand=True)

    # 4. Add a Title Label
    title_label = ttk.Label(
        main_frame, 
        text="If you're reading this you're gay!", 
        font=("Segoe UI", 18, "bold")
    )
    title_label.pack(pady=(0, 10))

    # 5. Add a Text Area (like a console or preview pane)
    preview_text = tk.Text(
        main_frame, 
        height=10, 
        font=("Consolas", 11),
        padx=10,
        pady=10,
        bg="#f0f0f0",
        relief="flat"
    )
    preview_text.pack(fill=tk.BOTH, expand=True)
    
    # Insert some initial content
    preview_text.insert(tk.END, "jk\n")
    preview_text.insert(tk.END, "<3\n")
    preview_text.insert(tk.END, "-" * 30 + "\n")
    preview_text.insert(tk.END, "47th>48th")
    
    # Disable editing so it acts as a "preview" only
    preview_text.config(state=tk.DISABLED)

    # 6. Add a Close Button
    close_button = ttk.Button(main_frame, text="Close Window", command=root.destroy)
    close_button.pack(pady=(15, 0))

    # 7. Start the application loop (This keeps the window open)
    root.mainloop()

if __name__ == "__main__":
    main()