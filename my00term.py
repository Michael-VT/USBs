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
        
        self.seq_mode = False
        self.seq_pattern = cfg.get("seq_pattern", "Complete")
        self.seq_running = False
        self.seq_current = 0
        self.seq_after_id = None
        
        self.backend = SerialBackend(cfg, self.on_rx, self.set_status, root)
        
        self.build_ui()
        self.apply_theme()
        self.bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
    
    def build_ui(self) -> None:
        """Build the user interface."""
        self.root.title("Serial IDE")
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
        ttk.Button(
            bottom,
            text="Start repeat",
            command=self.toggle_repeat
        ).pack(side="left", padx=8)
        
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
        seq_frame = ttk.Frame(right)
        seq_frame.pack(fill="x", pady=4, padx=4)
        
        self.seq_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(seq_frame, text="Sequential mode", variable=self.seq_var).pack(anchor="w")
        
        pattern_frame = ttk.Frame(seq_frame)
        pattern_frame.pack(fill="x", pady=2)
        ttk.Label(pattern_frame, text="Wait for:").pack(side="left")
        self.seq_pattern_entry = ttk.Entry(pattern_frame)
        self.seq_pattern_entry.insert(0, self.seq_pattern)
        self.seq_pattern_entry.pack(side="left", fill="x", expand=True)
        
        btn_frame = ttk.Frame(seq_frame)
        btn_frame.pack(fill="x", pady=2)
        ttk.Button(btn_frame, text="Start", command=self.seq_start).pack(side="left")
        ttk.Button(btn_frame, text="Stop", command=self.seq_stop).pack(side="left")
        
        self.seq_status = ttk.Label(seq_frame, text=f"Current: 0/{len(self.commands)}")
        self.seq_status.pack(anchor="w")
        
        self.listbox = tk.Listbox(right)
        self.listbox.pack(fill="both", expand=True)
        
        for cmd in self.commands:
            self.listbox.insert("end", cmd)
        
        self.listbox.bind("<Button-1>", self.on_list_click)
        self.listbox.bind("<Double-Button-1>", self.edit_cmd)
    
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
        self.root.bind("<Control-f>", lambda e: self.save_profile_default())
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
        self.backend.close()
        self.root.quit()
        self.root.destroy()
    
    def clear(self) -> None:
        """Clear log buffer."""
        self.log.delete("1.0", "end")
        self.log_buffer.clear()
        self.hex_label.config(text="HEX:")
    
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
Ctrl+F  Save profile default
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
        
        self.log_buffer.append(txt + '\n')
        self.log.insert("end", txt + '\n')
        self.log.see("end")
        
        hx = " ".join(f"{b:02X}" for b in data)
        self.hex_label.config(text=f"HEX: {hx}")
        
        # Add sequential execution check
        if self.seq_running and self.seq_pattern:
            if self.seq_pattern.lower() in txt.lower():
                # Pattern found, send next command
                self.root.after(500, self._send_next_command)
    
    def send(self, event: Optional[tk.Event] = None) -> None:
        """Send command."""
        txt = self.entry.get().strip()
        if not txt:
            return
        
        self.last_cmd = txt
        self.backend.write((txt + "\r").encode())
        line = f">> {txt}\n"
        self.log_buffer.append(line)
        self.log.insert("end", line)
        self.log.see("end")
        self.entry.delete(0, "end")
    
    def _send_next_command(self) -> None:
        """Send next command in sequence."""
        if not self.seq_running:
            return

        # Find next non-empty command
        while self.seq_current < len(self.commands):
            cmd = self.commands[self.seq_current].strip()
            self.seq_current += 1

            if cmd:
                self.entry.delete(0, "end")
                self.entry.insert(0, cmd)
                self.send()
                self.seq_status.config(text=f"Current: {self.seq_current}/{len(self.commands)}")
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

        self.seq_running = True
        self.seq_current = 0
        self.seq_status.config(text="Starting sequence...")
        self._send_next_command()

    def seq_stop(self) -> None:
        """Stop sequential command execution."""
        self.seq_running = False
        self.seq_status.config(text="Sequence stopped")
        self.set_status("sequence stopped")

    def toggle_repeat(self) -> None:
        """Toggle command repeat."""
        if self.repeat_after:
            self.root.after_cancel(self.repeat_after)
            self.repeat_after = None
            return
        
        if not self.last_cmd:
            return
        
        sec = self.repeat_sec.get()
        if sec <= 0:
            return
        
        self._repeat_send()
    
    def _repeat_send(self) -> None:
        """Repeat command."""
        if not self.last_cmd:
            self.repeat_after = None
            return
        
        self.backend.write((self.last_cmd + "\r").encode())
        line = f">> {self.last_cmd}  (repeat)\n"
        self.log_buffer.append(line)
        self.log.insert("end", line)
        self.log.see("end")
        
        self.repeat_after = self.root.after(
            int(self.repeat_sec.get() * 1000),
            self._repeat_send
        )
    
    def on_list_click(self, event: tk.Event) -> None:
        """Handle listbox click."""
        idx = self.listbox.nearest(event.y)
        txt = self.listbox.get(idx).strip()
        if txt:
            self.entry.delete(0, "end")
            self.entry.insert(0, txt)
            self.last_cmd = txt
            self.backend.write((txt + "\r").encode())
            line = f">> {txt}\n"
            self.log_buffer.append(line)
            self.log.insert("end", line)
            self.log.see("end")
    
    def edit_cmd(self, event: tk.Event) -> None:
        """Edit command in listbox."""
        idx = self.listbox.curselection()
        if not idx:
            return
        
        idx = idx[0]
        old = self.listbox.get(idx)
        new = simpledialog.askstring("Edit", "Command:", initialvalue=old)
        if new is not None:
            self.listbox.delete(idx)
            self.listbox.insert(idx, new)
            self.commands[idx] = new
    
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
    
    def set_theme(self, name: str) -> None:
        """Set color theme."""
        self.cfg["theme"] = name
        self.apply_theme()
    
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
        for c in self.commands:
            self.listbox.insert("end", c)
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
