#!/usr/bin/env python3
"""
Serial Terminal for USB devices
Works with Python 3.14+ on macOS

Dependencies:
    pip install pyserial

On macOS with Python 3.14+, tkinter is included by default.
"""

from __future__ import annotations

import sys
import json
import os
from datetime import datetime
from typing import Optional, Callable, Any

# Check Python version
if sys.version_info < (3, 8):
    print("Error: Python 3.8+ required", file=sys.stderr)
    sys.exit(1)

# Check tkinter availability
try:
    import tkinter as tk
    from tkinter import ttk, simpledialog, filedialog, messagebox
except ImportError as e:
    print(f"Error: tkinter not available: {e}", file=sys.stderr)
    print("\nTo fix this:", file=sys.stderr)
    print("  Option 1: Use system Python: /usr/bin/python3 my_term.py", file=sys.stderr)
    print("  Option 2: Install tcl-tk and reinstall Python:", file=sys.stderr)
    print("    brew install tcl-tk", file=sys.stderr)
    print("    PYTHON_CONFIGURE_OPTS=\"--with-tcltk-includes='-I$(brew --prefix tcl-tk)/include' --with-tcltk-libs='-L$(brew --prefix tcl-tk)/lib'\" pyenv install 3.14.0", file=sys.stderr)
    sys.exit(1)

# Check pyserial availability
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("Error: pyserial not installed", file=sys.stderr)
    print("\nInstall with: pip install pyserial", file=sys.stderr)
    sys.exit(1)


# Constants
LINES_COUNT = 40
PROFILE_DIR = "profiles"
DEFAULT_PROFILE = os.path.join(PROFILE_DIR, "profile_usb_st.json")

# Create profiles directory
os.makedirs(PROFILE_DIR, exist_ok=True)

# Themes
THEMES = {
    "dark": {"bg": "#111", "fg": "#00FFAA"},
    "amber": {"bg": "#1b1200", "fg": "#FFB000"},
    "blue": {"bg": "#0b1320", "fg": "#7FDBFF"},
    "white_on_black": {"bg": "#000", "fg": "#FFF"},
    "white_on_blue": {"bg": "#002b55", "fg": "#FFF"},
}


class SerialBackend:
    """Handles serial communication with a USB device."""
    
    def __init__(
        self,
        cfg: dict[str, Any],
        rx_callback: Callable[[bytes], None],
        status_callback: Callable[[str], None],
        root: tk.Tk
    ) -> None:
        self.cfg = cfg
        self.rx_callback = rx_callback
        self.status_callback = status_callback
        self.root = root
        self.running = True
        self.virtual = cfg["port"] == "VIRTUAL"
        self.ser: Optional[serial.Serial] = None
        self.after_id: Optional[str] = None
        
        self.auto_reconnect = cfg.get("auto_reconnect", True)
        self.reconnect_delay = cfg.get("reconnect_delay", 2000)
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = cfg.get("max_reconnect_attempts", 5)
        
        if not self.virtual:
            try:
                self.ser = serial.Serial(
                    cfg["port"],
                    cfg["baud"],
                    timeout=0.05
                )
                self.status_callback("connected")
            except Exception as e:
                self.status_callback(f"error: {e}")
                self.virtual = True
        
        self._poll()
    
    def _poll(self) -> None:
        """Poll serial port for incoming data."""
        if not self.running:
            return
        
        if self.virtual or not self.ser or not self.ser.is_open:
            if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.status_callback(f"reconnecting... ({self.reconnect_attempts}/{self.max_reconnect_attempts})")
                self._try_reconnect()
                self.after_id = self.root.after(self.reconnect_delay, self._poll)
            else:
                self.after_id = self.root.after(50, self._poll)
            return
        
        try:
            if self.ser.in_waiting:
                data = self.ser.read(self.ser.in_waiting)
                if data:
                    self.rx_callback(data)
        except Exception as e:
            self.status_callback(f"disconnected: {e}")
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.ser = None
            self.after_id = self.root.after(100, self._poll)
            return
        
        self.reconnect_attempts = 0
        self.after_id = self.root.after(10, self._poll)
        
    def _try_reconnect(self) -> None:
        """Attempt to reconnect to serial port."""
        try:
            if not self.virtual:
                self.ser = serial.Serial(
                    self.cfg["port"],
                    self.cfg["baud"],
                    timeout=0.05
                )
                self.reconnect_attempts = 0
                self.status_callback("reconnected")
        except Exception as e:
            self.status_callback(f"reconnect failed: {e}")
    
    def write(self, data: bytes) -> None:
        """Write data to serial port."""
        if self.virtual or not self.ser or not self.ser.is_open:
            self.rx_callback(b"[echo] " + data)
            return
        
        try:
            self.ser.write(data)
        except Exception:
            self.status_callback("write failed")
    
    def close(self) -> None:
        """Close serial connection and cleanup."""
        self.running = False
        
        if self.after_id:
            try:
                self.root.after_cancel(self.after_id)
            except Exception:
                pass
        
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass


