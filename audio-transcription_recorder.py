import tkinter as tk
from tkinter import messagebox, filedialog, Toplevel
import os
import sys
import json
import wave
import pyaudio
import pygame
import time
import threading
import numpy as np
import datetime

# -------------------------
# Scaling - MAIN WINDOW ONLY
# -------------------------
# These scales will apply only to the main (root) window UI.
SCALE_TEXT_MAIN = 2   # multiply text sizes by this in main window
SCALE_BUTTON_MAIN = 1.5 # multiply button sizes by this in main window

# Base sizes for non-main windows and widgets
LABEL_BASE = 10
ENTRY_BASE = 12
BUTTON_BASE = 12
HEADER_BASE = 18
ITEM_HEIGHT_BASE = 20

# Fonts used in non-main windows (About, metadata popups, dropdown list)
LABEL_FONT_NORMAL = ('Arial', LABEL_BASE)
ENTRY_FONT_NORMAL = ('Arial', ENTRY_BASE)
BUTTON_FONT_NORMAL = ('Arial', BUTTON_BASE)
HEADER_FONT_NORMAL = ('Arial', HEADER_BASE, 'bold')
LISTBOX_FONT_NORMAL = ENTRY_FONT_NORMAL
ITEM_HEIGHT_NORMAL = ITEM_HEIGHT_BASE

# Fonts used in main window (scaled)
LABEL_FONT_MAIN = ('Arial', int(LABEL_BASE * SCALE_TEXT_MAIN))
ENTRY_FONT_MAIN = ('Arial', int(ENTRY_BASE * SCALE_TEXT_MAIN))
BUTTON_FONT_MAIN = ('Arial', int(BUTTON_BASE * SCALE_BUTTON_MAIN))
HEADER_FONT_MAIN = ('Arial', int(HEADER_BASE * SCALE_TEXT_MAIN), 'bold')
TEXTBOX_FONT_MAIN = ENTRY_FONT_MAIN
LISTBOX_FONT_MAIN = ENTRY_FONT_MAIN
ITEM_HEIGHT_MAIN = int(ITEM_HEIGHT_BASE * SCALE_TEXT_MAIN)

# Window geometry for main window
ROOT_GEOMETRY_MAIN = f"{int(1000 * 1.6)}x{int(800 * 1.4)}"  # larger window to accommodate bigger UI

