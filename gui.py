#!/usr/bin/env python3
"""
QAPP GUI — Simple graphical interface for the MEDSL Precinct QA Engine.

Provides a user-friendly way to:
- Select a CSV file to QA
- Choose which checks to run (with filter-by-column support)
- Select output format (Excel, Legacy text, or Both)
- Run the QA and view results

Launch with: python gui.py
Or via CLI: python qapp.py --gui
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import subprocess
import platform
from PIL import Image, ImageTk

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from qa_core import config
from qa_core.runner import run_qa, OUTPUT_EXCEL, OUTPUT_LEGACY, OUTPUT_BOTH


class QAPPGui:
    """Main GUI application for QAPP."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("QAPP — MEDSL Precinct QA Engine")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)

        # Variables
        self.csv_path = tk.StringVar()
        self.output_mode = tk.StringVar(value="excel")
        self.all_checks_var = tk.BooleanVar(value=True)
        self.filter_columns_var = tk.StringVar()
        self.check_vars: dict[str, tk.BooleanVar] = {}
        self.is_running = False
        
        # Progress tracking
        self.progress_value = tk.DoubleVar(value=0)
        
        # Load logo image
        self.logo_image = None
        self.logo_photo = None
        self._load_logo()

        self._create_widgets()

    def _load_logo(self):
        """Load and prepare the logo image."""
        logo_path = REPO_ROOT / "logo.png"
        if not logo_path.exists():
            return
        
        try:
            img = Image.open(logo_path)
            # Resize logo to fit nicely in header (height ~126px)
            img.thumbnail((200, 126), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Failed to load logo: {e}")

    def _create_widgets(self):
        """Create all GUI widgets."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        # --- Title Header ---
        header_frame = ttk.Frame(main_frame)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        header_frame.columnconfigure(0, weight=1)
        
        # Title with QAPP highlighted
        title_frame = ttk.Frame(header_frame)
        title_frame.grid(row=0, column=0, sticky="w")
        
        # Create styled title: "Quality Assurance for the Precinct Project"
        # with Q, A, P, P bolded
        title_text = tk.Text(title_frame, height=1, width=45, borderwidth=0, 
                            highlightthickness=0, wrap="none", cursor="arrow")
        title_text.configure(background=self.root.cget("bg"), font=("TkDefaultFont", 14))
        
        # Configure tags for bold letters
        title_text.tag_configure("bold", font=("TkDefaultFont", 14, "bold"), foreground="#3791FF")
        title_text.tag_configure("normal", font=("TkDefaultFont", 14), foreground="#0B2E4F")
        
        # Insert styled text
        title_text.insert("end", "Q", "bold")
        title_text.insert("end", "uality ", "normal")
        title_text.insert("end", "A", "bold")
        title_text.insert("end", "ssurance for the ", "normal")
        title_text.insert("end", "P", "bold")
        title_text.insert("end", "recinct ", "normal")
        title_text.insert("end", "P", "bold")
        title_text.insert("end", "roject", "normal")
        
        title_text.configure(state="disabled")
        title_text.grid(row=0, column=0, sticky="w")
        
        # Logo in top right
        if self.logo_photo:
            logo_label = ttk.Label(header_frame, image=self.logo_photo)
            logo_label.grid(row=0, column=1, sticky="e", padx=(10, 0))

        # --- File Selection ---
        file_frame = ttk.LabelFrame(main_frame, text="1. Select CSV File", padding="5")
        file_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        ttk.Entry(file_frame, textvariable=self.csv_path, width=60).grid(row=0, column=1, sticky="ew", padx=(0, 5))
        ttk.Button(file_frame, text="Browse...", command=self._browse_file).grid(row=0, column=2)

        # --- Output Format ---
        output_frame = ttk.LabelFrame(main_frame, text="2. Select Output Format", padding="5")
        output_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ttk.Radiobutton(output_frame, text="Excel Report (default)", variable=self.output_mode, value="excel").grid(row=0, column=0, sticky="w", padx=(0, 20))
        ttk.Radiobutton(output_frame, text="Legacy Text Files", variable=self.output_mode, value="legacy").grid(row=0, column=1, sticky="w", padx=(0, 20))
        ttk.Radiobutton(output_frame, text="Both", variable=self.output_mode, value="both").grid(row=0, column=2, sticky="w")

        # --- Check Selection ---
        checks_frame = ttk.LabelFrame(main_frame, text="3. Select Checks", padding="5")
        checks_frame.grid(row=3, column=0, sticky="nsew", pady=(0, 10))
        main_frame.rowconfigure(3, weight=1)

        # Controls row
        controls_frame = ttk.Frame(checks_frame)
        controls_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        controls_frame.columnconfigure(2, weight=1)

        ttk.Checkbutton(controls_frame, text="All Checks", variable=self.all_checks_var, command=self._toggle_all_checks).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ttk.Button(controls_frame, text="Check All", command=lambda: self._set_all_checks(True)).grid(row=0, column=1, padx=(0, 5))
        ttk.Button(controls_frame, text="Uncheck All", command=lambda: self._set_all_checks(False)).grid(row=0, column=2, sticky="w")

        # Filter by column with autocomplete
        filter_frame = ttk.Frame(checks_frame)
        filter_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        filter_frame.columnconfigure(1, weight=1)

        ttk.Label(filter_frame, text="Filter by column(s):").grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        # Create autocomplete combobox for column filter
        self.column_combobox = ttk.Combobox(filter_frame, textvariable=self.filter_columns_var, width=40)
        self.column_combobox['values'] = config.REQUIRED_COLUMNS
        self.column_combobox.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        self.column_combobox.bind('<KeyRelease>', self._on_column_filter_keyrelease)
        self.column_combobox.bind('<<ComboboxSelected>>', self._on_column_selected)
        
        ttk.Button(filter_frame, text="Apply Filter", command=self._apply_column_filter).grid(row=0, column=2)
        ttk.Label(filter_frame, text="(type to autocomplete, comma-separate for multiple)", font=("TkDefaultFont", 9, "italic")).grid(row=1, column=1, sticky="w")

        # Scrollable check list
        list_frame = ttk.Frame(checks_frame)
        list_frame.grid(row=2, column=0, sticky="nsew")
        checks_frame.rowconfigure(2, weight=1)
        checks_frame.columnconfigure(0, weight=1)

        canvas = tk.Canvas(list_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.checks_inner_frame = ttk.Frame(canvas)

        self.checks_inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.checks_inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # Populate checks
        self._populate_checks()

        # --- Run Button ---
        run_frame = ttk.Frame(main_frame)
        run_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        run_frame.columnconfigure(1, weight=1)

        self.run_button = ttk.Button(run_frame, text="Run QA", command=self._run_qa, style="Accent.TButton")
        self.run_button.grid(row=0, column=0, padx=(0, 10))

        # Determinate progress bar that fills as we make progress
        self.progress = ttk.Progressbar(run_frame, mode="determinate", variable=self.progress_value, length=300)
        self.progress.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        self.status_label = ttk.Label(run_frame, text="Ready")
        self.status_label.grid(row=0, column=2, sticky="w")

        # --- Log Output ---
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="5")
        log_frame.grid(row=5, column=0, sticky="nsew")
        main_frame.rowconfigure(5, weight=1)

        self.log_text = tk.Text(log_frame, height=8, wrap="word", state="disabled")
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

    def _populate_checks(self):
        """Populate the checks list from config.AVAILABLE_CHECKS."""
        # Clear existing
        for widget in self.checks_inner_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()

        # Group checks by category
        by_category: dict[str, list[tuple[str, dict]]] = {}
        for key, info in config.AVAILABLE_CHECKS.items():
            cat = info.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append((key, info))

        row = 0
        for cat, checks in by_category.items():
            cat_label = config.CHECK_CATEGORIES.get(cat, cat.title())
            ttk.Label(self.checks_inner_frame, text=cat_label, font=("TkDefaultFont", 10, "bold")).grid(row=row, column=0, sticky="w", pady=(10, 2))
            row += 1

            for key, info in checks:
                var = tk.BooleanVar(value=True)
                self.check_vars[key] = var
                cols = ", ".join(info.get("columns", [])) or "all columns"
                text = f"{key}: {info['label']} [{cols}]"
                cb = ttk.Checkbutton(self.checks_inner_frame, text=text, variable=var, command=self._on_check_changed)
                cb.grid(row=row, column=0, sticky="w", padx=(20, 0))
                row += 1

    def _browse_file(self):
        """Open file dialog to select a CSV file."""
        path = filedialog.askopenfilename(
            title="Select CSV file to QA",
            filetypes=[("CSV files", "*.csv"), ("TSV files", "*.tsv"), ("All files", "*.*")]
        )
        if path:
            self.csv_path.set(path)

    def _toggle_all_checks(self):
        """Toggle all checks based on 'All Checks' checkbox."""
        val = self.all_checks_var.get()
        for var in self.check_vars.values():
            var.set(val)

    def _set_all_checks(self, value: bool):
        """Set all checks to a specific value."""
        self.all_checks_var.set(value)
        for var in self.check_vars.values():
            var.set(value)

    def _on_check_changed(self):
        """Update 'All Checks' checkbox state based on individual checks."""
        all_checked = all(var.get() for var in self.check_vars.values())
        self.all_checks_var.set(all_checked)

    def _on_column_filter_keyrelease(self, event):
        """Handle keyrelease in column filter for autocomplete."""
        # Ignore navigation keys
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Return', 'Tab', 'Escape'):
            return
        
        current_text = self.filter_columns_var.get()
        
        # Get the part after the last comma (for multi-column support)
        if ',' in current_text:
            prefix = current_text.rsplit(',', 1)[0] + ','
            search_term = current_text.rsplit(',', 1)[1].strip().lower()
        else:
            prefix = ''
            search_term = current_text.strip().lower()
        
        if not search_term:
            # Show all columns when empty
            self.column_combobox['values'] = config.REQUIRED_COLUMNS
            return
        
        # Filter columns that match the search term
        matching = [col for col in config.REQUIRED_COLUMNS if search_term in col.lower()]
        
        if matching:
            self.column_combobox['values'] = matching
            # Open dropdown to show suggestions
            self.column_combobox.event_generate('<Down>')
        else:
            self.column_combobox['values'] = config.REQUIRED_COLUMNS

    def _on_column_selected(self, event):
        """Handle column selection from dropdown."""
        selected = self.column_combobox.get()
        current_text = self.filter_columns_var.get()
        
        # If there's already comma-separated content, append to it
        if ',' in current_text:
            # Get everything before the last comma
            prefix = current_text.rsplit(',', 1)[0]
            # Check if the selected value is a full column name
            if selected in config.REQUIRED_COLUMNS:
                self.filter_columns_var.set(f"{prefix},{selected}")
        
        # Reset dropdown to show all columns
        self.column_combobox['values'] = config.REQUIRED_COLUMNS

    def _apply_column_filter(self):
        """Filter checks by column names."""
        filter_text = self.filter_columns_var.get().strip()
        if not filter_text:
            self._set_all_checks(True)
            return

        columns = [c.strip() for c in filter_text.split(",") if c.strip()]
        matching_keys = set(config.get_checks_for_columns(columns))

        for key, var in self.check_vars.items():
            var.set(key in matching_keys)

        self._on_check_changed()
        self._log(f"Filtered to {len(matching_keys)} checks for columns: {', '.join(columns)}")

    def _log(self, message: str):
        """Add a message to the log output."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _update_progress(self, value: float, status: str = None):
        """Update progress bar (thread-safe)."""
        def update():
            self.progress_value.set(value)
            if status:
                self.status_label.configure(text=status)
        self.root.after(0, update)

    def _run_qa(self):
        """Run the QA engine in a background thread."""
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showerror("Error", "Please select a CSV file first.")
            return

        if not Path(csv_path).exists():
            messagebox.showerror("Error", f"File not found: {csv_path}")
            return

        if self.is_running:
            messagebox.showwarning("Warning", "QA is already running.")
            return

        # Gather selected checks
        selected_checks = {key for key, var in self.check_vars.items() if var.get()}
        if not selected_checks:
            messagebox.showerror("Error", "Please select at least one check to run.")
            return

        # Start QA in background thread
        self.is_running = True
        self.run_button.configure(state="disabled")
        self.progress_value.set(0)
        self.status_label.configure(text="Loading data...")
        self._log(f"Starting QA on: {csv_path}")
        self._log(f"Running {len(selected_checks)} checks...")

        def run_thread():
            try:
                output_mode_map = {
                    "excel": OUTPUT_EXCEL,
                    "legacy": OUTPUT_LEGACY,
                    "both": OUTPUT_BOTH,
                }
                mode = output_mode_map.get(self.output_mode.get(), OUTPUT_EXCEL)

                # Update progress: Loading
                self._update_progress(10, "Loading data...")
                
                # Let runner.py handle all output modes (including legacy)
                result = run_qa(csv_path, include_checks=selected_checks, output_mode=mode)
                
                # Update progress: Complete
                self._update_progress(100, "Complete!")

                self.root.after(0, lambda: self._on_qa_complete(result, mode))
            except Exception as e:
                self.root.after(0, lambda: self._on_qa_error(str(e)))

        thread = threading.Thread(target=run_thread, daemon=True)
        thread.start()

    def _on_qa_complete(self, result: dict, output_mode: str):
        """Called when QA completes successfully."""
        self.is_running = False
        self.run_button.configure(state="normal")
        self.progress_value.set(100)
        self.status_label.configure(text="Complete!")

        excel_path = result.get("excel_path") if result else None
        legacy_dir = result.get("legacy_dir") if result else None

        self._log("QA completed successfully!")
        if excel_path:
            self._log(f"Excel Report: {excel_path}")
        if legacy_dir:
            self._log(f"Legacy Files: {legacy_dir}")

        # Show completion dialog with options based on what was produced
        self._show_completion_dialog(excel_path, legacy_dir, output_mode)

    def _show_completion_dialog(self, excel_path: Path | None, legacy_dir: Path | None, output_mode: str):
        """Show completion dialog with options to open outputs."""
        dialog = tk.Toplevel(self.root)
        dialog.title("QA Complete")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog on parent
        dialog.geometry("450x250")
        dialog_frame = ttk.Frame(dialog, padding="20")
        dialog_frame.pack(fill="both", expand=True)
        
        # Success message
        ttk.Label(dialog_frame, text="✓ QA completed successfully!", 
                  font=("TkDefaultFont", 12, "bold"), foreground="#37C256").pack(pady=(0, 15))
        
        # Show paths
        if excel_path:
            ttk.Label(dialog_frame, text=f"Excel Report:\n{excel_path}", 
                      wraplength=400, justify="center").pack(pady=(0, 5))
        if legacy_dir:
            ttk.Label(dialog_frame, text=f"Legacy Files:\n{legacy_dir}", 
                      wraplength=400, justify="center").pack(pady=(0, 10))
        
        # Buttons frame
        btn_frame = ttk.Frame(dialog_frame)
        btn_frame.pack(pady=(15, 0))
        
        def open_excel():
            if excel_path:
                self._open_file(excel_path)
            dialog.destroy()
        
        def open_legacy():
            if legacy_dir:
                self._open_folder(legacy_dir)
            dialog.destroy()
        
        def open_both():
            if excel_path:
                self._open_file(excel_path)
            if legacy_dir:
                self._open_folder(legacy_dir)
            dialog.destroy()
        
        def close_dialog():
            dialog.destroy()
        
        # Show buttons based on what was produced
        if output_mode == OUTPUT_BOTH and excel_path and legacy_dir:
            ttk.Button(btn_frame, text="Open Excel Report", command=open_excel).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Open Legacy Folder", command=open_legacy).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="Open Both", command=open_both, style="Accent.TButton").pack(side="left", padx=5)
        elif excel_path:
            ttk.Button(btn_frame, text="Open Excel Report", command=open_excel, style="Accent.TButton").pack(side="left", padx=5)
        elif legacy_dir:
            ttk.Button(btn_frame, text="Open Legacy Folder", command=open_legacy, style="Accent.TButton").pack(side="left", padx=5)
        
        ttk.Button(btn_frame, text="Close", command=close_dialog).pack(side="left", padx=5)
        
        # Center dialog
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

    def _on_qa_error(self, error: str):
        """Called when QA fails with an error."""
        self.is_running = False
        self.run_button.configure(state="normal")
        self.progress_value.set(0)
        self.status_label.configure(text="Error")

        self._log(f"ERROR: {error}")
        messagebox.showerror("QA Error", f"An error occurred:\n\n{error}")

    def _open_file(self, path: Path):
        """Open a file with the system default application."""
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", str(path)])
            elif system == "Windows":
                import os
                os.startfile(str(path))
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._log(f"Failed to open file: {e}")

    def _open_folder(self, path: Path):
        """Open a folder with the system file manager."""
        system = platform.system()
        try:
            if system == "Darwin":
                subprocess.Popen(["open", str(path)])
            elif system == "Windows":
                subprocess.Popen(["explorer", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as e:
            self._log(f"Failed to open folder: {e}")


def main():
    """Launch the QAPP GUI."""
    root = tk.Tk()

    # Use MEDSL brand colors
    try:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        
        # MEDSL Color Palette
        logo_blue = "#3791FF"      # Primary accent
        dark_blue = "#156DD0"      # Hover/pressed states
        navy = "#0B2E4F"           # Dark text/headers
        light_blue = "#59CBF5"     # Highlights
        blue_7 = "#9FDDF3"         # Very light blue
        text_gray = "#525971"      # Secondary text
        chart_gray = "#C4C4C4"     # Borders/dividers
        bg_color = "#f8fafc"       # Light background (slight blue tint)
        
        # Configure the root window background
        root.configure(bg=bg_color)
        
        # Configure ttk styles
        style.configure(".", background=bg_color, foreground=navy)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color)
        style.configure("TLabelframe.Label", background=bg_color, foreground=navy, font=("TkDefaultFont", 10, "bold"))
        style.configure("TLabel", background=bg_color, foreground=navy)
        style.configure("TCheckbutton", background=bg_color, foreground=navy)
        style.configure("TRadiobutton", background=bg_color, foreground=navy)
        style.configure("TEntry", fieldbackground="white")
        style.configure("TCombobox", fieldbackground="white")
        
        # Style buttons with MEDSL Logo Blue
        style.configure("TButton", padding=6, background=chart_gray)
        style.map("TButton",
                  background=[("active", logo_blue)],
                  foreground=[("active", "white")])
        
        # Accent button (Run QA) with Logo Blue
        style.configure("Accent.TButton", 
                       background=logo_blue, 
                       foreground="white",
                       padding=10,
                       font=("TkDefaultFont", 11, "bold"))
        style.map("Accent.TButton",
                  background=[("active", dark_blue), ("pressed", navy)],
                  foreground=[("active", "white"), ("pressed", "white")])
        
        # Progress bar with MEDSL blue
        style.configure("TProgressbar", 
                       background=logo_blue,
                       troughcolor=chart_gray)
        
    except Exception:
        pass

    app = QAPPGui(root)
    
    # Bring window to front (basic cross-platform approach)
    def raise_window():
        root.lift()
        root.focus_set()
    
    # Schedule the raise after window is initialized
    root.after(100, raise_window)
    
    root.mainloop()


if __name__ == "__main__":
    main()
