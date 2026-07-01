import os
import sys
import time
import math
import random
import ctypes
import threading
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import speech_recognition as sr
import pyttsx3
from datetime import datetime

HAS_SOUNDDEVICE = False
try:
    import sounddevice as sd
    import numpy as np
    HAS_SOUNDDEVICE = True
except ImportError:
    pass

# Set default customtkinter theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AuraVoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Voice Expense Manager")
        self.geometry("1180x780")
        self.minsize(1100, 720)
        
        # Center window on load
        self.center_window()
        
        # App State variables
        self.app_state = "LOADING_MODEL" # LOADING_MODEL, READY, LISTENING, PROCESSING, SUCCESS, ERROR
        self.recording_active = False
        self.tts_speaking = False
        self.tts_engine = None
        
        # Waveform animation settings
        self.phase = 0.0
        self.target_amplitude = 8.0
        self.current_amplitude = 8.0
        self.ripple_radius = 45.0
        self.animation_running = True
        
        # Setup colors
        self.setup_colors()
        
        # Setup UI layout
        self.create_layout()
        
        # Start the canvas visualizer loop
        self.run_visualizer_loop()
        
        # Responsive layout configuration state
        self.current_layout_mode = None
        self.bind("<Configure>", self.on_window_resize)
        
        # Load LLM in background thread
        self.llm = None
        self.model_loading = True
        threading.Thread(target=self.async_load_llm, daemon=True).start()
        
        # Bind keyboard shortcuts & close event
        self.bind("<Control-c>", lambda e: self.copy_to_clipboard())
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Populate initial database stats
        self.refresh_dashboard()

    def center_window(self):
        self.update_idletasks()
        w = 1180
        h = 780
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def setup_colors(self):
        # Premium dark/light palettes
        self.colors_dark = {
            "bg_app": "#0A0A0C",
            "bg_sidebar": "#121216",
            "bg_panel": "#161620",
            "bg_card": "#21212B",
            "accent_primary": "#00E5FF",   # Cyan
            "accent_secondary": "#A855F7", # Neon Purple
            "accent_tertiary": "#14B8A6",  # Teal
            "accent_success": "#10B981",   # Emerald Green
            "accent_error": "#EF4444",     # Red
            "text_bright": "#F8FAFC",
            "text_muted": "#64748B",
            "border": "#2D2D3B"
        }
        
        self.colors_light = {
            "bg_app": "#F8FAFC",
            "bg_sidebar": "#FFFFFF",
            "bg_panel": "#F1F5F9",
            "bg_card": "#E2E8F0",
            "accent_primary": "#0284C7",   # Sky Blue
            "accent_secondary": "#7C3AED", # Violet
            "accent_tertiary": "#0D9488",  # Teal
            "accent_success": "#16A34A",   # Green
            "accent_error": "#DC2626",     # Red
            "text_bright": "#0F172A",
            "text_muted": "#64748B",
            "border": "#CBD5E1"
        }
        
        self.colors = self.colors_dark

    def toggle_theme(self):
        if self.theme_switch.get() == 1:
            ctk.set_appearance_mode("dark")
            self.colors = self.colors_dark
        else:
            ctk.set_appearance_mode("light")
            self.colors = self.colors_light
            
        # Update canvas configurations directly
        self.canvas.configure(bg=self.colors["bg_app"], highlightbackground=self.colors["bg_app"])
        
        # Redraw GUI elements colors
        self.sidebar.configure(fg_color=self.colors["bg_sidebar"])
        self.main_content.configure(fg_color=self.colors["bg_app"])
        self.header_frame.configure(fg_color="transparent")
        self.kpis_container.configure(fg_color="transparent")
        
        # Cards
        for card in [self.card_net, self.card_inc, self.card_exp]:
            card.configure(fg_color=self.colors["bg_card"], border_color=self.colors["border"])
            
        self.split_container.configure(fg_color="transparent")
        self.accounts_panel.configure(fg_color=self.colors["bg_panel"])
        self.transactions_panel.configure(fg_color=self.colors["bg_panel"])
        self.console_panel.configure(fg_color=self.colors["bg_panel"])
        
        self.update_app_state(self.app_state)
        self.refresh_dashboard()

    def async_load_llm(self):
        try:
            sys.path.append(os.getcwd())
            from function_calling import load_model
            self.llm = load_model()
            self.model_loading = False
            self.after(0, self.on_model_loaded)
        except Exception as e:
            print("Failed to load LLM model:", e)
            self.model_loading = False
            self.after(0, self.update_app_state, "ERROR", f"LLM Load Failed: {e}")

    def on_model_loaded(self):
        self.update_app_state("READY")
        self.show_toast("AI Agent model loaded successfully!", "success")
        self.refresh_dashboard()

    def create_layout(self):
        # Configure columns (Sidebar vs Main Area)
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main App
        self.grid_rowconfigure(0, weight=1)
        
        # ==========================================
        # 1. SIDEBAR FRAME (Voice Control Area)
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=self.colors["bg_sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Title Label
        logo_label = ctk.CTkLabel(self.sidebar, text="Voice", font=ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"), text_color=self.colors["accent_primary"])
        logo_label.pack(padx=20, pady=(20, 2))
        
        sub_logo_label = ctk.CTkLabel(self.sidebar, text="EXPENSE MANAGER", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["accent_secondary"])
        sub_logo_label.pack(padx=20, pady=(0, 25))
        
        # Audio Visualizer Canvas
        self.canvas_width = 240
        self.canvas_height = 200
        self.canvas = tk.Canvas(
            self.sidebar, 
            bg=self.colors["bg_sidebar"], 
            width=self.canvas_width, 
            height=self.canvas_height,
            highlightthickness=0
        )
        self.canvas.pack(padx=20, pady=10)
        
        # Draw the Interactive Mic Button Shape on Canvas
        self.btn_x = self.canvas_width // 2
        self.btn_y = self.canvas_height // 2
        self.btn_r = 38
        self.draw_vector_mic()
        
        # Sublabel: Guidance text under visualizer
        self.sublabel = ctk.CTkLabel(
            self.sidebar, 
            text="Initializing agent...", 
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color=self.colors["text_muted"],
            wraplength=220
        )
        self.sublabel.pack(padx=20, pady=10)
        
        # Divider Line
        divider = ctk.CTkFrame(self.sidebar, height=1, fg_color="#2D2D35")
        divider.pack(padx=20, pady=15, fill="x")
        
        # Dictation Settings Section
        settings_label = ctk.CTkLabel(self.sidebar, text="SETTINGS", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_muted"])
        settings_label.pack(padx=20, pady=(0, 8), anchor="w")
        
        # Dropdown: Dictation Language
        lang_label = ctk.CTkLabel(self.sidebar, text="Language", font=ctk.CTkFont(size=12), text_color=self.colors["text_muted"])
        lang_label.pack(padx=20, pady=(0, 2), anchor="w")
        self.sidebar_lang_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["English", "Spanish", "French", "German", "Hindi"],
            fg_color="#1E1E24",
            button_color="#2D2D35",
            button_hover_color="#3D3D48",
            dropdown_fg_color="#16161B"
        )
        self.sidebar_lang_menu.pack(padx=20, pady=(0, 15), fill="x")
        self.sidebar_lang_menu.set("English")
        
        # Dropdown: Visualizer Wave Type
        visualizer_label = ctk.CTkLabel(self.sidebar, text="Visualizer Animation", font=ctk.CTkFont(size=12), text_color=self.colors["text_muted"])
        visualizer_label.pack(padx=20, pady=(0, 2), anchor="w")
        self.sidebar_vis_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Siri Waves", "Concentric Pulse", "Solid Ring", "None"],
            fg_color="#1E1E24",
            button_color="#2D2D35",
            button_hover_color="#3D3D48",
            dropdown_fg_color="#16161B"
        )
        self.sidebar_vis_menu.pack(padx=20, pady=(0, 15), fill="x")
        self.sidebar_vis_menu.set("Siri Waves")
        
        # Theme Toggle
        self.theme_switch = ctk.CTkSwitch(self.sidebar, text="Dark Mode", command=self.toggle_theme, progress_color=self.colors["accent_primary"])
        self.theme_switch.pack(padx=20, pady=10, anchor="w")
        self.theme_switch.select()
        
        # Version Tag
        if sys.platform == "win32":
            backend_desc = "WinMM"
        elif HAS_SOUNDDEVICE:
            backend_desc = "SoundDevice"
        elif sys.platform.startswith("linux"):
            backend_desc = "Arecord"
        else:
            backend_desc = "Generic"
            
        version_label = ctk.CTkLabel(
            self.sidebar, 
            text=f"v2.1.0 (Audio: {backend_desc})", 
            font=ctk.CTkFont(size=11), 
            text_color="#64748B"
        )
        version_label.pack(padx=20, pady=(15, 10), fill="x", side="bottom")

        # ==========================================
        # 2. MAIN APP CONTENT (Dashboard Panel)
        # ==========================================
        self.main_content = ctk.CTkFrame(self, corner_radius=0, fg_color=self.colors["bg_app"])
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=25, pady=20)
        
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=0) # Header
        self.main_content.grid_rowconfigure(1, weight=0) # KPIs
        self.main_content.grid_rowconfigure(2, weight=1) # Split Content (Accounts & Transactions)
        self.main_content.grid_rowconfigure(3, weight=0) # Console / Feedback
        
        # Header (Status details)
        self.header_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        self.header_title = ctk.CTkLabel(
            self.header_frame, 
            text="Financial Dashboard", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        )
        self.header_title.pack(anchor="w", side="left")
        
        # Dynamic Badge: State Indicator
        self.badge_frame = ctk.CTkFrame(self.header_frame, fg_color="#1E1E24", corner_radius=15, height=30)
        self.badge_frame.pack(anchor="e", side="right", padx=10)
        self.badge_frame.pack_propagate(False)
        
        self.status_dot = ctk.CTkFrame(self.badge_frame, width=10, height=10, corner_radius=5, fg_color=self.colors["accent_error"])
        self.status_dot.pack(side="left", padx=(12, 6), pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.badge_frame, 
            text="LOADING LLM", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color=self.colors["accent_error"]
        )
        self.status_label.pack(side="left", padx=(0, 12), pady=3)
        
        # ==========================================
        # 3. KPI CARDS CONTAINER
        # ==========================================
        self.kpis_container = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.kpis_container.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        
        self.kpis_container.grid_columnconfigure(0, weight=1)
        self.kpis_container.grid_columnconfigure(1, weight=1)
        self.kpis_container.grid_columnconfigure(2, weight=1)
        
        # Card 1: Net Balance
        self.card_net = ctk.CTkFrame(self.kpis_container, fg_color=self.colors["bg_card"], border_width=1, border_color=self.colors["border"], corner_radius=12, height=90)
        self.card_net.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.card_net.grid_columnconfigure(0, weight=1)
        self.card_net.grid_rowconfigure(0, weight=1)
        
        net_title = ctk.CTkLabel(self.card_net, text="NET ASSETS", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_muted"])
        net_title.pack(padx=15, pady=(12, 2), anchor="w")
        self.kpi_net_label = ctk.CTkLabel(self.card_net, text="$0.00", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.colors["accent_primary"])
        self.kpi_net_label.pack(padx=15, pady=(0, 12), anchor="w")
        
        # Card 2: Income
        self.card_inc = ctk.CTkFrame(self.kpis_container, fg_color=self.colors["bg_card"], border_width=1, border_color=self.colors["border"], corner_radius=12, height=90)
        self.card_inc.grid(row=0, column=1, padx=5, sticky="ew")
        
        inc_title = ctk.CTkLabel(self.card_inc, text="TOTAL INCOME", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_muted"])
        inc_title.pack(padx=15, pady=(12, 2), anchor="w")
        self.kpi_inc_label = ctk.CTkLabel(self.card_inc, text="$0.00", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.colors["accent_success"])
        self.kpi_inc_label.pack(padx=15, pady=(0, 12), anchor="w")
        
        # Card 3: Expenses
        self.card_exp = ctk.CTkFrame(self.kpis_container, fg_color=self.colors["bg_card"], border_width=1, border_color=self.colors["border"], corner_radius=12, height=90)
        self.card_exp.grid(row=0, column=2, padx=(10, 0), sticky="ew")
        
        exp_title = ctk.CTkLabel(self.card_exp, text="TOTAL EXPENSE", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_muted"])
        exp_title.pack(padx=15, pady=(12, 2), anchor="w")
        self.kpi_exp_label = ctk.CTkLabel(self.card_exp, text="$0.00", font=ctk.CTkFont(size=22, weight="bold"), text_color=self.colors["accent_error"])
        self.kpi_exp_label.pack(padx=15, pady=(0, 12), anchor="w")
        
        # ==========================================
        # 4. SPLIT CONTAINER (Accounts + Transactions)
        # ==========================================
        self.split_container = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.split_container.grid(row=2, column=0, sticky="nsew", pady=(0, 15))
        
        # Accounts list panel
        self.accounts_panel = ctk.CTkFrame(self.split_container, fg_color=self.colors["bg_panel"], corner_radius=12)
        self.accounts_panel.grid_columnconfigure(0, weight=1)
        self.accounts_panel.grid_rowconfigure(0, weight=0)
        self.accounts_panel.grid_rowconfigure(1, weight=1)
        
        acc_title_lbl = ctk.CTkLabel(self.accounts_panel, text="Accounts & Balances", font=ctk.CTkFont(size=14, weight="bold"))
        acc_title_lbl.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.accounts_scroll = ctk.CTkScrollableFrame(self.accounts_panel, fg_color="transparent")
        self.accounts_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Recent Transactions Panel
        self.transactions_panel = ctk.CTkFrame(self.split_container, fg_color=self.colors["bg_panel"], corner_radius=12)
        self.transactions_panel.grid_columnconfigure(0, weight=1)
        self.transactions_panel.grid_rowconfigure(0, weight=0)
        self.transactions_panel.grid_rowconfigure(1, weight=1)
        
        tx_title_lbl = ctk.CTkLabel(self.transactions_panel, text="Recent Transactions", font=ctk.CTkFont(size=14, weight="bold"))
        tx_title_lbl.grid(row=0, column=0, padx=15, pady=10, sticky="w")
        
        self.transactions_scroll = ctk.CTkScrollableFrame(self.transactions_panel, fg_color="transparent")
        self.transactions_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # ==========================================
        # 5. CONSOLE PANEL (Command console + Feedback)
        # ==========================================
        self.console_panel = ctk.CTkFrame(self.main_content, fg_color=self.colors["bg_panel"], corner_radius=12)
        self.console_panel.grid(row=3, column=0, sticky="ew")
        self.console_panel.grid_columnconfigure(0, weight=1)
        
        # Quick Templates panel (User Friendly enhancement)
        self.templates_bar = ctk.CTkFrame(self.console_panel, fg_color="transparent")
        self.templates_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 0))
        
        tpl_lbl = ctk.CTkLabel(self.templates_bar, text="Quick Templates:", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors["text_muted"])
        tpl_lbl.pack(side="left", padx=(0, 10))
        
        templates = [
            ("☕ Coffee ($15)", "Spent $15 from Cash on Coffee"),
            ("💼 Salary ($3000)", "I received $3000 to Cash from Job"),
            ("⇄ Transfer ($500)", "Transfer $500 from Cash to Bank")
        ]
        
        for label, cmd_text in templates:
            btn = ctk.CTkButton(
                self.templates_bar,
                text=label,
                font=ctk.CTkFont(size=11),
                fg_color=self.colors["bg_card"],
                hover_color=self.colors["border"],
                border_width=1,
                border_color=self.colors["border"],
                height=25,
                width=110,
                command=lambda text=cmd_text: self.use_template(text)
            )
            btn.pack(side="left", padx=5)
        
        # Command bar
        command_bar = ctk.CTkFrame(self.console_panel, fg_color="transparent")
        command_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(8, 6))
        command_bar.grid_columnconfigure(0, weight=1)
        
        self.command_input = ctk.CTkEntry(
            command_bar,
            placeholder_text="Say or type a command... (e.g. 'Spent $20 from Cash on Coffee')",
            font=ctk.CTkFont(size=13),
            border_width=2,
            border_color="#2E2E3A",
            fg_color="#0A0A0C",
            height=40
        )
        self.command_input.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.command_input.bind("<Return>", lambda e: self.submit_command())
        
        self.submit_btn = ctk.CTkButton(
            command_bar,
            text="⚡ Submit Command",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            height=40,
            command=self.submit_command
        )
        self.submit_btn.grid(row=0, column=1, sticky="w")
        
        # Feedback details panel
        self.feedback_frame = ctk.CTkFrame(self.console_panel, fg_color="#0A0A0C", corner_radius=8, height=45)
        self.feedback_frame.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 12))
        self.feedback_frame.pack_propagate(False)
        
        self.feedback_text = ctk.CTkLabel(
            self.feedback_frame,
            text="AI Agent response status will show here.",
            font=ctk.CTkFont(family="Consolas", size=12),
            text_color="#94A3B8"
        )
        self.feedback_text.pack(side="left", padx=15)
        
        # Toast message label overlay
        self.toast_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="transparent",
            text_color="#FFFFFF",
            corner_radius=6,
            height=30
        )
        self.toast_label.place(relx=0.5, rely=0.08, anchor="center")

    # ==========================================
    # USER FRIENDLY TEMPLATE HANDLER
    # ==========================================
    def use_template(self, text):
        self.command_input.delete(0, tk.END)
        self.command_input.insert(0, text)
        self.show_toast("Template selected! Submitting...", "info")
        self.submit_command()

    # ==========================================
    # RESPONSIVE LAYOUT MANAGER (Desktop "Media Query")
    # ==========================================
    def on_window_resize(self, event):
        if event.widget == self:
            self.adjust_responsive_layout(event.width)

    def adjust_responsive_layout(self, width):
        # 950px breakpoint for layout changes
        target_mode = "mobile" if width < 950 else "desktop"
        if self.current_layout_mode == target_mode:
            return
            
        self.current_layout_mode = target_mode
        
        # Forget existing configurations to prevent layering bugs
        self.accounts_panel.grid_forget()
        self.transactions_panel.grid_forget()
        
        if target_mode == "mobile":
            # Stack panels vertically (mobile behavior)
            self.split_container.grid_columnconfigure(0, weight=1)
            self.split_container.grid_columnconfigure(1, weight=0)
            self.split_container.grid_rowconfigure(0, weight=1)
            self.split_container.grid_rowconfigure(1, weight=1)
            
            self.accounts_panel.grid(row=0, column=0, sticky="nsew", pady=(0, 10), padx=0)
            self.transactions_panel.grid(row=1, column=0, sticky="nsew", pady=(10, 0), padx=0)
        else:
            # Grid panels side-by-side (desktop behavior)
            self.split_container.grid_columnconfigure(0, weight=2)
            self.split_container.grid_columnconfigure(1, weight=3)
            self.split_container.grid_rowconfigure(0, weight=1)
            self.split_container.grid_rowconfigure(1, weight=0)
            
            self.accounts_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
            self.transactions_panel.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)

    # ==========================================
    # DATABASE DASHBOARD SYNCRONIZER
    # ==========================================
    def refresh_dashboard(self):
        conn = None
        try:
            conn = sqlite3.connect("ritul.db")
            cursor = conn.cursor()
            
            # Create accounts table & defaults if they are missing
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ACCOUNTS (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    open_balance REAL DEFAULT 0.0
                );
            """)
            
            # 1. Fetch Accounts and balances
            cursor.execute("""
                SELECT 
                    a.id,
                    a.name,
                    a.open_balance,
                    COALESCE((SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'income' AND credit_account_id = a.id), 0.0) as total_income,
                    COALESCE((SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'expense' AND debit_account_id = a.id), 0.0) as total_expense,
                    COALESCE((SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'transfer' AND debit_account_id = a.id), 0.0) as total_transfer_in,
                    COALESCE((SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'transfer' AND credit_account_id = a.id), 0.0) as total_transfer_out
                FROM ACCOUNTS a;
            """)
            accounts = cursor.fetchall()
            
            total_net = 0.0
            account_data = []
            for acc in accounts:
                id_, name, open_bal, inc, exp, t_in, t_out = acc
                balance = open_bal + inc - exp + t_in - t_out
                total_net += balance
                account_data.append((name, balance))
                
            # Fetch total income and expenses across all transactions
            cursor.execute("SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'income'")
            total_inc = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT SUM(amount) FROM TRANSACTIONS WHERE type = 'expense'")
            total_exp = cursor.fetchone()[0] or 0.0
            
            # Update KPI labels
            self.kpi_net_label.configure(text=f"${total_net:,.2f}")
            self.kpi_inc_label.configure(text=f"${total_inc:,.2f}")
            self.kpi_exp_label.configure(text=f"${total_exp:,.2f}")
            
            # Update Accounts list in GUI
            self.update_accounts_ui(account_data)
            
            # 2. Fetch recent transactions
            cursor.execute("""
                SELECT 
                    t.id,
                    t.type,
                    t.transaction_date,
                    t.amount,
                    t.narration,
                    (SELECT name FROM ACCOUNTS WHERE id = t.debit_account_id) as debit_acc,
                    (SELECT name FROM ACCOUNTS WHERE id = t.credit_account_id) as credit_acc,
                    c_inc.name as inc_cat,
                    c_exp.name as exp_cat
                FROM TRANSACTIONS t
                LEFT JOIN CATEGORY c_inc ON t.income_category_id = c_inc.id
                LEFT JOIN CATEGORY c_exp ON t.expense_category_id = c_exp.id
                ORDER BY t.id DESC
                LIMIT 10;
            """)
            transactions = cursor.fetchall()
            self.update_transactions_ui(transactions)
            
        except Exception as e:
            print("Dashboard refresh failed:", e)
        finally:
            if conn:
                conn.close()

    def update_accounts_ui(self, account_data):
        for widget in self.accounts_scroll.winfo_children():
            widget.destroy()
            
        if not account_data:
            empty_lbl = ctk.CTkLabel(self.accounts_scroll, text="No accounts found", text_color=self.colors["text_muted"])
            empty_lbl.pack(pady=10)
            return

        for name, balance in account_data:
            row_frame = ctk.CTkFrame(self.accounts_scroll, fg_color=self.colors["bg_app"], corner_radius=6, height=38)
            row_frame.pack(fill="x", pady=4, padx=5)
            row_frame.pack_propagate(False)
            
            name_lbl = ctk.CTkLabel(row_frame, text=name, font=ctk.CTkFont(size=12, weight="bold"), text_color=self.colors["text_bright"])
            name_lbl.pack(side="left", padx=10)
            
            bal_lbl = ctk.CTkLabel(row_frame, text=f"${balance:,.2f}", font=ctk.CTkFont(size=12), text_color=self.colors["accent_primary"])
            bal_lbl.pack(side="right", padx=10)

    def update_transactions_ui(self, transactions):
        for widget in self.transactions_scroll.winfo_children():
            widget.destroy()
            
        if not transactions:
            empty_lbl = ctk.CTkLabel(self.transactions_scroll, text="No transactions recorded yet", text_color=self.colors["text_muted"])
            empty_lbl.pack(pady=10)
            return

        for t in transactions:
            id_, type_, date_, amount, narration, debit_acc, credit_acc, inc_cat, exp_cat = t
            
            row_frame = ctk.CTkFrame(self.transactions_scroll, fg_color=self.colors["bg_app"], corner_radius=6, height=48)
            row_frame.pack(fill="x", pady=4, padx=5)
            row_frame.pack_propagate(False)
            
            if type_ == 'income':
                type_sym = "➕"
                color = self.colors["accent_success"]
                desc = f"Income to {credit_acc or 'Account'}"
                details = f"Category: {inc_cat or 'Income'}"
            elif type_ == 'expense':
                type_sym = "➖"
                color = self.colors["accent_error"]
                desc = f"Expense from {debit_acc or 'Account'}"
                details = f"Category: {exp_cat or 'Expense'}"
            else:
                type_sym = "⇄"
                color = self.colors["accent_secondary"]
                desc = f"Transfer: {credit_acc} → {debit_acc}"
                details = narration or "Fund Transfer"
                
            if details and len(details) > 35:
                details = details[:32] + "..."
                
            icon_lbl = ctk.CTkLabel(row_frame, text=type_sym, font=ctk.CTkFont(size=14), text_color=color)
            icon_lbl.pack(side="left", padx=(10, 5))
            
            info_col = ctk.CTkFrame(row_frame, fg_color="transparent")
            info_col.pack(side="left", fill="both", padx=5, pady=4)
            
            desc_lbl = ctk.CTkLabel(info_col, text=desc, font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
            desc_lbl.pack(anchor="w")
            
            sub_lbl = ctk.CTkLabel(info_col, text=f"{date_} | {details}", font=ctk.CTkFont(size=10), text_color=self.colors["text_muted"], anchor="w")
            sub_lbl.pack(anchor="w")
            
            amt_text = f"${amount:,.2f}"
            if type_ == 'income':
                amt_text = f"+{amt_text}"
            elif type_ == 'expense':
                amt_text = f"-{amt_text}"
                
            amt_lbl = ctk.CTkLabel(row_frame, text=amt_text, font=ctk.CTkFont(size=12, weight="bold"), text_color=color)
            amt_lbl.pack(side="right", padx=10)

    # ==========================================
    # VECTOR MICROPHONE RENDER
    # ==========================================
    def draw_vector_mic(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        
        self.canvas.delete("mic_element")
        
        # Border
        self.canvas.create_oval(
            cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
            outline="#2E2E3A", width=2, tags=("mic_element", "mic_ring_border")
        )
        
        # Mic Circle background button
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#1E1E26", outline=self.colors["accent_primary"], width=2.5,
            tags=("mic_element", "mic_button", "mic_bg")
        )
        
        # Microphone body
        self.canvas.create_line(
            cx, cy - 12, cx, cy + 8,
            width=10, fill="#FFFFFF", capstyle="round",
            tags=("mic_element", "mic_button", "mic_icon")
        )
        
        # Stand U-shape arc
        self.canvas.create_arc(
            cx - 11, cy - 5, cx + 11, cy + 14,
            start=180, extent=180, style="arc", width=3, outline="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Stand vertical neck
        self.canvas.create_line(
            cx, cy + 14, cx, cy + 22,
            width=3, fill="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Stand base
        self.canvas.create_line(
            cx - 8, cy + 22, cx + 8, cy + 22,
            width=3, fill="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Attach hover bindings & click event trigger
        self.canvas.tag_bind("mic_button", "<Button-1>", lambda e: self.on_mic_click())
        self.canvas.tag_bind("mic_button", "<Enter>", lambda e: self.on_mic_enter())
        self.canvas.tag_bind("mic_button", "<Leave>", lambda e: self.on_mic_leave())

    def on_mic_enter(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            accent = self.colors["accent_primary"]
            self.canvas.itemconfig("mic_bg", fill="#2C2C3C", outline=accent)
            
            # Interactive glow halo
            self.canvas.create_oval(
                cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                outline=accent, width=1, tags="hover_glow"
            )
            self.canvas.tag_lower("hover_glow", "mic_button")

    def on_mic_leave(self):
        self.canvas.delete("hover_glow")
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            self.canvas.itemconfig("mic_bg", fill="#1E1E26", outline=self.colors["accent_primary"])

    def on_mic_click(self):
        if self.model_loading:
            self.show_toast("AI model loading. Please wait...", "warning")
            return
            
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            self.update_app_state("LISTENING")
            self.start_dictation_recording()
        elif self.app_state == "LISTENING":
            self.recording_active = False

    # ==========================================
    # APP STATE MANAGER
    # ==========================================
    def update_app_state(self, new_state, error_detail=None):
        self.app_state = new_state
        
        # Match styles to state
        if new_state == "LOADING_MODEL":
            self.status_dot.configure(fg_color=self.colors["accent_error"])
            self.status_label.configure(text="LOADING MODEL", text_color=self.colors["accent_error"])
            self.sublabel.configure(text="Initialising Llama model in background. Please wait...", text_color=self.colors["text_muted"])
            self.target_amplitude = 12.0
            self.canvas.itemconfig("mic_bg", fill="#121216", outline=self.colors["text_muted"])
            
        elif new_state == "READY":
            self.status_dot.configure(fg_color=self.colors["accent_primary"])
            self.status_label.configure(text="READY", text_color=self.colors["accent_primary"])
            self.sublabel.configure(text="Click microphone and speak transaction command", text_color=self.colors["text_muted"])
            self.target_amplitude = 8.0
            self.canvas.itemconfig("mic_bg", fill="#1E1E26", outline=self.colors["accent_primary"])
            
        elif new_state == "LISTENING":
            self.status_dot.configure(fg_color=self.colors["accent_error"])
            self.status_label.configure(text="RECORDING", text_color=self.colors["accent_error"])
            self.sublabel.configure(text="Listening... Click Mic button again when finished speaking.", text_color=self.colors["accent_error"])
            self.target_amplitude = 48.0
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_error"], outline=self.colors["accent_error"])
            
        elif new_state == "PROCESSING":
            self.status_dot.configure(fg_color=self.colors["accent_secondary"])
            self.status_label.configure(text="PROCESSING", text_color=self.colors["accent_secondary"])
            self.sublabel.configure(text="Running transaction with AI agent...", text_color=self.colors["accent_secondary"])
            self.target_amplitude = 18.0
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_secondary"], outline=self.colors["accent_secondary"])
            
        elif new_state == "SUCCESS":
            self.status_dot.configure(fg_color=self.colors["accent_success"])
            self.status_label.configure(text="SUCCESS", text_color=self.colors["accent_success"])
            self.sublabel.configure(text="Transaction successful!", text_color=self.colors["accent_success"])
            self.target_amplitude = 6.0
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_success"], outline=self.colors["accent_success"])
            self.after(2000, lambda: self.update_app_state("READY") if self.app_state == "SUCCESS" else None)
            
        elif new_state == "ERROR":
            err_msg = error_detail if error_detail else "Operation failed"
            self.status_dot.configure(fg_color=self.colors["accent_error"])
            self.status_label.configure(text="ERROR", text_color=self.colors["accent_error"])
            self.sublabel.configure(text=err_msg, text_color=self.colors["accent_error"])
            self.target_amplitude = 0.0
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_error"], outline=self.colors["accent_error"])
            self.after(3500, lambda: self.update_app_state("READY") if self.app_state == "ERROR" else None)

    # ==========================================
    # SPEECH ENGINE - NATIVE RECORDER THREADS
    # ==========================================
    def start_dictation_recording(self):
        self.recording_active = True
        threading.Thread(target=self.dictation_record_worker, daemon=True).start()

    def dictation_record_worker(self):
        temp_wav = os.path.join(os.getcwd(), "aura_speech_temp.wav")
        if os.path.exists(temp_wav):
            try:
                os.remove(temp_wav)
            except Exception:
                pass

        backend = None
        if sys.platform == "win32":
            backend = "winmm"
        elif HAS_SOUNDDEVICE:
            backend = "sounddevice"
        elif sys.platform.startswith("linux"):
            backend = "arecord"
        else:
            backend = "none"

        print(f"Starting dictation recording using backend: {backend}")
        start_time = time.time()
        max_duration = 60.0
        
        if backend == "winmm":
            try:
                winmm = ctypes.windll.winmm
                winmm.mciSendStringW("close recsound", None, 0, 0)
                winmm.mciSendStringW("open new type waveaudio alias recsound", None, 0, 0)
                winmm.mciSendStringW("set recsound time format ms", None, 0, 0)
                winmm.mciSendStringW("set recsound alignment 2 bitspersample 16 samplespersec 16000 channels 1 bytespersec 32000", None, 0, 0)
                winmm.mciSendStringW("record recsound", None, 0, 0)
                
                while self.recording_active:
                    elapsed = time.time() - start_time
                    if elapsed >= max_duration:
                        break
                    remaining = int(max_duration - elapsed)
                    self.after(0, self.update_recording_sublabel, remaining)
                    time.sleep(0.1)
                
                winmm.mciSendStringW("stop recsound", None, 0, 0)
                winmm.mciSendStringW(f'save recsound "{temp_wav}"', None, 0, 0)
                winmm.mciSendStringW("close recsound", None, 0, 0)
            except Exception as e:
                print("winmm recording failed, trying sounddevice if available:", e)
                if HAS_SOUNDDEVICE:
                    backend = "sounddevice"
                else:
                    self.after(0, self.on_transcription_complete, "", f"Recording failed on Windows: {e}")
                    return

        if backend == "sounddevice":
            try:
                fs = 16000
                myrecording = sd.rec(int(max_duration * fs), samplerate=fs, channels=1, dtype='int16')
                
                while self.recording_active:
                    elapsed = time.time() - start_time
                    if elapsed >= max_duration:
                        break
                    remaining = int(max_duration - elapsed)
                    self.after(0, self.update_recording_sublabel, remaining)
                    time.sleep(0.1)
                
                sd.stop()
                elapsed = time.time() - start_time
                actual_samples = int(elapsed * fs)
                sliced_recording = myrecording[:actual_samples]
                
                import wave
                with wave.open(temp_wav, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(fs)
                    wf.writeframes(sliced_recording.tobytes())
            except Exception as e:
                print("sounddevice recording failed:", e)
                self.after(0, self.on_transcription_complete, "", f"Recording failed: {e}")
                return

        elif backend == "arecord":
            import subprocess
            try:
                cmd = ["arecord", "-f", "S16_LE", "-c", "1", "-r", "16000", temp_wav]
                process = subprocess.Popen(cmd)
                
                while self.recording_active:
                    elapsed = time.time() - start_time
                    if elapsed >= max_duration:
                        break
                    remaining = int(max_duration - elapsed)
                    self.after(0, self.update_recording_sublabel, remaining)
                    time.sleep(0.1)
                
                process.terminate()
                process.wait()
            except Exception as e:
                print("arecord failed:", e)
                self.after(0, self.on_transcription_complete, "", f"Recording failed: arecord not available or failed: {e}")
                return

        elif backend == "none":
            self.after(0, self.on_transcription_complete, "", "No recording backend available. Please install sounddevice: pip install sounddevice")
            return

        # Hand off WAV file path to translation worker
        threading.Thread(target=self.dictation_transcribe_worker, args=(temp_wav,), daemon=True).start()

    def update_recording_sublabel(self, seconds_left):
        if self.app_state == "LISTENING":
            self.sublabel.configure(
                text=f"Recording... {seconds_left}s remaining. Click Mic circle again to finish.",
                text_color=self.colors["accent_error"]
            )

    def dictation_transcribe_worker(self, filepath):
        self.after(0, self.update_app_state, "PROCESSING")
        
        recognizer = sr.Recognizer()
        transcribed_text = ""
        error_info = None
        
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            try:
                with sr.AudioFile(filepath) as source:
                    audio = recognizer.record(source)
                
                lang_selection = self.sidebar_lang_menu.get()
                lang_codes = {
                    "English": "en-US",
                    "Spanish": "es-ES",
                    "French": "fr-FR",
                    "German": "de-DE",
                    "Hindi": "hi-IN"
                }
                api_lang = lang_codes.get(lang_selection, "en-US")
                
                transcribed_text = recognizer.recognize_google(audio, language=api_lang)
                
            except sr.UnknownValueError:
                error_info = "Could not understand speech"
            except sr.RequestError as e:
                error_info = f"Speech API request failed: {e}"
            except Exception as e:
                error_info = f"Transcription failed: {e}"
            finally:
                try:
                    os.remove(filepath)
                except Exception:
                    pass
        else:
            error_info = "No audio recorded."
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                    
        self.after(0, self.on_transcription_complete, transcribed_text, error_info)

    def on_transcription_complete(self, text, error_info):
        if error_info:
            self.update_app_state("ERROR", error_info)
            self.show_toast(error_info, "danger")
        else:
            self.command_input.delete(0, tk.END)
            self.command_input.insert(0, text)
            self.show_toast("Speech transcribed! Submitting...", "info")
            # Automatically execute the transcribed query
            self.submit_command()

    # ==========================================
    # LLM AGENT INTEGRATION PIPELINE
    # ==========================================
    def submit_command(self):
        prompt = self.command_input.get().strip()
        if not prompt:
            self.show_toast("Please enter or dictate a command!", "warning")
            return
            
        from function_calling import check_amount_in_prompt, check_bank_in_prompt
        
        # Check if amount is mentioned
        if not check_amount_in_prompt(prompt):
            self.on_command_success("Amount not mentioned.", False)
            return
            
        # Check if bank/account is mentioned
        if not check_bank_in_prompt(prompt):
            self.on_command_success("No bank account mentioned. Please add bank accounts.", False)
            return
            
        if self.model_loading or not self.llm:
            self.show_toast("AI Agent is loading. Please wait...", "warning")
            return

        self.update_app_state("PROCESSING")
        self.feedback_text.configure(text="AI Agent is reasoning...", text_color="#E2E8F0")
        
        # Execute prompt in a background thread to prevent UI freezing
        threading.Thread(target=self.run_llm_transaction_worker, args=(prompt,), daemon=True).start()

    def run_llm_transaction_worker(self, prompt):
        try:
            sys.path.append(os.getcwd())
            from function_calling import run_tool_calls, parse_function_calls, execute_calls, generate_final_answer
            
            messages = [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # This calls the database modifiers internally via tool calls
            response = run_tool_calls(self.llm, messages)
            
            content = response["choices"][0]["message"]["content"]
            calls = parse_function_calls(content)
            results = execute_calls(calls)
            
            final_answer = generate_final_answer(
                self.llm,
                messages,
                content,
                results
            )
            
            print("AI Final Output:", final_answer)
            
            # Check if any transactions were run and if they succeeded
            success = False
            if results:
                success = any(res.get("result", {}).get("status") == "success" for res in results)
                feedback = "\n".join([res.get("result", {}).get("message", "") for res in results])
            else:
                feedback = final_answer
                
            self.after(0, self.on_command_success, feedback, success)
            
        except Exception as e:
            print("Command run failed:", e)
            self.after(0, self.on_command_error, str(e))

    def on_command_success(self, feedback, success):
        if success:
            self.update_app_state("SUCCESS")
            self.feedback_text.configure(text=feedback, text_color=self.colors["accent_success"])
            self.show_toast("Transaction successful!", "success")
        else:
            self.update_app_state("READY")
            if "validation error" in feedback.lower() or "not mentioned" in feedback.lower():
                self.feedback_text.configure(text=feedback, text_color=self.colors["accent_error"])
                self.show_toast("Validation failed", "warning")
            else:
                self.feedback_text.configure(text=feedback, text_color=self.colors["text_bright"])
                self.show_toast("Query processed", "info")
            
        self.command_input.delete(0, tk.END)
        self.refresh_dashboard()
        
        # Speak back the results
        if feedback:
            self.speak_feedback(feedback)

    def on_command_error(self, err_details):
        self.update_app_state("ERROR", err_details)
        self.feedback_text.configure(text=f"Error: {err_details}", text_color=self.colors["accent_error"])
        self.show_toast("Command failed", "danger")
        self.speak_feedback("Sorry, I could not complete your request due to an error.")

    def speak_feedback(self, text):
        if self.tts_speaking:
            self.stop_tts()
        self.tts_speaking = True
        threading.Thread(target=self.tts_voice_worker, args=(text,), daemon=True).start()

    def tts_voice_worker(self, text):
        try:
            self.tts_engine = pyttsx3.init()
            self.tts_engine.setProperty('rate', 165)
            
            voices = self.tts_engine.getProperty('voices')
            lang_selection = self.sidebar_lang_menu.get()
            
            matched_voice = None
            for voice in voices:
                name = getattr(voice, 'name', '')
                if not isinstance(name, str):
                    name = ''
                if lang_selection.lower() in name.lower():
                    matched_voice = voice.id
                    break
                
                voice_langs = []
                for l in getattr(voice, 'languages', []):
                    if isinstance(l, bytes):
                        voice_langs.append(l.decode('utf-8', errors='ignore').lower())
                    elif isinstance(l, str):
                        voice_langs.append(l.lower())
                
                lang_lower = lang_selection.lower()
                if any(lang_lower in vl for vl in voice_langs):
                    matched_voice = voice.id
                    break
            
            if matched_voice:
                self.tts_engine.setProperty('voice', matched_voice)
                
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print("TTS error:", e)
        finally:
            self.tts_speaking = False

    def stop_tts(self):
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception:
                pass
        self.tts_speaking = False

    # ==========================================
    # CANVAS VISUALIZATION LOOP
    # ==========================================
    def run_visualizer_loop(self):
        def loop():
            if not self.animation_running:
                return
            self.update_visuals()
            self.after(16, loop)
        loop()

    def update_visuals(self):
        cx, cy = self.btn_x, self.btn_y
        
        # Smoothly interpolate amplitude
        self.current_amplitude += (self.target_amplitude - self.current_amplitude) * 0.12
        
        if self.app_state == "LISTENING":
            self.phase += 0.16
            self.target_amplitude = random.uniform(30.0, 55.0)
        elif self.app_state == "PROCESSING" or self.app_state == "LOADING_MODEL":
            self.phase += 0.28
            self.target_amplitude = 18.0
        else:
            self.phase += 0.04
            if self.app_state in ["READY", "SUCCESS", "ERROR"]:
                self.target_amplitude = 8.0 if self.app_state == "READY" else (6.0 if self.app_state == "SUCCESS" else 0.0)
                
        self.canvas.delete("animation_wave")
        
        style = self.sidebar_vis_menu.get()
        if style == "None":
            return
            
        if style == "Siri Waves":
            self.draw_siri_waves()
        elif style == "Concentric Pulse":
            self.draw_concentric_pulses()
        elif style == "Solid Ring":
            self.draw_solid_glow_ring()

    def draw_siri_waves(self):
        w = self.canvas_width
        cy = self.btn_y
        amp = self.current_amplitude
        
        # Primary Cyan Wave
        points1 = []
        for x in range(0, w + 10, 10):
            envelope = math.sin(math.pi * x / w) if 0 <= x <= w else 0
            y = cy + math.sin(x * 0.035 - self.phase) * amp * envelope
            points1.extend([x, y])
        self.canvas.create_line(
            points1, smooth=True, fill=self.colors["accent_primary"], width=3,
            tags="animation_wave"
        )
        
        # Secondary Purple Wave
        points2 = []
        for x in range(0, w + 10, 10):
            envelope = math.sin(math.pi * x / w)
            y = cy + math.sin(x * 0.052 + self.phase * 1.3 + 1.2) * (amp * 0.6) * envelope
            points2.extend([x, y])
        self.canvas.create_line(
            points2, smooth=True, fill=self.colors["accent_secondary"], width=2.2,
            tags="animation_wave"
        )
        
        self.canvas.tag_lower("animation_wave", "mic_button")

    def draw_concentric_pulses(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        
        if self.app_state in ["LISTENING", "PROCESSING", "LOADING_MODEL"]:
            self.ripple_radius += 1.8
            if self.ripple_radius > 100.0:
                self.ripple_radius = float(r)
            
            fade_range = 100.0 - r
            current_diff = self.ripple_radius - r
            alpha = max(0.0, min(1.0, 1.0 - (current_diff / fade_range)))
            
            glow_color = self.colors["accent_secondary"] if self.app_state != "LISTENING" else self.colors["accent_error"]
            glow_col = self.fade_color(glow_color, self.colors["bg_sidebar"], alpha)
            
            self.canvas.create_oval(
                cx - self.ripple_radius, cy - self.ripple_radius,
                cx + self.ripple_radius, cy + self.ripple_radius,
                outline=glow_col, width=2.5, tags="animation_wave"
            )
        else:
            # Steady breathe glow ring
            breath_amp = math.sin(self.phase * 1.5) * 6.0
            radius = r + 10 + breath_amp
            self.canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                outline=self.colors["accent_primary"], width=1, tags="animation_wave"
            )
            
        self.canvas.tag_lower("animation_wave", "mic_button")

    def draw_solid_glow_ring(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        outline_thickness = 1.0 + (self.current_amplitude / 12.0)
        
        color = self.colors["accent_primary"]
        if self.app_state == "LISTENING":
            color = self.colors["accent_error"]
        elif self.app_state == "PROCESSING" or self.app_state == "LOADING_MODEL":
            color = self.colors["accent_secondary"]
        elif self.app_state == "SUCCESS":
            color = self.colors["accent_success"]
            
        self.canvas.create_oval(
            cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
            outline=color, width=outline_thickness, tags="animation_wave"
        )
        self.canvas.tag_lower("animation_wave", "mic_button")

    def fade_color(self, hex_from, hex_to, alpha):
        alpha = max(0.0, min(1.0, alpha))
        r1, g1, b1 = int(hex_from[1:3], 16), int(hex_from[3:5], 16), int(hex_from[5:7], 16)
        r2, g2, b2 = int(hex_to[1:3], 16), int(hex_to[3:5], 16), int(hex_to[5:7], 16)
        r = int(r1 * alpha + r2 * (1 - alpha))
        g = int(g1 * alpha + g2 * (1 - alpha))
        b = int(b1 * alpha + b2 * (1 - alpha))
        return f"#{r:02x}{g:02x}{b:02x}"

    # ==========================================
    # TOAST MANAGER
    # ==========================================
    def show_toast(self, text, style="success"):
        colors_map = {
            "success": ("#10B981", "#FFFFFF"),
            "warning": ("#F59E0B", "#0F172A"),
            "danger": ("#EF4444", "#FFFFFF"),
            "info": ("#3B82F6", "#FFFFFF")
        }
        bg, fg = colors_map.get(style, ("#10B981", "#FFFFFF"))
        
        self.toast_label.configure(
            text=text, 
            fg_color=bg, 
            text_color=fg
        )
        
        if hasattr(self, "_toast_clear_job") and self._toast_clear_job:
            self.after_cancel(self._toast_clear_job)
            
        self._toast_clear_job = self.after(2500, self.clear_toast)

    def clear_toast(self):
        self.toast_label.configure(text="", fg_color="transparent")
        self._toast_clear_job = None

    def copy_to_clipboard(self):
        text = self.command_input.get().strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.show_toast("Copied to clipboard!", "success")
        else:
            self.show_toast("Nothing to copy!", "warning")

    # ==========================================
    # SHUTDOWN / EXIT
    # ==========================================
    def on_close(self):
        self.animation_running = False
        self.recording_active = False
        self.stop_tts()
        self.destroy()

if __name__ == "__main__":
    app = AuraVoiceApp()
    app.mainloop()