# -------------------------
# SearchableDropdown widget
# (uses NORMAL fonts so popup lists are normal-sized)
# -------------------------
class SearchableDropdown:
    """
    Entry + Toplevel listbox popup.
    This widget uses NORMAL fonts (not main-window scaling), so popups remain standard size.
    """
    def __init__(self, parent, options, default=None, max_visible=8, use_main_scale=False):
        self.parent = parent
        self.options = list(options)
        self.max_visible = max_visible
        self.var = tk.StringVar(value=default if default is not None else "")
        self.use_main_scale = use_main_scale  # if True, use main fonts (rare)
        # Choose fonts depending on whether caller asked to use main scaling
        entry_font = ENTRY_FONT_MAIN if use_main_scale else ENTRY_FONT_NORMAL
        listbox_font = LISTBOX_FONT_MAIN if use_main_scale else LISTBOX_FONT_NORMAL
        item_height = ITEM_HEIGHT_MAIN if use_main_scale else ITEM_HEIGHT_NORMAL

        # Entry widget
        self.widget = tk.Entry(parent, textvariable=self.var, bg='#444444', fg='white',
                               insertbackground='white', font=entry_font)
        # Popup Toplevel containing listbox + scrollbar
        self.popup = None
        self.listbox_font = listbox_font
        self.item_height = item_height
        self.filtered = self.options.copy()
        # Bindings
        self.widget.bind("<FocusIn>", lambda e: self.show_popup())
        self.widget.bind("<Button-1>", lambda e: self.show_popup())
        self.widget.bind("<KeyRelease>", self.on_type)
        self.widget.bind("<Down>", self.on_down)
        self.widget.bind("<Up>", self.on_up)
        self.widget.bind("<Return>", self.on_return)
        self.widget.bind("<Escape>", lambda e: self.hide_popup())

    def create_popup(self):
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            return
        self.popup = tk.Toplevel(self.parent)
        self.popup.wm_overrideredirect(True)
        self.popup.attributes("-topmost", True)
        self.listbox = tk.Listbox(self.popup, activestyle='none', highlightthickness=0, font=self.listbox_font)
        self.scrollbar = tk.Scrollbar(self.popup, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.config(yscrollcommand=self.scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.bind("<ButtonRelease-1>", self.on_click)
        self.listbox.bind("<Motion>", lambda e: self.listbox.selection_clear(0, tk.END))
        # Mouse wheel for listbox scrolling (cross-platform)
        self.listbox.bind("<Enter>", lambda e: self._bind_mousewheel(self.listbox))
        self.listbox.bind("<Leave>", lambda e: self._unbind_mousewheel(self.listbox))
        # Hide popup if focus is lost
        self.popup.bind("<FocusOut>", lambda e: self.hide_popup())

    def _bind_mousewheel(self, widget):
        widget.bind_all("<MouseWheel>", self._on_mousewheel)      # Windows
        widget.bind_all("<Button-4>", self._on_mousewheel)        # Linux scroll up
        widget.bind_all("<Button-5>", self._on_mousewheel)        # Linux scroll down

    def _unbind_mousewheel(self, widget):
        widget.unbind_all("<MouseWheel>")
        widget.unbind_all("<Button-4>")
        widget.unbind_all("<Button-5>")

    def _on_mousewheel(self, event):
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
                self.listbox.yview_scroll(-1, "units")
            else:
                self.listbox.yview_scroll(1, "units")

    def show_popup(self):
        self.create_popup()
        # Position popup under entry
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height()
        # compute popup height according to max_visible
        visible = min(self.max_visible, max(1, len(self.filtered)))
        popup_height = visible * self.item_height
        self.popup.geometry(f"{self.widget.winfo_width()}x{popup_height}+{x}+{y}")
        self.update_list()
        self.popup.deiconify()
        try:
            self.popup.focus_force()
        except Exception:
            pass

    def hide_popup(self):
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            self.popup.withdraw()

    def update_list(self):
        if not self.popup or not tk.Toplevel.winfo_exists(self.popup):
            return
        self.listbox.delete(0, tk.END)
        for item in self.filtered:
            self.listbox.insert(tk.END, item)
        self.listbox.selection_clear(0, tk.END)
        if self.filtered:
            self.listbox.see(0)

    def on_type(self, event):
        txt = self.var.get().strip().lower()
        if txt == "":
            self.filtered = self.options.copy()
        else:
            self.filtered = [o for o in self.options if txt in o.lower()]
        self.show_popup()

    def on_click(self, event):
        idx = self.listbox.curselection()
        if idx:
            sel = self.listbox.get(idx)
            self.var.set(sel)
        self.hide_popup()
        self.widget.focus_set()

    def on_down(self, event):
        self.show_popup()
        if not self.listbox.curselection():
            self.listbox.selection_set(0)
            self.listbox.activate(0)
        else:
            cur = self.listbox.curselection()[0]
            if cur < self.listbox.size() - 1:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(cur + 1)
                self.listbox.activate(cur + 1)
                self.listbox.see(cur + 1)
        return "break"

    def on_up(self, event):
        self.show_popup()
        if not self.listbox.curselection():
            self.listbox.selection_set(0)
            self.listbox.activate(0)
        else:
            cur = self.listbox.curselection()[0]
            if cur > 0:
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(cur - 1)
                self.listbox.activate(cur - 1)
                self.listbox.see(cur - 1)
        return "break"

    def on_return(self, event):
        sel = None
        if self.popup and tk.Toplevel.winfo_exists(self.popup):
            idx = self.listbox.curselection()
            if idx:
                sel = self.listbox.get(idx)
        if not sel:
            txt = self.var.get().strip()
            matches = [o for o in self.options if o.lower() == txt.lower()]
            if matches:
                sel = matches[0]
        if sel:
            self.var.set(sel)
        self.hide_popup()
        return "break"

# -------------------------
# Main Application
# -------------------------
class AudioTextCollector:
    def __init__(self, master):
        self.master = master
        self.master.title("Audio Text Collector")
        # configure main window geometry and bg
        self.master.configure(bg='#333333')
        self.master.geometry(ROOT_GEOMETRY_MAIN)

        # Directories
        self.audio_path = "audio/"
        self.transcripts_path = "transcripts/"
        os.makedirs(self.audio_path, exist_ok=True)
        os.makedirs(self.transcripts_path, exist_ok=True)

        # State variables
        self.source_lines = []
        self.current_index = 0
        self.current_session = None
        self.session_path = ""
        self.session_txt = ""
        self.session_number = 1
        self.temp_audio = "temp.wav"
        self.current_audio = None
        self.current_sent_id = None
        self.is_recording = False
        self.is_playing = False
        self.recording_start_time = 0
        self.frames = []
        self.stream = None
        self.checkpoint_file = "checkpoint.txt"
        self.speaker_id = "spk01"
        self.source_file = None
        self.session_start_datetime = None

        # New flag: replacing mode (used to prevent checkpoint change / append when replacing)
        self.is_replacing = False

        # UI elements (main window)
        self.prev_nums = []
        self.prev_labels = []
        self.current_num = None
        self.next_nums = []
        self.next_labels = []
        self.timer_label = None
        self.progress_canvas = None
        self.play_btn = None
        self.new_session_btn = None

        # Setup main UI (uses MAIN scaled fonts)
        self.setup_ui_main()

        # audio init
        original_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        self.p = pyaudio.PyAudio()
        pygame.mixer.init()
        sys.stderr.close()
        sys.stderr = original_stderr

        self.load_checkpoint()
        if self.current_session:
            self.session_path = os.path.join(self.audio_path, self.current_session)
            self.session_txt = os.path.join(self.transcripts_path, f"{self.current_session}.txt")
            if not self.session_start_datetime:
                start_dt = self._load_session_start_from_info(self.session_path)
                if start_dt:
                    self.session_start_datetime = start_dt
            self.new_session_btn.config(bg='red')

    # -------------------------
    # Main window UI (SCALED)
    # -------------------------
    def setup_ui_main(self):
        # larger button internal padding
        btn_ipadx = int(8 * SCALE_BUTTON_MAIN)
        btn_ipady = int(8 * SCALE_BUTTON_MAIN)

        top_frame = tk.Frame(self.master, bg='#333333')
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=10)

        # Buttons use MAIN sized font
        self.load_btn = tk.Button(top_frame, text="📂 Load", command=self.load_source,
                                  bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.load_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.new_session_btn = tk.Button(top_frame, text="➕ New", command=self.start_new_session,
                                         bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.new_session_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.about_btn = tk.Button(top_frame, text="ℹ️ About", command=self.show_about,
                                   bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.about_btn.pack(side=tk.RIGHT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        # Text display frame (labels and text use MAIN fonts)
        self.text_frame = tk.Frame(self.master, bg='#333333')
        self.text_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=False)

        for i in range(3):
            num_label = tk.Label(self.text_frame, text="", bg='#333333', fg='#ffffff',
                                 font=LABEL_FONT_MAIN, width=5, anchor='e')
            num_label.grid(row=i, column=0, padx=5, pady=8)
            self.prev_nums.append(num_label)
            prev_label = tk.Label(self.text_frame, text="", bg='#333333', fg='#aaaaaa',
                                  font=LABEL_FONT_MAIN, anchor='w')
            prev_label.grid(row=i, column=1, sticky='ew', pady=8)
            self.prev_labels.append(prev_label)

        self.current_num = tk.Label(self.text_frame, text="", bg='#333333', fg='#ffffff',
                                    font=LABEL_FONT_MAIN, width=5, anchor='e')
        self.current_num.grid(row=3, column=0, padx=5, pady=10)
        self.text_box = tk.Text(self.text_frame, height=3, wrap=tk.WORD, bg='#444444',
                                fg='white', insertbackground='white', font=TEXTBOX_FONT_MAIN)
        self.text_box.grid(row=3, column=1, sticky='ew', pady=10)

        for i in range(3):
            num_label = tk.Label(self.text_frame, text="", bg='#333333', fg='#ffffff',
                                 font=LABEL_FONT_MAIN, width=5, anchor='e')
            num_label.grid(row=4+i, column=0, padx=5, pady=8)
            self.next_nums.append(num_label)
            next_label = tk.Label(self.text_frame, text="", bg='#333333', fg='#aaaaaa',
                                  font=LABEL_FONT_MAIN, anchor='w')
            next_label.grid(row=4+i, column=1, sticky='ew', pady=8)
            self.next_labels.append(next_label)

        self.text_frame.columnconfigure(1, weight=1)

        # Waveform canvas bigger
        self.waveform_canvas = tk.Canvas(self.master, bg='#444444', height=int(100 * SCALE_TEXT_MAIN), highlightthickness=0)
        self.waveform_canvas.pack(fill=tk.X, padx=10, pady=10)

        bottom_frame = tk.Frame(self.master, bg='#333333')
        bottom_frame.pack(fill=tk.X, pady=10)

        self.prev_btn = tk.Button(bottom_frame, text="◀️ Prev", command=self.previous_line,
                                  bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.prev_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.replace_btn = tk.Button(bottom_frame, text="🔄 Replace", command=self.replace_recording,
                                     bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.replace_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        # Save Edit button
        self.save_edit_btn = tk.Button(bottom_frame, text="💾 Save Edit", command=self.save_current_edit,
                                       bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.save_edit_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.play_btn = tk.Button(bottom_frame, text="▶️ Play", command=self.toggle_play,
                                  bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.play_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.next_btn = tk.Button(bottom_frame, text="▶️ Next", command=self.next_line,
                                  bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.next_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.link_btn = tk.Button(bottom_frame, text="🔗 Link Line", command=self.link_line,
                                  bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.link_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.end_session_btn = tk.Button(bottom_frame, text="⏹️ End", command=self.end_session,
                                         bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.end_session_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        self.load_session_btn = tk.Button(bottom_frame, text="📂 Load Ses", command=self.load_existing_session,
                                          bg='#555555', fg='white', font=BUTTON_FONT_MAIN)
        self.load_session_btn.pack(side=tk.LEFT, padx=5, ipady=btn_ipady, ipadx=btn_ipadx)

        # Timer label (scaled)
        self.timer_label = tk.Label(self.master, text="00:00.000 / 00:00.000", bg='#333333',
                                    fg='white', font=ENTRY_FONT_MAIN)
        self.timer_label.pack(fill=tk.X, pady=10)

        # Progress canvas
        self.progress_canvas = tk.Canvas(self.master, bg='#444444', height=int(10 * SCALE_TEXT_MAIN), highlightthickness=0)
        self.progress_canvas.pack(fill=tk.X, padx=10)

        # Keyboard bindings
        self.master.bind('<Left>', lambda e: self.previous_line())
        self.master.bind('<Right>', lambda e: self.next_line())
        self.master.bind('<BackSpace>', lambda e: self.replace_recording())
        self.master.bind('<Return>', lambda e: self.link_line())
        self.master.bind('<space>', self.space_handler)
        self.master.bind('<Control-o>', lambda e: self.load_source())
        self.master.bind('<Control-s>', lambda e: self.save_checkpoint())
        self.master.bind('<Control-e>', lambda e: self.save_current_edit())

    # -------------------------
    # Checkpoint & session info (unchanged)
    # -------------------------
    def space_handler(self, event):
        if self.master.focus_get() != self.text_box:
            if self.is_recording:
                self.pause_recording()
            elif self.current_audio:
                self.toggle_play()
            else:
                self.resume_recording()

    def load_checkpoint(self):
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.current_index = data.get('line_index', 0)
                    self.current_session = data.get('session', None)
                    sess_start = data.get('session_start', None)
                    if sess_start:
                        try:
                            self.session_start_datetime = datetime.datetime.fromisoformat(sess_start)
                        except Exception:
                            self.session_start_datetime = None
                elif isinstance(data, int):
                    self.current_index = data
                    self.current_session = None
                else:
                    raise ValueError("Invalid checkpoint data")
            except Exception as e:
                print(f"Error loading checkpoint: {e}")
                self.current_index = 0
                self.current_session = None
        else:
            self.current_index = 0
            self.current_session = None
        self.save_checkpoint()

    def save_checkpoint(self):
        data = {
            'line_index': self.current_index,
            'session': self.current_session,
            'session_start': self.session_start_datetime.isoformat() if self.session_start_datetime else None
        }
        with open(self.checkpoint_file, 'w') as f:
            json.dump(data, f)

    def _save_session_info_file(self, session_path, start_dt: datetime.datetime):
        """
        Save only start_datetime (keeps backward compatibility).
        Additional session-level fields are written in save_meta() directly.
        """
        try:
            info = {'start_datetime': start_dt.isoformat()}
            with open(os.path.join(session_path, "session_info.json"), 'w', encoding='utf-8') as sf:
                json.dump(info, sf)
        except Exception as e:
            print(f"Failed to save session_info.json: {e}")

    def _load_session_start_from_info(self, session_path):
        try:
            info_path = os.path.join(session_path, "session_info.json")
            if os.path.exists(info_path):
                with open(info_path, 'r', encoding='utf-8') as sf:
                    info = json.load(sf)
                if 'start_datetime' in info:
                    return datetime.datetime.fromisoformat(info['start_datetime'])
        except Exception as e:
            print(f"Failed to load session_info.json: {e}")
        return None

    # -------------------------
    # Source loading / display
    # -------------------------
    def load_source(self):
        file = filedialog.askopenfilename(initialdir=".", title="Select Source Text File", filetypes=[("Text files", "*.txt")])
        if file:
            self.source_file = file
            with open(file, 'r', encoding='utf-8') as f:
                self.source_lines = [line.strip() for line in f.readlines() if line.strip()]
            # IMPORTANT: do NOT reset self.current_index here — keep checkpoint behavior intact
            # just make sure current_index is within bounds
            if self.current_index < 0:
                self.current_index = 0
            if self.current_index >= len(self.source_lines):
                self.current_index = max(0, len(self.source_lines) - 1)
            # clear replace flag when loading a new source
            self.is_replacing = False
            self.update_display()
            print("Source file loaded: " + file)
        else:
            messagebox.showinfo("Info", "No file selected.")

    def update_display(self):

        if not self.source_lines:
            return
        self.text_box.delete('1.0', tk.END)
        self.text_box.insert(tk.END, self.source_lines[self.current_index])

        for i in range(3):
            idx = self.current_index - (3 - i)
            if idx >= 0:
                self.prev_nums[i].config(text=f"{idx + 1}:")
                self.prev_labels[i].config(text=self.source_lines[idx])
            else:
                self.prev_nums[i].config(text="")
                self.prev_labels[i].config(text="")

        self.current_num.config(text=f"{self.current_index + 1}:")
        for i in range(3):
            idx = self.current_index + (i + 1)
            if idx < len(self.source_lines):
                self.next_nums[i].config(text=f"{idx + 1}:")
                self.next_labels[i].config(text=self.source_lines[idx])
            else:
                self.next_nums[i].config(text="")
                self.next_labels[i].config(text="")

        self.load_current_audio()
        if self.current_audio:
            self.draw_static_waveform()
        else:
            self.waveform_canvas.delete("wave")
        self.update_button_state()

    def load_current_audio(self):
        self.current_sent_id = None
        self.current_audio = None
        if self.current_session:
            text = self.text_box.get('1.0', tk.END).strip()
            if text and os.path.exists(self.session_txt):
                with open(self.session_txt, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f.readlines()]
                try:
                    i = lines.index(text)
                    self.current_sent_id = i + 1
                    audio_file = os.path.join(self.session_path, f"{self.speaker_id}_{self.current_session}_sent{self.current_sent_id:04d}.wav")
                    if os.path.exists(audio_file):
                        self.current_audio = audio_file
                except ValueError:
                    pass

    # -------------------------
    # Recording/session flow (unchanged except for replace logic)
    # -------------------------
    def start_new_session(self):
        if not self.source_lines:
            messagebox.showerror("Error", "Load source first")
            return
        sessions = [d for d in os.listdir(self.audio_path) if d.startswith('session_')]
        if sessions:
            nums = []
            for d in sessions:
                try:
                    nums.append(int(d.split('_')[1]))
                except Exception:
                    pass
            self.session_number = max(nums) + 1 if nums else 1
        session_name = f"session_{self.session_number:02d}"
        self.session_path = os.path.join(self.audio_path, session_name)
        os.makedirs(self.session_path, exist_ok=True)
        self.session_txt = os.path.join(self.transcripts_path, f"{session_name}.txt")
        open(self.session_txt, 'a', encoding='utf-8').close()
        self.current_session = session_name
        self.session_start_datetime = datetime.datetime.now()
        self._save_session_info_file(self.session_path, self.session_start_datetime)
        self.save_checkpoint()
        self.new_session_btn.config(bg='red')
        self.start_recording()
        print(f"New session {session_name} started at {self.session_start_datetime.isoformat()}.")

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        if os.path.exists(self.temp_audio):
            with wave.open(self.temp_audio, 'rb') as wf:
                self.frames = []
                while chunk := wf.readframes(1024):
                    self.frames.append(chunk)
        else:
            self.frames = []
        self.recording_start_time = time.time()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        self.rec_thread = threading.Thread(target=self.record_loop)
        self.rec_thread.start()
        self.update_timer()
        self.update_button_state()
        self.master.after(100, self.update_waveform)

    def record_loop(self):
        while self.is_recording:
            try:
                data = self.stream.read(1024)
                self.frames.append(data)
            except Exception as e:
                messagebox.showerror("Recording Error", str(e))
                self.is_recording = False

    def stop_recording(self, temp=True):
        if not self.is_recording:
            return
        self.is_recording = False
        self.rec_thread.join()
        self.stream.stop_stream()
        self.stream.close()
        if temp and self.frames:
            with wave.open(self.temp_audio, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
                wf.setframerate(44100)
                wf.writeframes(b''.join(self.frames))
            self.current_audio = self.temp_audio
            self.draw_static_waveform()
        self.update_button_state()

    def pause_recording(self):
        self.stop_recording(temp=True)

    def resume_recording(self):
        self.start_recording()

    def replace_recording(self):
        """
        Replace an existing session audio/transcription for the current sent id.
        - Only allowed if current_session is set and current_sent_id is not None.
        - Does NOT append new data to the session.
        - Sets self.is_replacing = True so link_line knows not to advance index or update checkpoint.
        """
        # Guard: must be editing an existing linked sentence
        if not self.current_session or self.current_sent_id is None:
            messagebox.showerror("Error", "No existing linked session item to replace. Use Link Line to create audio first.")
            return

        # Stop any current recording (without saving temp), delete any temp files
        self.stop_recording(temp=False)
        self.delete_temp()

        # Remove existing audio file for this sent id (we will overwrite when user links)
        audio_file = os.path.join(self.session_path, f"{self.speaker_id}_{self.current_session}_sent{self.current_sent_id:04d}.wav")
        try:
            if os.path.exists(audio_file):
                os.remove(audio_file)
        except Exception as e:
            print("Warning: failed to remove old audio during replace:", e)

        self.current_audio = None
        self.frames = []
        self.waveform_canvas.delete("wave")

        # Set replacing mode so link_line will not advance or change checkpoint
        self.is_replacing = True

        # Start recording replacement audio
        self.start_recording()

    def toggle_play(self):
        if not self.current_audio:
            return
        if self.is_playing:
            pygame.mixer.music.pause()
            self.is_playing = False
        else:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.unpause()
            else:
                pygame.mixer.music.load(self.current_audio)
                pygame.mixer.music.play()
            self.is_playing = True
        self.update_button_state()
        self.update_progress()

    def update_progress(self):
        if self.is_playing:
            pos_ms = pygame.mixer.music.get_pos()
            pos = pos_ms / 1000.0
            with wave.open(self.current_audio, 'rb') as wf:
                total_frames = wf.getnframes()
                rate = wf.getframerate()
                total = total_frames / rate if rate else 0
            percent = pos / total if total > 0 else 0
            width = self.progress_canvas.winfo_width()
            self.progress_canvas.delete("progress")
            self.progress_canvas.create_rectangle(0, 0, width * percent, int(10 * SCALE_TEXT_MAIN), fill='#00ff00', tags="progress")
            self.timer_label.config(text=f"{self.format_time(pos)} / {self.format_time(total)}")
            self.master.after(100, self.update_progress)
        else:
            self.timer_label.config(text="00:00.000 / 00:00.000")
            self.progress_canvas.delete("progress")

    def format_time(self, secs):
        mins = int(secs // 60)
        secs_int = int(secs % 60)
        ms = int((secs - secs_int) * 1000)
        return f"{mins:02d}:{secs_int:02d}.{ms:03d}"

    def update_timer(self):
        if self.is_recording:
            elapsed = time.time() - self.recording_start_time
            self.timer_label.config(text=f"{self.format_time(elapsed)} / --:--.---")
            self.master.after(100, self.update_timer)
        else:
            self.timer_label.config(text="00:00.000 / 00:00.000")

    def update_button_state(self):
        if self.is_recording:
            self.play_btn.config(text="⏸️ Pause Rec", command=self.pause_recording)
        elif self.current_audio:
            self.play_btn.config(text="▶️ Play/Pause", command=self.toggle_play)
        else:
            self.play_btn.config(text="▶️ Resume Rec", command=self.resume_recording)

    def update_waveform(self):
        if self.is_recording:
            if self.frames:
                data = b''.join(self.frames)
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                max_points = 1000
                if len(audio_data) > max_points:
                    audio_data = audio_data[::len(audio_data)//max_points]
                self.waveform_canvas.delete("wave")
                width = self.waveform_canvas.winfo_width()
                height = self.waveform_canvas.winfo_height()
                points = []
                for i, val in enumerate(audio_data):
                    x = (i / len(audio_data)) * width if len(audio_data) > 0 else 0
                    y = height / 2 - val * (height / 2)
                    points.extend([x, y])
                self.waveform_canvas.create_line(points, fill='#00ff00', tags="wave")
            self.master.after(100, self.update_waveform)
        else:
            self.waveform_canvas.delete("wave")

    def draw_static_waveform(self):
        if self.current_audio:
            with wave.open(self.current_audio, 'rb') as wf:
                data = wf.readframes(wf.getnframes())
                audio_data = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            max_points = 1000
            if len(audio_data) > max_points:
                audio_data = audio_data[::len(audio_data)//max_points]
            self.waveform_canvas.delete("wave")
            width = self.waveform_canvas.winfo_width()
            height = self.waveform_canvas.winfo_height()
            points = []
            for i, val in enumerate(audio_data):
                x = (i / len(audio_data)) * width if len(audio_data) > 0 else 0
                y = height / 2 - val * (height / 2)
                points.extend([x, y])
            self.waveform_canvas.create_line(points, fill='#00ff00', tags="wave")

    def delete_temp(self):
        if os.path.exists(self.temp_audio):
            os.remove(self.temp_audio)

    def previous_line(self):
        if self.current_index > 0:
            self.stop_recording(temp=False)
            self.delete_temp()
            self.current_audio = None
            self.current_index -= 1
            # Clear replace flag when navigating away
            self.is_replacing = False
            self.update_display()
                        # Only start recording automatically if we're in a session AND
            # the current line is NOT already linked (no audio present).
            if self.current_session:
                # If current_audio exists (i.e. this line already has an audio file), do NOT record.
                # Otherwise start recording for this line.
                if self.current_audio:
                    # already linked — do nothing (don't record)
                    return
                else:
                    # not linked — start recording for the new line
                    self.start_recording()

    def next_line(self):
        if self.current_index < len(self.source_lines) - 1:
            self.stop_recording(temp=False)
            self.delete_temp()
            self.current_audio = None
            self.current_index += 1
            self.save_checkpoint()
            # Clear replace flag when advancing normally
            self.is_replacing = False
            # update_display will call load_current_audio() and set self.current_audio / self.current_sent_id
            self.update_display()

            # Only start recording automatically if we're in a session AND
            # the current line is NOT already linked (no audio present).
            if self.current_session:
                # If current_audio exists (i.e. this line already has an audio file), do NOT record.
                # Otherwise start recording for this line.
                if self.current_audio:
                    # already linked — do nothing (don't record)
                    return
                else:
                    # not linked — start recording for the new line
                    self.start_recording()

    def link_line(self):
        """
        Save current temp recording to the session transcript. If self.is_replacing is True,
        do an in-place replace (update audio and session transcript for current_sent_id) and
        DO NOT advance current_index or save checkpoint. If not replacing, behave as before:
        - if the line exists in session transcript, update it
        - else append a new session line and advance
        """
        if not self.current_session:
            return
        # stop recording and store temp
        self.stop_recording(temp=True)
        if not (os.path.exists(self.temp_audio) or self.frames):
            return
        current_text = self.text_box.get('1.0', tk.END).strip()
        # load existing session transcript lines
        with open(self.session_txt, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if self.current_sent_id is not None:
            # update existing sentence line
            sent_id = self.current_sent_id
            # ensure lines list long enough
            if sent_id - 1 < len(lines):
                lines[sent_id - 1] = current_text + '\n'
            else:
                # unlikely, but append to ensure index correctness
                while len(lines) < sent_id - 1:
                    lines.append('\n')
                lines.append(current_text + '\n')
        else:
            # creating new entry
            sent_id = len(lines) + 1
            lines.append(current_text + '\n')

        audio_file = os.path.join(self.session_path, f"{self.speaker_id}_{self.current_session}_sent{sent_id:04d}.wav")
        # write audio: either move temp or write frames
        if os.path.exists(self.temp_audio):
            try:
                if os.path.exists(audio_file):
                    os.remove(audio_file)
                os.rename(self.temp_audio, audio_file)
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save audio file: {e}")
                return
        else:
            try:
                with wave.open(audio_file, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
                    wf.setframerate(44100)
                    wf.writeframes(b''.join(self.frames))
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to write audio: {e}")
                return

        self.frames = []
        # write transcript
        try:
            with open(self.session_txt, 'w', encoding='utf-8') as f:
                f.write(''.join(lines))
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to write session transcript: {e}")
            return

        self.current_sent_id = sent_id

        if self.is_replacing:
            # Replacement completed: do not advance or update checkpoint
            self.is_replacing = False
            # refresh display to reflect any changed audio/transcript
            self.update_display()
            # do not automatically start recording again
        else:
            # Normal linking flow: advance index and update checkpoint (unchanged behavior)
            if self.current_index < len(self.source_lines) - 1:
                self.current_index += 1
                self.save_checkpoint()
                self.update_display()
                self.start_recording()

    # -------------------------
    # End session metadata window (uses NORMAL fonts)
    # -------------------------
    def end_session(self):
        self.stop_recording(temp=True)
        meta_win = Toplevel(self.master)
        meta_win.title("Session Metadata")
        meta_win.configure(bg='#333333')
        meta_win.geometry("600x900")  # a bit taller to fit new dropdowns

        end_datetime = datetime.datetime.now()
        num_lines = sum(1 for _ in open(self.session_txt, 'r', encoding='utf-8')) if os.path.exists(self.session_txt) else 0
        total_dur = 0
        wav_files = [f for f in os.listdir(self.session_path) if f.endswith('.wav')]
        for wav in wav_files:
            with wave.open(os.path.join(self.session_path, wav), 'rb') as wf:
                total_dur += wf.getnframes() / wf.getframerate()
        avg_dur = total_dur / num_lines if num_lines > 0 else 0

        if not self.session_start_datetime:
            self.session_start_datetime = self._load_session_start_from_info(self.session_path)

        frame = tk.Frame(meta_win, bg='#333333')
        frame.pack(padx=20, pady=20, fill=tk.BOTH, expand=True)

        row = 0
        tk.Label(frame, text="Session Start Date:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        start_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        start_entry.insert(0, self.session_start_datetime.strftime('%Y-%m-%d %H:%M:%S') if self.session_start_datetime else "")
        start_entry.config(state='readonly')
        start_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Session End Date:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        end_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        end_entry.insert(0, end_datetime.strftime('%Y-%m-%d %H:%M:%S'))
        end_entry.config(state='readonly')
        end_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Data Collector Name:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        collector_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        collector_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Language:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        languages = [
            "English", "Arabic", "Amharic", "Afar", "Afrikaans", "Akan", "Albanian", "Armenian", "Assamese",
            "Aymara", "Azerbaijani", "Basque", "Belarusian", "Bengali", "Bhojpuri", "Bosnian", "Bulgarian",
            "Burmese", "Catalan", "Cebuano", "Chichewa", "Chinese (Simplified)", "Chinese (Traditional)",
            "Corsican", "Croatian", "Czech", "Danish", "Divehi", "Dutch", "English (US)", "English (UK)", "Esperanto",
            "Estonian", "Ewe", "Faroese", "Fijian", "Filipino", "Finnish", "French", "Frisian", "Galician", "Georgian",
            "German", "Greek", "Guarani", "Gujarati", "Haitian Creole", "Hausa", "Hawaiian", "Hebrew", "Hindi",
            "Hmong", "Hungarian", "Icelandic", "Igbo", "Ilocano", "Indonesian", "Irish", "Italian", "Japanese",
            "Javanese", "Kannada", "Kazakh", "Khmer", "Kinyarwanda", "Konkani", "Korean", "Krio", "Kurdish",
            "Kyrgyz", "Lao", "Latin", "Latvian", "Lingala", "Lithuanian", "Luxembourgish", "Macedonian", "Malagasy",
            "Malay", "Malayalam", "Maltese", "Maori", "Marathi", "Marshallese", "Mongolian", "Nepali", "Norwegian",
            "Nyanja", "Odia", "Oromo", "Pashto", "Persian", "Polish", "Portuguese", "Punjabi", "Quechua", "Romanian",
            "Russian", "Samoan", "Sanskrit", "Scots Gaelic", "Sepedi", "Serbian", "Sesotho", "Shona", "Sindhi",
            "Sinhala", "Slovak", "Slovenian", "Somali", "Sotho", "Spanish", "Sundanese", "Swahili", "Swedish",
            "Tagalog", "Tajik", "Tamil", "Tatar", "Telugu", "Thai", "Tigrinya", "Tongan", "Turkish", "Turkmen",
            "Ukrainian", "Urdu", "Uyghur", "Uzbek", "Vietnamese", "Welsh", "Wolof", "Xhosa", "Yiddish", "Yoruba", "Zulu"
        ]
        # Use the NORMAL-sized searchable dropdown so the popup is normal
        sd = SearchableDropdown(frame, languages, default="English", max_visible=8, use_main_scale=False)
        sd.widget.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        sensitive_var = tk.BooleanVar()
        check = tk.Checkbutton(frame, text="Sensitive Information Flagged", variable=sensitive_var, bg='#333333', fg='white', selectcolor='#444444', font=LABEL_FONT_NORMAL)
        check.grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Number of Audios/Lines:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        num_lines_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        num_lines_entry.insert(0, str(num_lines))
        num_lines_entry.config(state='readonly')
        num_lines_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Total Duration (seconds):", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        total_dur_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        total_dur_entry.insert(0, f"{total_dur:.2f}")
        total_dur_entry.config(state='readonly')
        total_dur_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Average Duration (seconds):", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        avg_dur_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        avg_dur_entry.insert(0, f"{avg_dur:.2f}")
        avg_dur_entry.config(state='readonly')
        avg_dur_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Speaker Gender:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        gender_var = tk.StringVar(value="Male")
        gender_frame = tk.Frame(frame, bg='#333333')
        tk.Radiobutton(gender_frame, text="Male", variable=gender_var, value="Male", bg='#333333', fg='white', selectcolor='#444444', font=LABEL_FONT_NORMAL).pack(side=tk.LEFT, padx=5)
        tk.Radiobutton(gender_frame, text="Female", variable=gender_var, value="Female", bg='#333333', fg='white', selectcolor='#444444', font=LABEL_FONT_NORMAL).pack(side=tk.LEFT, padx=5)
        gender_frame.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Speaker Age:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        age_bins = ["0-4", "5-8", "9-13", "14-17", "18-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85-100"]
        age_var = tk.StringVar(value=age_bins[0])
        age_menu = tk.OptionMenu(frame, age_var, *age_bins)
        age_menu.configure(bg='#444444', fg='white', highlightthickness=0, font=ENTRY_FONT_NORMAL)
        age_menu.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Speaker Accent:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        accent_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        accent_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # tk.Label(frame, text="Speaking Style:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        # style_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        # style_entry.grid(row=row, column=1, sticky='w', pady=5)
        # row += 1

        # -------------------------
        # New: Audio Style dropdown (relevant styles)
        # -------------------------
        tk.Label(frame, text="Speaking Style:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        speaking_styles = ["narrative", "drama", "music", "conversational", "news", "advertisement", "instructional", "educational"]
        speaking_style_var = tk.StringVar(value=speaking_styles[0])
        speaking_style_menu = tk.OptionMenu(frame, speaking_style_var, *speaking_styles)
        speaking_style_menu.configure(bg='#444444', fg='white', highlightthickness=0, font=ENTRY_FONT_NORMAL)
        speaking_style_menu.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        # -------------------------
        # New: Session Quality dropdown 0-5
        # -------------------------
        tk.Label(frame, text="Session Quality (0-5):", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        quality_options = [str(i) for i in range(6)]
        quality_var = tk.StringVar(value="5")
        quality_menu = tk.OptionMenu(frame, quality_var, *quality_options)
        quality_menu.configure(bg='#444444', fg='white', highlightthickness=0, font=ENTRY_FONT_NORMAL)
        quality_menu.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Sample Rate:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        sample_rate_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        sample_rate_entry.insert(0, "44100")
        sample_rate_entry.config(state='readonly')
        sample_rate_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Channels:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        channels_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        channels_entry.insert(0, "1")
        channels_entry.config(state='readonly')
        channels_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        tk.Label(frame, text="Bit Depth:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=row, column=0, sticky='e', pady=5)
        bit_depth_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        bit_depth_entry.insert(0, "16")
        bit_depth_entry.config(state='readonly')
        bit_depth_entry.grid(row=row, column=1, sticky='w', pady=5)
        row += 1

        def save_meta():
            collector = collector_entry.get()
            lang = sd.var.get()
            sensitive = sensitive_var.get()
            gender = gender_var.get()
            age = age_var.get()
            accent = accent_entry.get()
            #style = style_entry.get()
            speaking_style = speaking_style_var.get()          # new
            session_quality = int(quality_var.get())     # new
            if self.session_start_datetime and os.path.exists(self.session_path):
                # write minimal start_datetime first (this keeps earlier behavior)
                self._save_session_info_file(self.session_path, self.session_start_datetime)
            # Save additional session-level metadata to session_info.json
            try:
                info = {
                    'start_datetime': self.session_start_datetime.isoformat() if self.session_start_datetime else None,
                    'end_datetime': end_datetime.isoformat(),
                    'collector': collector,
                    'language': lang,
                    'sensitive_flagged': sensitive,
                    'speaking_style': speaking_style,
                    'session_quality': session_quality,
                    'speaker_gender': gender,
                    'speaker_age': age,
                    'speaker_accent': accent,
                    #'speaking_style': speaking_style
                }
                with open(os.path.join(self.session_path, "session_info.json"), 'w', encoding='utf-8') as sf:
                    json.dump(info, sf, ensure_ascii=False, indent=2)
            except Exception as e:
                print("Failed to save extended session_info.json:", e)

            self.generate_session_metadata()
            readme_path = os.path.join(self.audio_path, "README_audio.md")
            with open(readme_path, 'a', encoding='utf-8') as f:
                f.write(f"\nSession {self.current_session}:\n")
                f.write(f"Start Date: {self.session_start_datetime.strftime('%Y-%m-%d %H:%M:%S') if self.session_start_datetime else ''}\n")
                f.write(f"End Date: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Data Collector: {collector}\n")
                f.write(f"Language: {lang}\n")
                f.write(f"Sensitive Information Flagged: {sensitive}\n")
                f.write(f"Number of Audios/Lines: {num_lines}\n")
                f.write(f"Total Duration (seconds): {total_dur:.2f}\n")
                f.write(f"Average Duration (seconds): {avg_dur:.2f}\n")
                f.write(f"Speaker Gender: {gender}\n")
                f.write(f"Speaker Age: {age}\n")
                f.write(f"Speaker Accent: {accent}\n")
                #f.write(f"Speaking Style: {style}\n")
                f.write(f"Speaking Style: {speaking_style}\n")           # new
                f.write(f"Session Quality: {session_quality}\n")  # new
                f.write("Sample Rate: 44100\n")
                f.write("Channels: 1\n")
                f.write("Bit Depth: 16\n")
            meta_win.destroy()
            self.current_session = None
            self.session_start_datetime = None
            self.new_session_btn.config(bg='#555555')
            self.save_checkpoint()
            print("Session ended.")

        # Collector entry placed after the labels; place it now (normal font)
        tk.Label(frame, text="Data Collector Name:", bg='#333333', fg='white', font=LABEL_FONT_NORMAL).grid(row=2, column=0, sticky='e', pady=5)
        collector_entry = tk.Entry(frame, bg='#444444', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        collector_entry.grid(row=2, column=1, sticky='w', pady=5)

        save_btn = tk.Button(frame, text="Save", command=save_meta, bg='#555555', fg='white', font=BUTTON_FONT_NORMAL)
        save_btn.grid(row=row, column=0, columnspan=2, pady=20)

    # -------------------------
    # Metadata generation / merge (unchanged)
    # -------------------------
    def generate_session_metadata(self):
        meta_file = os.path.join(self.session_path, f"{self.current_session}.metadata.csv")
        with open(meta_file, 'w', encoding='utf-8') as f:
            f.write("sentence_id,audio_file,text,duration\n")
            with open(self.session_txt, 'r', encoding='utf-8') as txt:
                lines = [line.strip() for line in txt.readlines()]
            for i, text in enumerate(lines):
                sent_id = i + 1
                audio = f"{self.speaker_id}_{self.current_session}_sent{sent_id:04d}.wav"
                audio_p = os.path.join(self.session_path, audio)
                dur = 0
                if os.path.exists(audio_p):
                    with wave.open(audio_p, 'rb') as wf:
                        dur = wf.getnframes() / wf.getframerate()
                f.write(f"{sent_id},{audio},{text},{dur}\n")
        self.merge_metadata()

    def merge_metadata(self):
        global_meta = "metadata.csv"
        with open(global_meta, 'w', encoding='utf-8') as g:
            g.write("session,sentence_id,audio_file,text,duration\n")
            sessions = [d for d in os.listdir(self.audio_path) if d.startswith('session_')]
            for ses in sessions:
                meta = os.path.join(self.audio_path, ses, f"{ses}.metadata.csv")
                if os.path.exists(meta):
                    with open(meta, 'r', encoding='utf-8') as m:
                        next(m)
                        for line in m:
                            g.write(f"{ses},{line}")

    def load_existing_session(self):
        session_dir = filedialog.askdirectory(initialdir=self.audio_path, title="Select Session Folder")
        if session_dir:
            ses_name = os.path.basename(session_dir)
            self.session_path = session_dir
            self.session_txt = os.path.join(self.transcripts_path, f"{ses_name}.txt")
            if os.path.exists(self.session_txt):
                with open(self.session_txt, 'r', encoding='utf-8') as f:
                    self.source_lines = [line.strip() for line in f.readlines()]
                self.current_index = 0
                self.current_session = ses_name
                # clear replacing state when loading session
                self.is_replacing = False
                start_dt = self._load_session_start_from_info(self.session_path)
                if start_dt:
                    self.session_start_datetime = start_dt
                self.new_session_btn.config(bg='red')
                self.update_display()
                print(f"Session {ses_name} loaded for checking.")
            else:
                messagebox.showerror("Error", "Session transcript not found")

    # -------------------------
    # About dialog (NORMAL fonts)
    # -------------------------
    def show_about(self):
        about_win = Toplevel(self.master)
        about_win.title("About Audio Text Collector")
        about_win.configure(bg='#1f1f1f')
        about_win.geometry("700x520")

        header = tk.Frame(about_win, bg='#2b2b2b', pady=12)
        header.pack(fill=tk.X)
        tk.Label(header, text="Audio Text Collector", bg='#2b2b2b', fg='white', font=HEADER_FONT_NORMAL).pack(side=tk.LEFT, padx=18)
        tk.Label(header, text="v1.0", bg='#2b2b2b', fg='#cfcfcf', font=BUTTON_FONT_NORMAL).pack(side=tk.LEFT, padx=6)

        frame = tk.Frame(about_win, bg='#1f1f1f')
        frame.pack(padx=20, pady=12, fill=tk.BOTH, expand=True)

        left = tk.Frame(frame, bg='#1f1f1f')
        left.grid(row=0, column=0, sticky='nsew', padx=(0,10))
        right = tk.Frame(frame, bg='#1f1f1f')
        right.grid(row=0, column=1, sticky='nsew')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=2)

        card = tk.Frame(left, bg='#2a2a2a', bd=0, relief=tk.RIDGE, padx=12, pady=12)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(card, text="What it does", bg='#2a2a2a', fg='white', font=('Arial', 14, 'bold')).pack(anchor='w')
        summary = ("Lightweight offline tool to record and link sentence-level audio\n"
                   "— Session management\n"
                   "— Quick record/playback\n"
                   "— Metadata export for datasets")
        tk.Label(card, text=summary, bg='#2a2a2a', fg='#d0d0d0', justify='left', font=ENTRY_FONT_NORMAL).pack(anchor='w', pady=(8,0))

        details_frame = tk.Frame(right, bg='#1f1f1f')
        details_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(details_frame, text="Usage & Shortcuts", bg='#1f1f1f', fg='white', font=('Arial', 13, 'bold')).pack(anchor='w')
        usage_text = tk.Text(details_frame, height=12, wrap=tk.WORD, bg='#2a2a2a', fg='white', font=ENTRY_FONT_NORMAL, insertbackground='white')
        usage_text.insert(tk.END, "1. Load a source text file using the Load button.\n"
                                 "2. Start a new session to begin recording.\n"
                                 "3. Record audio for the current line using space bar or buttons.\n"
                                 "4. Use Link Line to save recordings and text.\n"
                                 "5. Navigate with arrows or buttons.\n"
                                 "6. End session and fill metadata when done.\n"
                                 "7. Load existing sessions for review or editing.\n\n"
                                 "Keyboard shortcuts:\nLeft/Right — navigation\nBackspace — replace (only for already-linked session lines)\nEnter — link line\nCtrl+O — load source\nCtrl+S — save checkpoint\nCtrl+E — save current edit")
        usage_text.config(state='disabled')
        usage_text.pack(fill=tk.BOTH, expand=True, pady=(6,0))

        close_btn = tk.Button(about_win, text="Close", command=about_win.destroy, bg='#555555', fg='white', font=BUTTON_FONT_NORMAL)
        close_btn.pack(pady=12)

    # -------------------------
    # Minimal new function to save edits back to source file (keeps everything else unchanged)
    # -------------------------
    def save_current_edit(self):
        """
        Save the text currently shown in the textbox back to the loaded source file.
        Preserves original file blank-line layout by mapping non-empty lines in the
        file to entries in self.source_lines.
        """
        if not self.source_lines:
            messagebox.showinfo("Info", "No source loaded.")
            return

        # Ensure current_index valid
        if not (0 <= self.current_index < len(self.source_lines)):
            messagebox.showerror("Error", "Current index out of range.")
            return

        new_text = self.text_box.get('1.0', tk.END).rstrip('\n')
        # Update in-memory lines first
        self.source_lines[self.current_index] = new_text

        if not self.source_file:
            # Nothing to write to on disk, but update display anyway
            self.update_display()
            messagebox.showinfo("Saved", "Edit saved to memory (no source file path).")
            return

        try:
            with open(self.source_file, 'r', encoding='utf-8') as f:
                orig_lines = f.readlines()
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to read source file: {e}")
            return

        out_lines = []
        src_idx = 0
        for ol in orig_lines:
            if ol.strip():  # map to source_lines entries
                if src_idx < len(self.source_lines):
                    out_lines.append(self.source_lines[src_idx] + '\n')
                else:
                    out_lines.append(ol)
                src_idx += 1
            else:
                out_lines.append(ol)

        # Append any remaining in-memory lines if original had fewer non-empty lines
        while src_idx < len(self.source_lines):
            out_lines.append(self.source_lines[src_idx] + '\n')
            src_idx += 1

        try:
            tmp_path = self.source_file + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as tf:
                tf.writelines(out_lines)
            os.replace(tmp_path, self.source_file)
        except Exception as e:
            # fallback direct write
            try:
                with open(self.source_file, 'w', encoding='utf-8') as f:
                    f.writelines(out_lines)
            except Exception as e2:
                messagebox.showerror("Save Error", f"Failed to write source file: {e2}")
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
                return

        # Refresh display and confirm
        self.update_display()
        messagebox.showinfo("Saved", f"Line {self.current_index + 1} saved to {os.path.basename(self.source_file)}.")

if __name__ == "__main__":
    root = tk.Tk()
    app = AudioTextCollector(root)
    root.mainloop()