class App:
    """Main application class for the Serial Terminal."""
    
    def __init__(self, root: tk.Tk, cfg: dict[str, Any]) -> None:
        self.root = root
        self.cfg = cfg
        self.log_buffer: list[str] = []
        self.last_cmd = ""
        self.repeat_after: Optional[str] = None
        self.help_shown = False
        self.font_size = 7
        self.eol_mode = cfg.get("eol_mode", "none")
        
        self.seq_pattern = cfg.get("seq_pattern", "Complete")
        self.seq_delay = cfg.get("seq_delay", 0.3)  # Delay after Complete, 0.2-1.0 sec
        self.seq_timeout = cfg.get("seq_timeout", 10)  # Timeout after Start, 10 sec
        self.line_counter = 0
        
        # Execution engine
        self.exec_mode: Optional[str] = None  # 'seq', 'repeat', 'range', 'selected'
        self.last_executed_real_idx = None  # Real index of last executed command (for 'selected' mode)
        self.exec_state = "IDLE"  # 'IDLE', 'WAIT_START', 'WAIT_COMPLETE'
        self.exec_timeout_id: Optional[str] = None
        self.exec_start_time: Optional[datetime] = None
        self.repeat_current = 0
        self.seq_current = 0
        self.seq_end = 0
        self.command_status = {}  # Store status for each command: ✓ success, ✗ failed
        self.selected_commands = set()  # Store indices of selected commands for Run Selected
        
        # Stats
        self.stats = {
            "total_sent": 0,
            "success": 0,
            "failed": 0,
            "cmd_times": []
        }
        self.last_cmd_time = None
        
        self.backend = SerialBackend(cfg, self.on_rx, self.set_status, root)
        
        self.build_ui()
        self.apply_theme()
        # Load window geometry settings
        self._load_window_settings()
        self.bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
    
    def build_ui(self) -> None:
        """Build the user interface."""
        from datetime import datetime
        working_dir = os.getcwd()
        creation_date = "2026-04-21"
        port_info = self.cfg.get('port', 'VIRTUAL')
        title = f"Serial IDE v08 ({creation_date}) | Port: {port_info} | Dir: {working_dir}"
        self.root.title(title)
        self.root.geometry("1200x720")
        
        # Menu bar
        menubar = tk.Menu(self.root)
        
        # Profile menu
        prof = tk.Menu(menubar, tearoff=0)
        prof.add_command(label="Save profile", command=self.save_profile)
        prof.add_command(label="Load profile", command=self.load_profile)
        menubar.add_cascade(label="Profile", menu=prof)
        
        # Theme menu
        theme_menu = tk.Menu(menubar, tearoff=0)
        for t in THEMES:
            theme_menu.add_command(
                label=t,
                command=lambda name=t: self.set_theme(name)
            )
        menubar.add_cascade(label="Theme", menu=theme_menu)
        
        # Other menus
        menubar.add_command(label="Port settings", command=self.port_settings)
        menubar.add_command(label="Save log", command=self.save_log_manual)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Search log (Ctrl+F)", command=self.search_log)
        tools_menu.add_command(label="Command statistics", command=self.show_statistics)
        tools_menu.add_command(label="Export filtered log", command=self.export_filtered_log)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # EOL mode menu
        eol_menu = tk.Menu(menubar, tearoff=0)
        eol_menu.add_command(label="No EOL", command=lambda: self.set_eol("none"))
        eol_menu.add_command(label="Add \\n", command=lambda: self.set_eol("add_n"))
        eol_menu.add_command(label="Add \\r\\n", command=lambda: self.set_eol("add_rn"))
        menubar.add_cascade(label="EOL Mode", menu=eol_menu)
        
        self.root.config(menu=menubar)
        
        # Main paned window
        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)
        
        # Left panel (log + controls)
        left = ttk.Frame(paned)
        paned.add(left, weight=3)
        
        # Log text area
        self.log = tk.Text(left, font=("Menlo", self.font_size))
        self.log.pack(fill="both", expand=True)
        
        # Status bar
        self.status = ttk.Label(left, text="Port: —", foreground="gray")
        self.status.pack(fill="x")
        
        # HEX display
        self.hex_label = ttk.Label(left, text="HEX:", cursor="hand2")
        self.hex_label.pack(fill="x")
        self.hex_label.bind("<Button-1>", self.copy_hex)
        
        # Command entry area
        bottom = ttk.Frame(left)
        bottom.pack(fill="x", pady=4)
        
        self.entry = ttk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send)
        
        ttk.Button(bottom, text="Send", command=self.send).pack(side="left", padx=4)
        
        # Repeat controls
        ttk.Label(bottom, text="Repeat every").pack(side="left")
        self.repeat_sec = tk.DoubleVar(value=1.0)
        ttk.Entry(bottom, textvariable=self.repeat_sec, width=6).pack(side="left")
        ttk.Label(bottom, text="s ×").pack(side="left")
        self.repeat_cnt = tk.IntVar(value=0)
        ttk.Entry(bottom, textvariable=self.repeat_cnt, width=6).pack(side="left")
        self.btn_repeat = ttk.Button(
            bottom,
            text="Start repeat",
            command=self.toggle_repeat
        )
        self.btn_repeat.pack(side="left", padx=8)
        
        # Virtual port simulation
        if self.cfg["port"] == "VIRTUAL":
            sim = ttk.Frame(left)
            sim.pack(fill="x")
            self.sim_entry = ttk.Entry(sim)
            self.sim_entry.pack(side="left", fill="x", expand=True)
            self.sim_entry.bind("<Return>", self.inject)
            ttk.Button(sim, text="Inject", command=self.inject).pack(side="left")
        
        self.commands = self.cfg.get("commands", [""] * LINES_COUNT)

        # Right panel (command list)
        right = ttk.Frame(paned, width=300)
        paned.add(right, weight=1)
        
        # Add sequential execution controls
        seq_frame = ttk.LabelFrame(right, text="Sequential Execution")
        seq_frame.pack(fill="x", pady=4, padx=4)
        
        # Pattern settings
        pattern_frame = ttk.Frame(seq_frame)
        pattern_frame.pack(fill="x", pady=2)
        ttk.Label(pattern_frame, text="Completion pattern:").pack(side="left")
        self.seq_pattern_entry = ttk.Entry(pattern_frame)
        self.seq_pattern_entry.insert(0, self.seq_pattern)
        self.seq_pattern_entry.pack(side="left", fill="x", expand=True)

        # Timing settings
        timing_frame = ttk.Frame(seq_frame)
        timing_frame.pack(fill="x", pady=2)
        
        ttk.Label(timing_frame, text="Delay (s):").pack(side="left")
        self.seq_delay_var = tk.DoubleVar(value=self.seq_delay)
        delay_spinbox = ttk.Spinbox(timing_frame, from_=0.2, to=1.0, increment=0.1, textvariable=self.seq_delay_var, width=6)
        delay_spinbox.pack(side="left")
        ttk.Label(timing_frame, text="(0.2-1.0)").pack(side="left")
        
        ttk.Label(timing_frame, text="Timeout (s):").pack(side="left", padx=(10, 0))
        self.seq_timeout_var = tk.IntVar(value=self.seq_timeout)
        timeout_spinbox = ttk.Spinbox(timing_frame, from_=5, to=60, increment=5, textvariable=self.seq_timeout_var, width=6)
        timeout_spinbox.pack(side="left")
        ttk.Label(timing_frame, text="(5-60)").pack(side="left")

        # Control buttons
        btn_frame = ttk.Frame(seq_frame)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="▶ Start", command=self.seq_start).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="■ Stop", command=self.seq_stop).pack(side="left", padx=2)

        # Status label
        self.seq_status = ttk.Label(seq_frame, text=f"Ready: {len(self.commands)} commands")
        self.seq_status.pack(anchor="w")
        
        # Add range controls to right panel
        range_frame = ttk.LabelFrame(right, text="Test Range")
        range_frame.pack(fill="x", pady=4, padx=4)

        ttk.Label(range_frame, text="From line:").grid(row=0, column=0, sticky="w")
        self.range_from = tk.IntVar(value=1)
        ttk.Spinbox(range_frame, from_=1, to=LINES_COUNT, textvariable=self.range_from, width=8).grid(row=0, column=1)

        ttk.Label(range_frame, text="To line:").grid(row=1, column=0, sticky="w")
        self.range_to = tk.IntVar(value=LINES_COUNT)
        ttk.Spinbox(range_frame, from_=1, to=LINES_COUNT, textvariable=self.range_to, width=8).grid(row=1, column=1)

        ttk.Button(range_frame, text="Run Range", command=self.run_range).grid(row=2, column=0, columnspan=2, pady=5)
        
        # Run Selected frame
        selected_frame = ttk.LabelFrame(right, text="Run Selected")
        selected_frame.pack(fill="x", pady=4, padx=4)
        ttk.Button(selected_frame, text="Run Selected Commands", command=self.run_selected).pack(fill="x", padx=5, pady=5)
        
        self.listbox = ttk.Treeview(right, columns=("Select", "#", "Command", "Status"), show="headings", height=20)
        self.listbox.heading("Select", text="Select")
        self.listbox.heading("#", text="#")
        self.listbox.heading("Command", text="Command")
        self.listbox.heading("Status", text="Status")
        self.listbox.column("Select", width=60, anchor="center")
        self.listbox.column("#", width=40, anchor="center")
        self.listbox.column("Command", width=280)
        self.listbox.column("Status", width=60, anchor="center")
        self.listbox.pack(fill="both", expand=True)
        
        for i, cmd in enumerate(self.commands):
            selected = "[✓]" if i in self.selected_commands else "[ ]"
            self.listbox.insert("", "end", iid=str(i), values=(selected, i+1, cmd, ""))
        
        self.listbox.bind("<Button-1>", self.on_list_click)
        self.listbox.bind("<Double-Button-1>", self.edit_cmd)
        
        # Create context menu for right-click
        # Create context menu for right-click
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Toggle Selection", command=self.toggle_selection)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Edit Command", command=self.edit_selected)
        self.context_menu.add_command(label="Add New Command", command=self.add_new_command)
        self.context_menu.add_command(label="Insert Before", command=self.insert_before)
        self.context_menu.add_command(label="Insert After", command=self.insert_after)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Delete Command", command=self.delete_selected)
        
        # Bind right-click to show context menu
        self.listbox.bind("<Button-3>", self.show_context_menu)
        
        # macOS also uses Button-2 for right-click on some systems
        self.listbox.bind("<Button-2>", self.show_context_menu)
    def set_eol(self, mode: str) -> None:
        """Set end-of-line mode."""
        self.eol_mode = mode
        self.cfg["eol_mode"] = mode
    
    def set_status(self, msg: str) -> None:
        """Update status bar."""
        color = "lime" if "connected" in msg else "red"
        self.root.after(
            0,
            lambda: self.status.config(text=f"Port: {msg}", foreground=color)
        )
    
    def bind_keys(self) -> None:
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-x>", lambda e: self.quit())
        self.root.bind("<Control-b>", lambda e: self.clear())
        self.root.bind("<Control-c>", lambda e: self.copy_selected())
        self.root.bind("<Control-s>", lambda e: self.save_log_auto())
        self.root.bind("<Control-p>", lambda e: self.save_profile_default())
        self.root.bind("<Control-f>", lambda e: self.search_log())
        self.root.bind("<Control-h>", lambda e: self.show_help())
        self.root.bind("<Escape>", lambda e: self.hide_help())
        self.root.bind("<Control-equal>", lambda e: self.font_zoom(1))
        self.root.bind("<Control-minus>", lambda e: self.font_zoom(-1))
        self.root.bind("<Control-Alt-m>", lambda e: self.toggle_day_night())
        self.root.bind("<Control-Alt-s>", lambda e: self.show_settings())
        self.root.bind("<Control-Alt-r>", lambda e: self.seq_start())
        self.root.bind("<Control-Alt-x>", lambda e: self.seq_stop())

    def toggle_day_night(self) -> None:
        """Toggle between day and night themes."""
        current = self.cfg.get("theme", "dark")
        if current in ["dark", "amber", "blue"]:
            self.set_theme("white_on_black")
            self.set_status("theme: day mode")
        else:
            self.set_theme("dark")
            self.set_status("theme: night mode")

    def show_settings(self) -> None:
        """Show unified settings dialog."""
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Terminal Settings")
        settings_win.geometry("500x400")

        # Create notebook for tabbed interface
        notebook = ttk.Notebook(settings_win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Display tab
        display_frame = ttk.Frame(notebook)
        notebook.add(display_frame, text="Display")

        ttk.Label(display_frame, text="Font Size:").grid(row=0, column=0, sticky="w", pady=5)
        font_size_var = tk.IntVar(value=self.font_size)
        ttk.Spinbox(display_frame, from_=6, to=24, textvariable=font_size_var, width=10).grid(row=0, column=1, sticky="w")

        ttk.Label(display_frame, text="Theme:").grid(row=1, column=0, sticky="w", pady=5)
        theme_var = tk.StringVar(value=self.cfg.get("theme", "dark"))
        theme_combo = ttk.Combobox(display_frame, textvariable=theme_var, values=list(THEMES.keys()), state="readonly")
        theme_combo.grid(row=1, column=1, sticky="w")

        # Log options tab
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Logging")

        filter_empty_var = tk.BooleanVar(value=self.cfg.get("filter_empty_lines", True))
        ttk.Checkbutton(log_frame, text="Filter empty lines", variable=filter_empty_var).grid(row=0, column=0, sticky="w", pady=5)

        normalize_var = tk.BooleanVar(value=self.cfg.get("normalize_line_endings", True))
        ttk.Checkbutton(log_frame, text="Normalize line endings (\\r\\n → \\n)", variable=normalize_var).grid(row=1, column=0, sticky="w", pady=5)

        show_line_num_var = tk.BooleanVar(value=self.cfg.get("show_line_numbers", False))
        ttk.Checkbutton(log_frame, text="Show line numbers", variable=show_line_num_var).grid(row=2, column=0, sticky="w", pady=5)

        show_ts_var = tk.BooleanVar(value=self.cfg.get("show_timestamps", False))
        ttk.Checkbutton(log_frame, text="Show timestamps", variable=show_ts_var).grid(row=3, column=0, sticky="w", pady=5)

        # Connection tab
        conn_frame = ttk.Frame(notebook)
        notebook.add(conn_frame, text="Connection")

        reconnect_var = tk.BooleanVar(value=self.backend.auto_reconnect if hasattr(self.backend, 'auto_reconnect') else True)
        ttk.Checkbutton(conn_frame, text="Auto-reconnect on disconnect", variable=reconnect_var).grid(row=0, column=0, sticky="w", pady=5)

        # Buttons
        btn_frame = ttk.Frame(settings_win)
        btn_frame.pack(fill="x", padx=10, pady=10)

        def apply_settings() -> None:
            # Apply all settings
            self.font_size = font_size_var.get()
            self.log.config(font=("Menlo", self.font_size))

            self.cfg["theme"] = theme_var.get()
            self.apply_theme()

            self.cfg["filter_empty_lines"] = filter_empty_var.get()
            self.cfg["normalize_line_endings"] = normalize_var.get()
            self.cfg["show_line_numbers"] = show_line_num_var.get()
            self.cfg["show_timestamps"] = show_ts_var.get()

            if hasattr(self.backend, 'auto_reconnect'):
                self.backend.auto_reconnect = reconnect_var.get()

            self.save_profile_default()
            settings_win.destroy()

        ttk.Button(btn_frame, text="Apply", command=apply_settings).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=settings_win.destroy).pack(side="right")
    
    def font_zoom(self, delta: int) -> None:
        """Change font size."""
        self.font_size += delta
        if self.font_size < 6:
            self.font_size = 6
        self.log.config(font=("Menlo", self.font_size))
    
    def copy_selected(self) -> None:
        """Copy selected text to clipboard."""
        try:
            sel = self.log.selection_get()
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
        except Exception:
            pass
    
    def quit(self) -> None:
        """Quit application."""
        self._save_window_settings()
        self.backend.close()
        self.root.quit()
        self.root.destroy()
    def clear(self) -> None:
        """Clear log buffer."""
        self.log.delete("1.0", "end")
        self.log_buffer.clear()
        self.hex_label.config(text="HEX:")
        self.line_counter = 0
    
    def _prepare_log_content(self) -> str:
        """Prepare log content for saving with normalization."""
        content = "".join(self.log_buffer)

        # Normalize line endings
        if self.cfg.get("normalize_line_endings", True):
            content = content.replace('\r\n', '\n').replace('\r', '\n')

        # Optionally add metadata header
        if self.cfg.get("add_log_header", True):
            header = f"# Serial Terminal Log\n# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            header += f"# Port: {self.cfg.get('port', 'N/A')}\n"
            header += f"# Lines: {len(self.log_buffer)}\n#\n"
            content = header + content

        return content

    def save_log_auto(self) -> None:
        """Save log with auto-generated filename."""
        line_count = len(self.log_buffer)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fn = f"{timestamp}-{line_count}-lines-term.log.txt"
        
        content = self._prepare_log_content()
        try:
            with open(fn, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update()
            self.set_status(f"saved: {fn}")
        except Exception as e:
            self.set_status(f"save failed: {e}")
    
    def save_profile_default(self) -> None:
        """Save default profile."""
        self.cfg["commands"] = self.commands
        self.cfg["repeat_sec"] = self.repeat_sec.get()
        self.cfg["repeat_cnt"] = self.repeat_cnt.get()
        self.cfg["font_size"] = self.font_size
        self.cfg["eol_mode"] = self.eol_mode
        # cmd_history is already updated in self.cfg in send()
        try:
            with open(DEFAULT_PROFILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def show_help(self) -> None:
        """Show help text."""
        if self.help_shown:
            return
        
        self.log.delete("1.0", "end")
        text = """Ctrl+X  Quit
Ctrl+B  Clear
Ctrl+C  Copy selected text
Ctrl+S  Save log (auto name) + copy to clipboard
Ctrl+P  Save profile default
Ctrl+F  Search log
Ctrl+H  This help
Esc     Back to log
Ctrl+=  Zoom in font
Ctrl+-  Zoom out font
Ctrl+Alt+M Toggle Theme
Ctrl+Alt+S Settings
Ctrl+Alt+R Start Sequence
Ctrl+Alt+X Stop Sequence

Click line → send + copy to entry
Double click → edit
Click HEX → copy to clipboard"""
        self.log.insert("end", text)
        self.help_shown = True
    
    def hide_help(self) -> None:
        """Hide help and restore log."""
        if not self.help_shown:
            return
        
        self.log.delete("1.0", "end")
        for line in self.log_buffer:
            self.log.insert("end", line)
        self.log.see("end")
        self.help_shown = False
    
    def on_rx(self, data: bytes) -> None:
        """Handle received data."""
        if self.help_shown:
            return
        
        # Normalize line endings
        txt = data.decode(errors="ignore")
        if self.cfg.get("normalize_line_endings", True):
            txt = txt.replace('\r\n', '\n').replace('\r', '\n')
        txt = txt.rstrip('\n')
        
        # Skip empty lines (configurable)
        if self.cfg.get("filter_empty_lines", True):
            if not txt.strip():
                return
        
        self.line_counter += 1
        
        # Build display line
        display_parts = []
        if self.cfg.get("show_line_numbers", False):
            display_parts.append(f"{self.line_counter:5d}>")
            
        if self.cfg.get("show_timestamps", False):
            ts = datetime.now().strftime(self.cfg.get("timestamp_format", "%H:%M:%S"))
            display_parts.append(f"[{ts}]")
            
        display_parts.append(txt)
        display_line = " ".join(display_parts)
        
        self.log_buffer.append(display_line + '\n')
        self.log.insert("end", display_line + '\n')
        self.log.see("end")
        
        hx = " ".join(f"{b:02X}" for b in data)
        self.hex_label.config(text=f"HEX: {hx}")
        
        # Execution engine: check for Start and Complete patterns
        if self.exec_mode is not None and txt.strip():
            txt_lower = txt.lower()
            
            # Check for "Start" pattern - command execution started
            if "start" in txt_lower and self.exec_state == 'WAIT_START':
                self._handle_start()
            
            # Check for completion pattern (e.g., "Complete")
            pattern_lower = self.seq_pattern.lower()
            if pattern_lower in txt_lower and self.exec_state == 'WAIT_COMPLETE':
                self._handle_complete()
    
    def send(self, event: Optional[tk.Event] = None) -> None:
        """Send command."""
        txt = self.entry.get().strip()
        if not txt:
            return
        
        self.last_cmd = txt
        self.stats["total_sent"] += 1
        self.last_cmd_time = datetime.now()
        
        self.backend.write((txt + "\r").encode())
        line = f">> {txt}\n"
        self.log_buffer.append(line)
        self.log.insert("end", line)
        self.log.see("end")
        
        # Command history persistence
        if "cmd_history" not in self.cfg:
            self.cfg["cmd_history"] = []
        if txt not in self.cfg["cmd_history"]:
            self.cfg["cmd_history"].append(txt)
    
    def _send_next_command(self) -> None:
        """Send next command in sequence."""
        if not self.seq_running:
            return

        end_limit = getattr(self, "seq_end", len(self.commands))

        # Find next non-empty command
        while self.seq_current < end_limit:
            cmd = self.commands[self.seq_current].strip()
            self.seq_current += 1

            if cmd:
                self.entry.delete(0, "end")
                self.entry.insert(0, cmd)
                self.send()
                self.seq_status.config(text=f"Current: {self.seq_current}/{end_limit}")
                return

        # All commands sent
        self.seq_running = False
        self.seq_status.config(text="Sequence complete")
        self.set_status("sequence complete")

    def seq_start(self) -> None:
        """Start sequential command execution."""
        self.seq_pattern = self.seq_pattern_entry.get().strip()
        if not self.seq_pattern:
            messagebox.showwarning("Pattern Required", "Please enter a completion pattern")
            return

        # Load timing settings from UI
        self.seq_delay = self.seq_delay_var.get()
        self.seq_timeout = self.seq_timeout_var.get()

        # Initialize execution
        self.exec_mode = 'seq'
        self.exec_state = 'WAIT_START'
        self.seq_current = 0
        self.seq_end = len(self.commands)
        self.seq_status.config(text="Starting sequence...")
        self._exec_next()

    def seq_stop(self) -> None:
        """Stop sequential command execution."""
        self._stop_execution()

    def _stop_execution(self) -> None:
        """Stop any running execution."""
        self.exec_mode = None
        self.exec_state = 'IDLE'
        if self.exec_timeout_id:
            try:
                self.root.after_cancel(self.exec_timeout_id)
            except Exception:
                pass
            self.exec_timeout_id = None
        self.seq_status.config(text="Execution stopped")
        self.set_status("execution stopped")



    def _update_command_status(self, cmd_index: int, status: str) -> None:
        """Update status for a specific command in the list.
        
        Args:
            cmd_index: Zero-based command index
            status: Status icon - '✓' for success, '✗' for failure, '' for clear
        """
        self.command_status[cmd_index] = status
        try:
            if status == '✓':
                self.listbox.item(str(cmd_index), values=(cmd_index+1, self.commands[cmd_index], status), tags=('success',))
                self.listbox.tag_configure('success', foreground='green')
            elif status == '✗':
                self.listbox.item(str(cmd_index), values=(cmd_index+1, self.commands[cmd_index], status), tags=('failed',))
                self.listbox.tag_configure('failed', foreground='red')
            else:
                self.listbox.item(str(cmd_index), values=(cmd_index+1, self.commands[cmd_index], status))
        except Exception:
            pass  # Item might not exist in listbox

    def _clear_all_statuses(self) -> None:
        """Clear all command statuses."""
        self.command_status.clear()
        for i in range(len(self.commands)):
            try:
                self.listbox.item(str(i), values=(i+1, self.commands[i], ""))
            except Exception:
                pass
    def _exec_next(self) -> None:
        """Execute next command based on current mode."""
        if self.exec_mode is None or self.exec_state == 'IDLE':
            return

        cmd = None
        
        # Find next command based on mode
        if self.exec_mode in ['seq', 'range', 'selected']:
            # Sequential, range, or selected mode
            if self.exec_mode == 'selected':
                # Get actual command index from selected list
                while self.seq_current < self.seq_end:
                    real_idx = self.seq_selected_indices[self.seq_current]
                    cmd = self.commands[real_idx].strip()
                    self.seq_current += 1
                    if cmd:
                        self.last_executed_real_idx = real_idx  # Save for status updates
                        break
                else:
                    # No more selected commands
                    self._stop_execution()
                    self.seq_status.config(text="Selected commands complete")
                    self.set_status("selected commands complete")
                    # Auto-save log for selected mode
                    self.save_log_auto()
                    self.log.insert("end", "\n📁 Log auto-saved after selected completion\n")
                    return
            else:
                # Original seq or range mode
                while self.seq_current < self.seq_end:
                    cmd = self.commands[self.seq_current].strip()
                    self.seq_current += 1
                    if cmd:
                        break
                else:
                    # No more commands
                    self._stop_execution()
                    self.seq_status.config(text="Sequence complete")
                    self.set_status("sequence complete")
                    # Auto-save log for range mode
                    if self.exec_mode == 'range':
                        self.save_log_auto()
                        self.log.insert("end", "\n📁 Log auto-saved after range completion\n")
                    return
        
        elif self.exec_mode == 'repeat':
            # Repeat mode
            repeat_limit = self.repeat_cnt.get()
            if repeat_limit > 0 and self.repeat_current >= repeat_limit:
                self._stop_execution()
                self.seq_status.config(text="Repeat complete")
                self.set_status("repeat complete")
                return
            
            cmd = self.last_cmd.strip()
            self.repeat_current += 1
            
        if not cmd:
            self._stop_execution()
            return

        # Send command
        # Send command
        self.entry.delete(0, "end")
        self.entry.insert(0, cmd)
        self.backend.write((cmd + "\r").encode())
        line = f">> {cmd}\n"
        self.log_buffer.append(line)
        self.log.insert("end", line)
        self.log.see("end")

        # Update stats
        self.stats["total_sent"] += 1
        self.last_cmd_time = datetime.now()

        # Update status
        if self.exec_mode == 'seq':
            self.seq_status.config(text=f"Current: {self.seq_current}/{self.seq_end}")
        elif self.exec_mode == 'range':
            self.seq_status.config(text=f"Current: {self.seq_current}/{self.seq_end}")
        elif self.exec_mode == 'repeat':
            repeat_limit = self.repeat_cnt.get()
            if repeat_limit > 0:
                self.seq_status.config(text=f"Repeat: {self.repeat_current}/{repeat_limit}")
            else:
                self.seq_status.config(text=f"Repeat: {self.repeat_current} (infinite)")

        # Set state and start timeout
        self.exec_state = 'WAIT_COMPLETE'
        self._start_timeout()

    def _start_timeout(self) -> None:
        """Start timeout timer for command completion."""
        # Cancel existing timeout if any
        if self.exec_timeout_id:
            try:
                self.root.after_cancel(self.exec_timeout_id)
            except Exception:
                pass

        # Start new timeout (in milliseconds)
        timeout_ms = self.seq_timeout * 1000
        self.exec_timeout_id = self.root.after(timeout_ms, self._handle_timeout)

    def _handle_timeout(self) -> None:
        """Handle timeout - command didn't complete in time."""
        if self.exec_mode is None:
            return

        self.stats["failed"] += 1
        # Get command index for status update
        if self.exec_mode == 'selected' and self.last_executed_real_idx is not None:
            cmd_index = self.last_executed_real_idx
            cmd_num = cmd_index + 1
        else:
            cmd_num = getattr(self, 'seq_current', '?')
            cmd_index = cmd_num - 1  # Convert to 0-based index
        log_msg = f"⚠️ TIMEOUT: Command #{cmd_num} - no 'Complete' within {self.seq_timeout}s, proceeding to next\n"
        self.log.insert("end", log_msg)
        self.log.see("end")
        # Update status in Treeview with red X
        self._update_command_status(cmd_index, '✗')

        # Move to next command despite timeout
        if self.exec_mode in ['seq', 'range', 'selected']:
            self.root.after(int(self.seq_delay * 1000), self._exec_next)
        elif self.exec_mode == 'repeat':
            self.root.after(int(self.seq_delay * 1000), self._exec_next)

    def _handle_complete(self) -> None:
        """Handle 'Complete' received - command finished successfully."""
        if self.exec_mode is None:
            return

        # Log successful completion
        if self.last_cmd_time:
            delta = (datetime.now() - self.last_cmd_time).total_seconds()
            # Get command index for status update
            if self.exec_mode == 'selected' and self.last_executed_real_idx is not None:
                cmd_index = self.last_executed_real_idx
                cmd_num = cmd_index + 1
            else:
                cmd_num = getattr(self, 'seq_current', '?')
                cmd_index = cmd_num - 1  # Convert to 0-based index
            log_msg = f"✓ SUCCESS: Command #{cmd_num} completed in {delta:.2f}s\n"
            self.log.insert("end", log_msg)
            self.log.see("end")
            # Update status in Treeview with green checkmark
            self._update_command_status(cmd_index, '✓')
        if self.exec_timeout_id:
            try:
                self.root.after_cancel(self.exec_timeout_id)
            except Exception:
                pass
            self.exec_timeout_id = None

        self.stats["success"] += 1
        
        # Record command time if we have start time
        if self.last_cmd_time:
            delta = (datetime.now() - self.last_cmd_time).total_seconds()
            self.stats["cmd_times"].append(delta)

        # Wait for configured delay, then send next command
        delay_ms = int(self.seq_delay * 1000)
        self.root.after(delay_ms, self._exec_next)

    def _handle_start(self) -> None:
        """Handle 'Start' received - command execution started."""
        # This is mainly for logging purposes, actual timeout was started when command was sent
        self.set_status("Command started...")
    def run_range(self) -> None:
        """Run commands from specified line range."""
        start = self.range_from.get() - 1  # Convert to 0-based
        end = self.range_to.get()

        if start < 0 or end > len(self.commands) or start >= end:
            messagebox.showerror("Range Error", f"Invalid range: {start+1} to {end}")
            return

        self.seq_pattern = self.seq_pattern_entry.get().strip()
        if not self.seq_pattern:
            messagebox.showwarning("Pattern Required", "Please enter a completion pattern")
            return

        # Load timing settings from UI
        self.seq_delay = self.seq_delay_var.get()
        self.seq_timeout = self.seq_timeout_var.get()

        # Clear log and initialize range execution
        self.clear()
        self.line_counter = 0

        # Initialize execution for range mode
        self.exec_mode = 'range'
        self.exec_state = 'WAIT_START'
        self.seq_current = start
        self.seq_end = end
        self.seq_status.config(text=f"Running range: {start+1} to {end}")
        self.set_status(f"Running range: {start+1} to {end}")
        self._exec_next()
    def run_selected(self) -> None:
        """Run only selected commands."""
        if not self.selected_commands:
            messagebox.showwarning("No Selection", "Please select commands by clicking the Select column")
            return
        
        self.seq_pattern = self.seq_pattern_entry.get().strip()
        if not self.seq_pattern:
            messagebox.showwarning("Pattern Required", "Please enter a completion pattern")
            return
        
        # Load timing settings from UI
        self.seq_delay = self.seq_delay_var.get()
        self.seq_timeout = self.seq_timeout_var.get()
        
        # Get sorted list of selected indices
        self.seq_selected_indices = sorted(self.selected_commands)
        
        # Clear log and initialize selected execution
        self.clear()
        self.line_counter = 0
        
        # Initialize execution for selected mode
        self.exec_mode = 'selected'
        self.exec_state = 'WAIT_START'
        self.seq_current = 0  # Index in seq_selected_indices
        self.seq_end = len(self.seq_selected_indices)
        first_idx = self.seq_selected_indices[0] + 1
        last_idx = self.seq_selected_indices[-1] + 1
        self.seq_status.config(text=f"Running selected: {len(self.seq_selected_indices)} commands ({first_idx}-{last_idx})")
        self.set_status(f"Running selected commands: {len(self.seq_selected_indices)} total")
        self._exec_next()


    def show_statistics(self) -> None:
        """Show command execution statistics."""
        win = tk.Toplevel(self.root)
        win.title("Command Statistics")
        win.geometry("300x200")
        
        ttk.Label(win, text="Execution Statistics", font=("Helvetica", 14, "bold")).pack(pady=10)
        
        times = self.stats["cmd_times"]
        avg_time = sum(times) / len(times) if times else 0.0
        
        f = ttk.Frame(win)
        f.pack(fill="both", expand=True, padx=20)
        
        ttk.Label(f, text=f"Total Sent:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Label(f, text=str(self.stats["total_sent"])).grid(row=0, column=1, sticky="e")
        
        ttk.Label(f, text=f"Successful:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Label(f, text=str(self.stats["success"])).grid(row=1, column=1, sticky="e")
        
        failed = self.stats["total_sent"] - self.stats["success"]
        ttk.Label(f, text=f"Pending/Failed:").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Label(f, text=str(failed)).grid(row=2, column=1, sticky="e")
        
        ttk.Label(f, text=f"Avg Response Time:").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Label(f, text=f"{avg_time:.2f} s").grid(row=3, column=1, sticky="e")
        
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=10)

    def search_log(self, event: Optional[tk.Event] = None) -> None:
        """Search within log buffer."""
        term = simpledialog.askstring("Search", "Enter text to search:")
        if not term:
            return
            
        self.log.tag_remove("search", "1.0", "end")
        
        count = 0
        idx = "1.0"
        while True:
            idx = self.log.search(term, idx, nocase=True, stopindex="end")
            if not idx:
                break
            lastidx = f"{idx}+{len(term)}c"
            self.log.tag_add("search", idx, lastidx)
            idx = lastidx
            count += 1
            
        self.log.tag_config("search", background="yellow", foreground="black")
        
        if count > 0:
            self.set_status(f"Found {count} matches for '{term}'")
            # See the first match
            first_idx = self.log.search(term, "1.0", nocase=True, stopindex="end")
            if first_idx:
                self.log.see(first_idx)
        else:
            self.set_status(f"No matches found for '{term}'")

    def export_filtered_log(self) -> None:
        """Export log matching a specific filter."""
        term = simpledialog.askstring("Filter Export", "Enter text to filter by:")
        if not term:
            return
            
        f = filedialog.asksaveasfilename(defaultextension=".txt", initialfile=f"filtered_{term}.txt")
        if not f:
            return
            
        filtered_lines = [line for line in self.log_buffer if term.lower() in line.lower()]
        
        try:
            with open(f, "w", encoding="utf-8", newline="\n") as fp:
                fp.write("".join(filtered_lines))
            self.set_status(f"Exported {len(filtered_lines)} lines to {os.path.basename(f)}")
        except Exception as e:
            self.set_status(f"Export failed: {e}")

    def toggle_repeat(self) -> None:
        """Toggle command repeat."""
        if self.exec_mode == 'repeat':
            # Stop repeat
            self._stop_execution()
            self.btn_repeat.config(text="Start repeat")
            return
        
        # Start repeat
        if not self.last_cmd:
            messagebox.showwarning("No Command", "Please send a command first")
            return
        
        # Load timing settings from UI
        self.seq_delay = self.seq_delay_var.get()
        self.seq_timeout = self.seq_timeout_var.get()
        
        # Initialize repeat execution
        self.exec_mode = 'repeat'
        self.exec_state = 'WAIT_START'
        self.repeat_current = 0
        self.btn_repeat.config(text="Stop repeat")
        self.seq_status.config(text="Starting repeat...")
        self._exec_next()

    
    def on_list_click(self, event: tk.Event) -> None:
        """Handle treeview click - toggle checkbox or send command."""
        # Get the item under the cursor
        item_id = self.listbox.identify_row(event.y)
        if not item_id:
            return
        
        # Check which column was clicked
        col_id = self.listbox.identify_column(event.x)
        # Column #0 is 'Select', #1 is '#', #2 is 'Command', #3 is 'Status'
        if col_id == "#0":  # Select column
            try:
                idx = int(item_id)
                if idx in self.selected_commands:
                    self.selected_commands.remove(idx)
                    selected = "[ ]"
                else:
                    self.selected_commands.add(idx)
                    selected = "[✓]"
                # Update the checkbox display
                values = self.listbox.item(item_id, 'values')
                self.listbox.item(item_id, values=(selected, values[1], values[2], values[3]))
            except (ValueError, IndexError):
                pass
            return  # Don't send command when clicking checkbox
        
        # For other columns, send command as before
        try:
            idx = int(item_id)
            txt = self.commands[idx].strip()
            if txt:
                self.entry.delete(0, "end")
                self.entry.insert(0, txt)
                self.last_cmd = txt
                self.stats["total_sent"] += 1
                self.last_cmd_time = datetime.now()
                self.backend.write((txt + "\r").encode())
                line = f">> {txt}\n"
                self.log_buffer.append(line)
                self.log.insert("end", line)
                self.log.see("end")
                
                if "cmd_history" not in self.cfg:
                    self.cfg["cmd_history"] = []
                if txt not in self.cfg["cmd_history"]:
                    self.cfg["cmd_history"].append(txt)
        except (ValueError, IndexError):
            pass
            pass
    def toggle_selection(self) -> None:
        """Toggle selection state of the currently selected command."""
        selection = self.listbox.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command first")
            return
        
        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            return
        
        # Toggle selection state
        if idx in self.selected_commands:
            self.selected_commands.remove(idx)
            selected = "[ ]"
        else:
            self.selected_commands.add(idx)
            selected = "[✓]"
        
        # Update the checkbox display
        values = self.listbox.item(iid, 'values')
        self.listbox.item(iid, values=(selected, values[1], values[2], values[3]))

    def edit_cmd(self, event: tk.Event) -> None:
        """Edit command in Treeview."""
        selection = self.listbox.selection()
        if not selection:
            return
        
        iid = selection[0]  # Treeview uses item IDs (iid)
        try:
            idx = int(iid)
        except ValueError:
            return
        
        old = self.commands[idx]
        new = simpledialog.askstring("Edit Command", f"Edit command {idx+1}:", initialvalue=old)
        if new is not None:
            # Update the command in our list
            self.commands[idx] = new
            # Update the Treeview display
            self.listbox.item(iid, values=(idx+1, new, ""))
    
    def show_context_menu(self, event: tk.Event) -> None:
        """Show context menu on right-click."""
        # Select the item under cursor
        item_id = self.listbox.identify_row(event.y)
        if item_id:
            self.listbox.selection_set(item_id)
        
        # Show context menu at cursor position
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()
    
    def edit_selected(self) -> None:
        """Edit the selected command."""
        selection = self.listbox.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command first")
            return
        
        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            return
        
        old = self.commands[idx]
        new = simpledialog.askstring("Edit Command", f"Edit command {idx+1}:", initialvalue=old)
        if new is not None:
            self.commands[idx] = new
            self.listbox.item(iid, values=(idx+1, new, ""))
            self.save_commands_to_config()
    
    def add_new_command(self) -> None:
        """Add a new command at the end."""
        new_cmd = simpledialog.askstring("Add Command", "Enter new command:")
        if new_cmd is not None:
            idx = len(self.commands)
            self.commands.append(new_cmd)
            self.listbox.insert("", "end", iid=str(idx), values=(idx+1, new_cmd, ""))
            self._update_listbox_numbers()
            self.save_commands_to_config()
    
    def insert_before(self) -> None:
        """Insert a command before the selected one."""
        selection = self.listbox.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command first")
            return
        
        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            return
        
        new_cmd = simpledialog.askstring("Insert Before", "Enter command:")
        if new_cmd is not None:
            self.commands.insert(idx, new_cmd)
            self._rebuild_listbox()
            self.save_commands_to_config()
    
    def insert_after(self) -> None:
        """Insert a command after the selected one."""
        selection = self.listbox.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command first")
            return
        
        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            return
        
        new_cmd = simpledialog.askstring("Insert After", "Enter command:")
        if new_cmd is not None:
            self.commands.insert(idx + 1, new_cmd)
            self._rebuild_listbox()
            self.save_commands_to_config()
    
    def delete_selected(self) -> None:
        """Delete the selected command."""
        selection = self.listbox.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a command first")
            return
        
        iid = selection[0]
        try:
            idx = int(iid)
        except ValueError:
            return
        
        if messagebox.askyesno("Confirm Delete", f"Delete command {idx+1}?"):
            self.commands.pop(idx)
            self.listbox.delete(iid)
            self._update_listbox_numbers()
            self.save_commands_to_config()
    
    def _rebuild_listbox(self) -> None:
        """Rebuild the entire listbox from self.commands."""
        # Clear existing items
        for item in self.listbox.get_children():
            self.listbox.delete(item)
        
        # Re-insert all commands
        for i, cmd in enumerate(self.commands):
            self.listbox.insert("", "end", iid=str(i), values=(i+1, cmd, ""))
    
    def _update_listbox_numbers(self) -> None:
        """Update the line numbers in listbox after insert/delete."""
        for i, cmd in enumerate(self.commands):
            iid = str(i)
            if self.listbox.exists(iid):
                self.listbox.item(iid, values=(i+1, cmd, ""))
            else:
                self.listbox.insert("", "end", iid=iid, values=(i+1, cmd, ""))
    
    def save_commands_to_config(self) -> None:
        """Save commands to configuration."""
        self.cfg["commands"] = self.commands
        self.seq_status.config(text=f"Ready: {len(self.commands)} commands")

    def copy_hex(self, event: tk.Event) -> None:
        """Copy hex data to clipboard."""
        t = self.hex_label.cget("text")
        if t.startswith("HEX: "):
            self.root.clipboard_clear()
            self.root.clipboard_append(t[5:])
    
    def inject(self, event: Optional[tk.Event] = None) -> None:
        """Inject data in virtual mode."""
        if not hasattr(self, "sim_entry"):
            return
        
        txt = self.sim_entry.get().strip()
        if txt:
            self.backend.rx_callback((txt + "\n").encode())
            self.sim_entry.delete(0, "end")
    
    def apply_theme(self) -> None:
        """Apply color theme."""
        t = THEMES.get(self.cfg.get("theme", "dark"), THEMES["dark"])
        self.log.config(bg=t["bg"], fg=t["fg"], insertbackground="white")
        self.log.config(bg=t["bg"], fg=t["fg"], insertbackground="white")

    def _load_window_settings(self) -> None:
        """Load and restore window geometry settings."""
        try:
            geometry = self.cfg.get("window_geometry", "")
            if geometry:
                self.root.geometry(geometry)
                print(f"📐 Restored window geometry: {geometry}")
        except Exception as e:
            print(f"⚠️ Failed to restore window geometry: {e}")

    def _save_window_settings(self) -> None:
        """Save current window geometry settings."""
        try:
            geometry = self.root.geometry()
            self.cfg["window_geometry"] = geometry
            print(f"💾 Saved window geometry: {geometry}")
        except Exception as e:
            print(f"⚠️ Failed to save window geometry: {e}")

    def set_theme(self, name: str) -> None:
        """Set color theme."""
        self.cfg["theme"] = name
    
    def save_profile(self) -> None:
        """Save profile to file."""
        name = simpledialog.askstring("Save", "Profile name:")
        if not name:
            return
        
        data = self.cfg.copy()
        data["commands"] = self.commands
        data["repeat_sec"] = self.repeat_sec.get()
        data["repeat_cnt"] = self.repeat_cnt.get()
        data["font_size"] = self.font_size
        data["eol_mode"] = self.eol_mode
        # cmd_history is already in data because data = self.cfg.copy()
        
        with open(f"{PROFILE_DIR}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_profile(self) -> None:
        """Load profile from file."""
        f = filedialog.askopenfilename(initialdir=PROFILE_DIR)
        if not f:
            return
        
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        
        self.backend.close()
        self.cfg = data
        self.commands = data.get("commands", [""] * LINES_COUNT)
        self.repeat_sec.set(data.get("repeat_sec", 1.0))
        self.repeat_cnt.set(data.get("repeat_cnt", 0))
        self.font_size = data.get("font_size", 7)
        self.eol_mode = data.get("eol_mode", "none")
        self.log.config(font=("Menlo", self.font_size))
        self.log.delete("1.0", "end")
        self.listbox.delete(0, "end")
        for i, c in enumerate(self.commands):
            self.listbox.insert("end", f"{i+1:02d}: {c}")
        self.backend = SerialBackend(self.cfg, self.on_rx, self.set_status, self.root)
        self.apply_theme()
    
    def port_settings(self) -> None:
        """Show port settings info."""
        messagebox.showinfo(
            "Port",
            "Change port → edit profile or restart with new selection"
        )
    
    def save_log_manual(self) -> None:
        """Save log to user-selected file."""
        f = filedialog.asksaveasfilename(defaultextension=".txt")
        if f:
            content = self._prepare_log_content()
            try:
                with open(f, "w", encoding="utf-8", newline="\n") as fp:
                    fp.write(content)
                self.set_status(f"saved: {os.path.basename(f)}")
            except Exception as e:
                self.set_status(f"save failed: {e}")


def select_port() -> Optional[str]:
    """Show port selection dialog."""
    ports = [p.device for p in serial.tools.list_ports.comports()] + ["VIRTUAL"]
    
    win = tk.Tk()
    win.title("Select port")
    lb = tk.Listbox(win, width=50, height=12)
    lb.pack(padx=10, pady=10)
    
    for p in ports:
        lb.insert("end", p)
    
    res: list[Optional[str]] = [None]
    
    def ok() -> None:
        s = lb.curselection()
        if s:
            res[0] = lb.get(s[0])
        win.destroy()
    
    ttk.Button(win, text="Open", command=ok).pack(pady=5)
    win.mainloop()
    return res[0]


def main() -> None:
    """Main entry point."""
    cfg = {
        "port": None, 
        "baud": 115200, 
        "theme": "dark",
        "filter_empty_lines": True,
        "normalize_line_endings": True,
    }
    
    # Load default profile
    if os.path.exists(DEFAULT_PROFILE):
        try:
            with open(DEFAULT_PROFILE, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    
    # Check if configured port exists
    ports = [p.device for p in serial.tools.list_ports.comports()]
    if cfg["port"] not in ports and cfg["port"] != "VIRTUAL":
        p = select_port()
        if not p:
            return
        cfg["port"] = p
    
    # Create and run application
    root = tk.Tk()
    App(root, cfg)
    root.mainloop()


if __name__ == "__main__":
    main()
