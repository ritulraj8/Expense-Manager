import os
import sys
import time
import math
import random
import ctypes
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import speech_recognition as sr
import pyttsx3

# Set default customtkinter theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AuraVoiceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Expense manager")
        self.geometry("950x680")
        self.minsize(900, 620)
        
        # Center window on load
        self.center_window()
        
        # App State variables
        self.app_state = "READY" # READY, LISTENING, PROCESSING, SUCCESS, ERROR
        self.recording_active = False
        self.tts_speaking = False
        self.tts_engine = None
        
        # Waveform animation settings
        self.phase = 0.0
        self.target_amplitude = 8.0
        self.current_amplitude = 8.0
        self.ripple_radius = 45.0
        self.animation_running = True
        
        # Theme / Color definitions
        self.setup_colors()
        
        # Setup UI layout
        self.create_layout()
        
        # Start the canvas visualizer loop
        self.run_visualizer_loop()
        
        # Bind keyboard shortcuts & close event
        self.bind("<Control-c>", lambda e: self.copy_to_clipboard())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def center_window(self):
        self.update_idletasks()
        w = 950
        h = 680
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def setup_colors(self):
        # Premium color palette tokens
        # Dark Theme
        self.colors_dark = {
            "bg_app": "#0E0E11",
            "bg_sidebar": "#16161B",
            "bg_panel": "#1B1B22",
            "accent_primary": "#00E5FF",  # Cyan
            "accent_secondary": "#7B2CBF",  # Neon Purple
            "accent_tertiary": "#45A29E",   # Teal
            "accent_success": "#00E676",    # Green
            "accent_error": "#FF2A6D",      # Pinkish-Red
            "text_bright": "#FFFFFF",
            "text_muted": "#94A3B8"
        }
        
        # Light Theme
        self.colors_light = {
            "bg_app": "#F8FAFC",
            "bg_sidebar": "#FFFFFF",
            "bg_panel": "#F1F5F9",
            "accent_primary": "#0284C7",   # Sky Blue
            "accent_secondary": "#8B5CF6", # Violet
            "accent_tertiary": "#0D9488",  # Emerald
            "accent_success": "#16A34A",   # Green
            "accent_error": "#DC2626",     # Crimson
            "text_bright": "#0F172A",
            "text_muted": "#64748B"
        }
        
        # Current active palette
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
        self.update_app_state(self.app_state) # Refresh colors of elements

    def create_layout(self):
        # Configure columns (Sidebar vs Main Area)
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main App
        self.grid_rowconfigure(0, weight=1)
        
        # ==========================================
        # 1. SIDEBAR FRAME
        # ==========================================
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=self.colors_dark["bg_sidebar"] if ctk.get_appearance_mode() == "dark" else self.colors_light["bg_sidebar"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Logo Label
        logo_label = ctk.CTkLabel(self.sidebar, text="Expense Manager", font=ctk.CTkFont(family="Helvetica Neue", size=24, weight="bold"), text_color=self.colors_dark["accent_primary"])
        logo_label.pack(padx=20, pady=(25, 5))
        
        version_label = ctk.CTkLabel(self.sidebar, text="v1.0.0 (Native WinMM)", font=ctk.CTkFont(size=11), text_color="#64748B")
        version_label.pack(padx=20, pady=(0, 30))
        
        # Section Header
        settings_label = ctk.CTkLabel(self.sidebar, text="DICTATION SETTINGS", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors_dark["text_muted"])
        settings_label.pack(padx=20, pady=(15, 10), anchor="w")
        
        # Dropdown: Dictation Language
        lang_label = ctk.CTkLabel(self.sidebar, text="Language", font=ctk.CTkFont(size=12), text_color=self.colors_dark["text_muted"])
        lang_label.pack(padx=20, pady=(0, 2), anchor="w")
        self.sidebar_lang_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["English", "Spanish", "French", "German", "Hindi"],
            fg_color="#1E1E24",
            button_color="#2D2D35",
            button_hover_color="#3D3D48",
            dropdown_fg_color="#16161B"
        )
        self.sidebar_lang_menu.pack(padx=20, pady=(0, 20), fill="x")
        self.sidebar_lang_menu.set("English")
        
        # Dropdown: Visualizer Wave Type
        visualizer_label = ctk.CTkLabel(self.sidebar, text="Wave Animation", font=ctk.CTkFont(size=12), text_color=self.colors_dark["text_muted"])
        visualizer_label.pack(padx=20, pady=(0, 2), anchor="w")
        self.sidebar_vis_menu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Siri Waves", "Concentric Pulse", "Solid Ring", "None"],
            fg_color="#1E1E24",
            button_color="#2D2D35",
            button_hover_color="#3D3D48",
            dropdown_fg_color="#16161B"
        )
        self.sidebar_vis_menu.pack(padx=20, pady=(0, 20), fill="x")
        self.sidebar_vis_menu.set("Siri Waves")
        
        # Divider Line
        divider = ctk.CTkFrame(self.sidebar, height=1, fg_color="#2D2D35")
        divider.pack(padx=20, pady=10, fill="x")
        
        # Appearance Controls
        theme_label = ctk.CTkLabel(self.sidebar, text="APPEARANCE", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.colors_dark["text_muted"])
        theme_label.pack(padx=20, pady=(15, 10), anchor="w")
        
        self.theme_switch = ctk.CTkSwitch(self.sidebar, text="Dark Mode", command=self.toggle_theme, progress_color=self.colors_dark["accent_primary"])
        self.theme_switch.pack(padx=20, pady=5, anchor="w")
        self.theme_switch.select() # Start on dark mode
        
        # Explanatory card container
        info_frame = ctk.CTkFrame(self.sidebar, fg_color="#1B1B22", corner_radius=8)
        info_frame.pack(padx=20, pady=(30, 20), fill="x", side="bottom")
        
        info_title = ctk.CTkLabel(info_frame, text="Quick Guide", font=ctk.CTkFont(size=13, weight="bold"), text_color=self.colors_dark["accent_primary"])
        info_title.pack(padx=10, pady=(10, 2), anchor="w")
        
        info_desc = ctk.CTkLabel(
            info_frame, 
            text="1. Choose language.\n2. Click Mic circle.\n3. Speak clear sentences.\n4. Click Mic again to stop and translate.\n5. Click Speak button below textbox to read back.",
            font=ctk.CTkFont(size=11),
            text_color="#94A3B8",
            justify="left"
        )
        info_desc.pack(padx=10, pady=(0, 10), anchor="w")
        
        # ==========================================
        # 2. MAIN APP CONTENT
        # ==========================================
        self.main_content = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content.grid(row=0, column=1, sticky="nsew", padx=25, pady=20)
        
        self.main_content.grid_columnconfigure(0, weight=1)
        self.main_content.grid_rowconfigure(0, weight=0) # Header
        self.main_content.grid_rowconfigure(1, weight=1) # Visualizer Canvas & Mic
        self.main_content.grid_rowconfigure(2, weight=1) # Textbox & utility bar
        
        # Header (Aura voice status details)
        self.header_frame = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", pady=(5, 10))
        
        self.header_title = ctk.CTkLabel(
            self.header_frame, 
            text="Voice Dictation Center", 
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold")
        )
        self.header_title.pack(anchor="w", side="left")
        
        # Dynamic Badge: State Indicator
        self.badge_frame = ctk.CTkFrame(self.header_frame, fg_color="#1E1E24", corner_radius=15, height=30)
        self.badge_frame.pack(anchor="e", side="right", padx=10)
        self.badge_frame.pack_propagate(False)
        
        self.status_dot = ctk.CTkFrame(self.badge_frame, width=10, height=10, corner_radius=5, fg_color=self.colors["accent_primary"])
        self.status_dot.pack(side="left", padx=(12, 6), pady=10)
        
        self.status_label = ctk.CTkLabel(
            self.badge_frame, 
            text="READY", 
            font=ctk.CTkFont(size=12, weight="bold"), 
            text_color=self.colors["accent_primary"]
        )
        self.status_label.pack(side="left", padx=(0, 12), pady=3)
        
        # ------------------------------------------
        # Visualizer & Mic Frame
        # ------------------------------------------
        # This holds the Canvas where animations and the Mic Button are housed
        self.visualizer_frame = ctk.CTkFrame(self.main_content, fg_color=self.colors["bg_panel"], corner_radius=12)
        self.visualizer_frame.grid(row=1, column=0, sticky="nsew", pady=15)
        self.visualizer_frame.grid_rowconfigure(0, weight=1)
        self.visualizer_frame.grid_columnconfigure(0, weight=1)
        
        # Setup Canvas
        self.canvas_width = 640
        self.canvas_height = 240
        self.canvas = tk.Canvas(
            self.visualizer_frame, 
            bg=self.colors["bg_app"], 
            width=self.canvas_width, 
            height=self.canvas_height,
            highlightthickness=0
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Sublabel: Guidance text under visualizer
        self.sublabel = ctk.CTkLabel(
            self.visualizer_frame, 
            text="Click microphone to start dictation", 
            font=ctk.CTkFont(size=14, weight="normal"),
            text_color=self.colors["text_muted"]
        )
        self.sublabel.grid(row=1, column=0, pady=(0, 15))
        
        # Draw the Interactive Mic Button Shape on Canvas
        self.btn_x = self.canvas_width // 2
        self.btn_y = self.canvas_height // 2
        self.btn_r = 42
        self.draw_vector_mic()
        
        # ------------------------------------------
        # Text Dictation Area & Toolbar Frame
        # ------------------------------------------
        self.textbox_panel = ctk.CTkFrame(self.main_content, fg_color="transparent")
        self.textbox_panel.grid(row=2, column=0, sticky="nsew", pady=(10, 5))
        self.textbox_panel.grid_columnconfigure(0, weight=1)
        self.textbox_panel.grid_rowconfigure(0, weight=1) # Text area
        self.textbox_panel.grid_rowconfigure(1, weight=0) # Controls
        
        # Elegant customized text area
        self.textbox = ctk.CTkTextbox(
            self.textbox_panel, 
            font=ctk.CTkFont(family="Consolas", size=14),
            border_width=2,
            border_color="#2D2D35",
            fg_color="#1B1B22"
        )
        self.textbox.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.textbox.bind("<KeyRelease>", lambda e: self.update_counters())
        
        # Toast message label overlay
        self.toast_label = ctk.CTkLabel(
            self.textbox_panel,
            text="",
            font=ctk.CTkFont(size=13, weight="normal"),
            fg_color="transparent",
            text_color="#FFFFFF",
            corner_radius=6,
            height=30
        )
        # We can place it floating on top of the textbox using place
        self.toast_label.place(relx=0.5, rely=0.08, anchor="center")
        
        # Utility bar frame containing copy, tts, clear, save, count
        self.toolbar = ctk.CTkFrame(self.textbox_panel, fg_color="transparent")
        self.toolbar.grid(row=1, column=0, sticky="ew")
        
        # Left side controls
        self.speak_btn = ctk.CTkButton(
            self.toolbar, 
            text="🔊 Speak Text", 
            width=110,
            fg_color="#2563EB", 
            hover_color="#1D4ED8",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.speak_text
        )
        self.speak_btn.pack(side="left", padx=(0, 8))
        
        self.copy_btn = ctk.CTkButton(
            self.toolbar, 
            text="📋 Copy", 
            width=80,
            fg_color="#1E293B", 
            hover_color="#334155",
            font=ctk.CTkFont(size=12),
            command=self.copy_to_clipboard
        )
        self.copy_btn.pack(side="left", padx=8)
        
        self.save_btn = ctk.CTkButton(
            self.toolbar, 
            text="💾 Save", 
            width=80,
            fg_color="#1E293B", 
            hover_color="#334155",
            font=ctk.CTkFont(size=12),
            command=self.save_to_file
        )
        self.save_btn.pack(side="left", padx=8)
        
        self.clear_btn = ctk.CTkButton(
            self.toolbar, 
            text="🗑 Clear", 
            width=80,
            fg_color="#450A0A", 
            hover_color="#7F1D1D",
            text_color="#FCA5A5",
            font=ctk.CTkFont(size=12),
            command=self.clear_text
        )
        self.clear_btn.pack(side="left", padx=8)
        
        # Right side: character counter
        self.counter_label = ctk.CTkLabel(
            self.toolbar, 
            text="Words: 0 | Chars: 0", 
            font=ctk.CTkFont(size=12, weight="normal"),
            text_color=self.colors["text_muted"]
        )
        self.counter_label.pack(side="right", padx=(10, 5))

    # ==========================================
    # VECTOR MICROPHONE RENDER
    # ==========================================
    def draw_vector_mic(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        
        # Remove any previous microphone items
        self.canvas.delete("mic_element")
        
        # 1. Hover glow element placeholder (initially invisible/deleted)
        # 2. Mic Circle border
        self.canvas.create_oval(
            cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4,
            outline="#1F2937", width=2, tags=("mic_element", "mic_ring_border")
        )
        
        # 3. Mic Circle background button
        self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            fill="#1E1E24", outline=self.colors["accent_primary"], width=2.5,
            tags=("mic_element", "mic_button", "mic_bg")
        )
        
        # 4. Microphone vector parts (center body)
        # rounded rectangle (drawn using a thick line with round cap)
        self.canvas.create_line(
            cx, cy - 14, cx, cy + 10,
            width=12, fill="#FFFFFF", capstyle="round",
            tags=("mic_element", "mic_button", "mic_icon")
        )
        
        # Stand U-shape arc
        self.canvas.create_arc(
            cx - 13, cy - 6, cx + 13, cy + 17,
            start=180, extent=180, style="arc", width=3.5, outline="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Stand vertical neck
        self.canvas.create_line(
            cx, cy + 17, cx, cy + 26,
            width=3.5, fill="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Stand base horizontal bar
        self.canvas.create_line(
            cx - 9, cy + 26, cx + 9, cy + 26,
            width=3.5, fill="#FFFFFF",
            tags=("mic_element", "mic_button", "mic_stand")
        )
        
        # Attach hover bindings & click event trigger
        self.canvas.tag_bind("mic_button", "<Button-1>", lambda e: self.on_mic_click())
        self.canvas.tag_bind("mic_button", "<Enter>", lambda e: self.on_mic_enter())
        self.canvas.tag_bind("mic_button", "<Leave>", lambda e: self.on_mic_leave())

    # ==========================================
    # MIC HOVER & CLICK HANDLERS
    # ==========================================
    def on_mic_enter(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            accent = self.colors["accent_primary"]
            self.canvas.itemconfig("mic_bg", fill="#2C2C38", outline=accent)
            
            # Draw interactive glow halo under the mic
            self.canvas.create_oval(
                cx - r - 9, cy - r - 9, cx + r + 9, cy + r + 9,
                outline=accent, width=1, tags="hover_glow"
            )
            self.canvas.tag_lower("hover_glow", "mic_button")

    def on_mic_leave(self):
        self.canvas.delete("hover_glow")
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            self.canvas.itemconfig("mic_bg", fill="#1E1E24", outline=self.colors["accent_primary"])

    def on_mic_click(self):
        if self.app_state in ["READY", "SUCCESS", "ERROR"]:
            self.update_app_state("LISTENING")
            self.start_dictation_recording()
        elif self.app_state == "LISTENING":
            self.recording_active = False # Signal worker thread to stop recording and process

    # ==========================================
    # STATE MANAGER
    # ==========================================
    def update_app_state(self, new_state, error_detail=None):
        self.app_state = new_state
        
        accent_color = self.colors["accent_primary"]
        text_color = self.colors["text_muted"]
        
        # Match styles to state
        if new_state == "READY":
            self.status_dot.configure(fg_color=self.colors["accent_primary"])
            self.status_label.configure(text="READY", text_color=self.colors["accent_primary"])
            self.sublabel.configure(text="Click microphone to start dictation", text_color=self.colors["text_muted"])
            self.target_amplitude = 8.0
            
            self.canvas.itemconfig("mic_bg", fill="#1E1E24", outline=self.colors["accent_primary"])
            
        elif new_state == "LISTENING":
            self.status_dot.configure(fg_color=self.colors["accent_error"])
            self.status_label.configure(text="RECORDING", text_color=self.colors["accent_error"])
            self.sublabel.configure(text="Recording... Speak clearly. Click Mic circle again to finish.", text_color=self.colors["accent_error"])
            self.target_amplitude = 48.0
            
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_error"], outline=self.colors["accent_error"])
            
        elif new_state == "PROCESSING":
            self.status_dot.configure(fg_color=self.colors["accent_secondary"])
            self.status_label.configure(text="TRANSCRIBING", text_color=self.colors["accent_secondary"])
            self.sublabel.configure(text="Processing transcription...", text_color=self.colors["accent_secondary"])
            self.target_amplitude = 18.0
            
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_secondary"], outline=self.colors["accent_secondary"])
            
        elif new_state == "SUCCESS":
            self.status_dot.configure(fg_color=self.colors["accent_success"])
            self.status_label.configure(text="SUCCESS", text_color=self.colors["accent_success"])
            self.sublabel.configure(text="Transcribed successfully!", text_color=self.colors["accent_success"])
            self.target_amplitude = 6.0
            
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_success"], outline=self.colors["accent_success"])
            
            # Return to ready state after 1.8 seconds
            self.after(1800, lambda: self.update_app_state("READY") if self.app_state == "SUCCESS" else None)
            
        elif new_state == "ERROR":
            err_msg = error_detail if error_detail else "Could not understand audio"
            self.status_dot.configure(fg_color=self.colors["accent_error"])
            self.status_label.configure(text="ERROR", text_color=self.colors["accent_error"])
            self.sublabel.configure(text=err_msg, text_color=self.colors["accent_error"])
            self.target_amplitude = 0.0
            
            self.canvas.itemconfig("mic_bg", fill=self.colors["accent_error"], outline=self.colors["accent_error"])
            
            # Return to ready state after 2.5 seconds
            self.after(2500, lambda: self.update_app_state("READY") if self.app_state == "ERROR" else None)

    # ==========================================
    # SPEECH ENGINE - NATIVE RECORDER THREADS
    # ==========================================
    def start_dictation_recording(self):
        self.recording_active = True
        # Fire off background dictation recording thread
        threading.Thread(target=self.dictation_record_worker, daemon=True).start()

    def dictation_record_worker(self):
        # Native Windows MCI Audio Recorder using windll
        winmm = ctypes.windll.winmm
        
        # Clean any old references
        winmm.mciSendStringW("close recsound", None, 0, 0)
        
        # Open a new waveaudio recorder channel
        winmm.mciSendStringW("open new type waveaudio alias recsound", None, 0, 0)
        
        # Configure formatting: 16-bit PCM Mono, 16kHz sample rate (optimal for Google transcription)
        winmm.mciSendStringW("set recsound time format ms", None, 0, 0)
        winmm.mciSendStringW("set recsound alignment 2 bitspersample 16 samplespersec 16000 channels 1 bytespersec 32000", None, 0, 0)
        
        # Start recording
        winmm.mciSendStringW("record recsound", None, 0, 0)
        
        start_time = time.time()
        max_duration = 60.0 # Safety limit of 1 minute per capture
        
        while self.recording_active:
            elapsed = time.time() - start_time
            if elapsed >= max_duration:
                break
                
            # Update countdown status in sublabel
            remaining = int(max_duration - elapsed)
            # Update UI from the thread safely using after
            self.after(0, self.update_recording_sublabel, remaining)
            time.sleep(0.1)
            
        # Stop recording channel
        winmm.mciSendStringW("stop recsound", None, 0, 0)
        
        # Output temporary WAV file in user directory
        temp_wav = os.path.join(os.getcwd(), "aura_speech_temp.wav")
        # MCI save command (wrapped in quotes for spaces in paths)
        winmm.mciSendStringW(f'save recsound "{temp_wav}"', None, 0, 0)
        winmm.mciSendStringW("close recsound", None, 0, 0)
        
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
                    # Record the full audio content from file
                    audio = recognizer.record(source)
                
                # Fetch dropdown selected language and map to API locale codes
                lang_selection = self.sidebar_lang_menu.get()
                lang_codes = {
                    "English": "en-US",
                    "Spanish": "es-ES",
                    "French": "fr-FR",
                    "German": "de-DE",
                    "Hindi": "hi-IN"
                }
                api_lang = lang_codes.get(lang_selection, "en-US")
                
                # Google Speech Recognition (free cloud endpoint, no keys required)
                transcribed_text = recognizer.recognize_google(audio, language=api_lang)
                
            except sr.UnknownValueError:
                error_info = "Could not understand your speech"
            except sr.RequestError as e:
                error_info = f"Network or Speech API error: {e}"
            except Exception as e:
                error_info = f"Transcription failed: {e}"
            finally:
                # Always clean up temporary WAV file
                try:
                    os.remove(filepath)
                except Exception:
                    pass
        else:
            error_info = "No voice recorded. Please try again."
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except Exception:
                    pass
                    
        # Update results back onto the GUI main thread
        self.after(0, self.on_transcription_complete, transcribed_text, error_info)

    def on_transcription_complete(self, text, error_info):
        if error_info:
            self.update_app_state("ERROR", error_info)
        else:
            self.update_app_state("SUCCESS")
            # Grab current content
            current_value = self.textbox.get("1.0", tk.END).strip()
            
            # Format and add recognized dictation
            if current_value:
                updated_value = current_value + " " + text
            else:
                updated_value = text
                
            self.textbox.delete("1.0", tk.END)
            self.textbox.insert("1.0", updated_value)
            self.update_counters()
            self.show_toast("Transcribed speech successfully!", "success")

    # ==========================================
    # CANVAS VISUALIZATION LOOP
    # ==========================================
    def run_visualizer_loop(self):
        def loop():
            if not self.animation_running:
                return
                
            self.update_visuals()
            # Loop roughly at ~60fps (16ms delta)
            self.after(16, loop)
        loop()

    def update_visuals(self):
        cx, cy = self.btn_x, self.btn_y
        
        # 1. Smoothly interpolate amplitude towards target
        self.current_amplitude += (self.target_amplitude - self.current_amplitude) * 0.12
        
        # 2. Add phase speed based on states
        if self.app_state == "LISTENING":
            self.phase += 0.16
            # Jitter target amplitude slightly to simulate voice spikes
            self.target_amplitude = random.uniform(30.0, 55.0)
        elif self.app_state == "PROCESSING":
            self.phase += 0.28  # Faster speed representing calculating/spinning
            self.target_amplitude = 18.0
        else:
            self.phase += 0.04  # Slow wave float when idle
            if self.app_state in ["READY", "SUCCESS", "ERROR"]:
                self.target_amplitude = 8.0 if self.app_state == "READY" else (6.0 if self.app_state == "SUCCESS" else 0.0)
                
        # 3. Wipe and redraw visualizer layers
        self.canvas.delete("animation_wave")
        
        style = self.sidebar_vis_menu.get()
        if style == "None":
            return
            
        # Draw dynamic animation styles
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
        for x in range(0, w + 15, 15):
            # Sine wave envelope tapering off at ends
            envelope = math.sin(math.pi * x / w) if 0 <= x <= w else 0
            # Complex double-sine equation for natural feel
            y = cy + math.sin(x * 0.035 - self.phase) * amp * envelope
            points1.extend([x, y])
        self.canvas.create_line(
            points1, smooth=True, fill=self.colors["accent_primary"], width=3,
            tags="animation_wave"
        )
        
        # Secondary Purple Wave
        points2 = []
        for x in range(0, w + 15, 15):
            envelope = math.sin(math.pi * x / w)
            y = cy + math.sin(x * 0.052 + self.phase * 1.3 + 1.2) * (amp * 0.6) * envelope
            points2.extend([x, y])
        self.canvas.create_line(
            points2, smooth=True, fill=self.colors["accent_secondary"], width=2.2,
            tags="animation_wave"
        )
        
        # Background Muted Teal Wave
        points3 = []
        for x in range(0, w + 15, 15):
            envelope = math.sin(math.pi * x / w)
            y = cy + math.sin(x * 0.022 - self.phase * 0.7 + 3.1) * (amp * 0.35) * envelope
            points3.extend([x, y])
        self.canvas.create_line(
            points3, smooth=True, fill=self.colors["accent_tertiary"], width=1.5,
            tags="animation_wave"
        )
        
        # Always lower waves behind mic buttons
        self.canvas.tag_lower("animation_wave", "mic_button")

    def draw_concentric_pulses(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        
        if self.app_state == "LISTENING":
            self.ripple_radius += 1.8
            if self.ripple_radius > 120.0:
                self.ripple_radius = float(r)
            
            # Fade calculation
            fade_range = 120.0 - r
            current_diff = self.ripple_radius - r
            alpha = max(0.0, min(1.0, 1.0 - (current_diff / fade_range)))
            
            # Interpolate ripple color from Accent to App Background
            glow_col = self.fade_color(self.colors["accent_error"], self.colors["bg_app"], alpha)
            
            self.canvas.create_oval(
                cx - self.ripple_radius, cy - self.ripple_radius,
                cx + self.ripple_radius, cy + self.ripple_radius,
                outline=glow_col, width=2.5, tags="animation_wave"
            )
        else:
            # Subtle steady breath glow ring
            breath_amp = math.sin(self.phase * 1.5) * 6.0
            radius = r + 10 + breath_amp
            self.canvas.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                outline=self.colors["accent_primary"], width=1, tags="animation_wave"
            )
            
        self.canvas.tag_lower("animation_wave", "mic_button")

    def draw_solid_glow_ring(self):
        cx, cy, r = self.btn_x, self.btn_y, self.btn_r
        # Dynamic outline thickness pulsing based on amplitude
        outline_thickness = 1.0 + (self.current_amplitude / 12.0)
        
        color = self.colors["accent_primary"]
        if self.app_state == "LISTENING":
            color = self.colors["accent_error"]
        elif self.app_state == "PROCESSING":
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
    # TOOLBAR OPERATIONS & TOAST ALERTS
    # ==========================================
    def show_toast(self, text, style="success"):
        # Select colors based on theme
        colors_map = {
            "success": ("#10B981", "#FFFFFF"), # Emerald green
            "warning": ("#F59E0B", "#0F172A"), # Orange/Amber
            "danger": ("#EF4444", "#FFFFFF"),  # Crimson
            "info": ("#3B82F6", "#FFFFFF")     # Bright Blue
        }
        bg, fg = colors_map.get(style, ("#10B981", "#FFFFFF"))
        
        self.toast_label.configure(
            text=text, 
            fg_color=bg, 
            text_color=fg
        )
        
        # Cancel any pending toast clears
        if hasattr(self, "_toast_clear_job") and self._toast_clear_job:
            self.after_cancel(self._toast_clear_job)
            
        # Hide after 2.2 seconds
        self._toast_clear_job = self.after(2200, self.clear_toast)

    def clear_toast(self):
        self.toast_label.configure(text="", fg_color="transparent")
        self._toast_clear_job = None

    def update_counters(self):
        text = self.textbox.get("1.0", tk.END).strip()
        chars = len(text)
        words = len(text.split()) if text else 0
        self.counter_label.configure(text=f"Words: {words} | Chars: {chars}")

    def copy_to_clipboard(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.show_toast("Copied to clipboard!", "success")
        else:
            self.show_toast("Nothing to copy!", "warning")

    def save_to_file(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            self.show_toast("Nothing to save!", "warning")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Documents", "*.txt"), ("All Files", "*.*")],
            title="Save Transcription"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(text)
                self.show_toast("File saved successfully!", "success")
            except Exception as e:
                self.show_toast(f"Failed to save: {e}", "danger")

    def clear_text(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            return
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to clear the transcript?"):
            self.textbox.delete("1.0", tk.END)
            self.update_counters()
            self.show_toast("Transcript cleared", "info")

    # ==========================================
    # TEXT TO SPEECH (TTS) WORKER SYSTEM
    # ==========================================
    def speak_text(self):
        text = self.textbox.get("1.0", tk.END).strip()
        if not text:
            self.show_toast("Nothing to speak!", "warning")
            return
            
        if self.tts_speaking:
            # If active, button works as a STOP toggle
            self.stop_tts()
            return
            
        self.tts_speaking = True
        self.speak_btn.configure(text="⏹ Stop Speech", fg_color=self.colors["accent_error"])
        
        # Run TTS on a daemon worker thread to prevent GUI freezing
        threading.Thread(target=self.tts_voice_worker, args=(text,), daemon=True).start()

    def tts_voice_worker(self, text):
        try:
            self.tts_engine = pyttsx3.init()
            
            # Match speaking rate and set default settings
            self.tts_engine.setProperty('rate', 165)
            
            # Setup speech dialect options according to app dictation settings
            voices = self.tts_engine.getProperty('voices')
            lang_selection = self.sidebar_lang_menu.get()
            
            # Basic voice matcher search
            matched_voice = None
            for voice in voices:
                # E.g. Check for language matching substring
                if lang_selection.lower() in voice.name.lower() or lang_selection.lower() in getattr(voice, 'languages', []):
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
            self.after(0, self.reset_tts_button)

    def stop_tts(self):
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception:
                pass
        self.reset_tts_button()

    def reset_tts_button(self):
        self.speak_btn.configure(text="🔊 Speak Text", fg_color="#2563EB")
        self.tts_speaking = False

    # ==========================================
    # SHUTDOWN / EXIT
    # ==========================================
    def on_close(self):
        # Stop visualizer loop & clean up
        self.animation_running = False
        self.recording_active = False
        self.stop_tts()
        self.destroy()

if __name__ == "__main__":
    app = AuraVoiceApp()
    app.mainloop()
