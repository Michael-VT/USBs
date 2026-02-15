import asyncio
import json
import os
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, messagebox
import serial
import serial.tools.list_ports
from datetime import datetime

LINES_COUNT = 40
PROFILE_DIR = "profiles"
DEFAULT_PROFILE = f"{PROFILE_DIR}/profile_usb_st.json"
os.makedirs(PROFILE_DIR, exist_ok=True)


# ================= THEMES =================

THEMES = {
    "dark": {"bg": "#111", "fg": "#00FFAA"},
    "amber": {"bg": "#1b1200", "fg": "#FFB000"},
    "blue": {"bg": "#0b1320", "fg": "#7FDBFF"},
    "white_on_black": {"bg": "#000", "fg": "#FFF"},
    "white_on_blue": {"bg": "#002b55", "fg": "#FFF"},
}


# ================= SERIAL =================

class SerialBackend:
    def __init__(self, cfg, rx_callback):
        self.cfg = cfg
        self.rx_callback = rx_callback
        self.running = True
        self.virtual = cfg["port"] == "VIRTUAL"

        if not self.virtual:
            self.ser = serial.Serial(cfg["port"], cfg["baud"], timeout=0)

        asyncio.create_task(self.reader())

    async def reader(self):
        while self.running:
            await asyncio.sleep(0.01)
            if self.virtual:
                continue
            data = self.ser.read(self.ser.in_waiting or 1)
            if data:
                self.rx_callback(data)

    def write(self, data: bytes):
        if self.virtual:
            self.rx_callback(b"[echo] " + data)
        else:
            self.ser.write(data)

    def inject_virtual(self, txt):
        if self.virtual:
            self.rx_callback(txt.encode())

    def close(self):
        self.running = False
        if not self.virtual:
            self.ser.close()


# ================= APP =================

class App:
    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        self.log_buffer = []
        self.last_packet = b""
        self.last_cmd = ""
        self.repeat_task = None

        self.backend = SerialBackend(cfg, self.on_rx)

        self.build_ui()
        self.apply_theme()
        self.bind_hotkeys()

        self.loop()

    # -------- UI --------
    def build_ui(self):
        self.root.title("Engineer Serial IDE")
        self.root.geometry("1200x720")

        # menu (оставляем как было)
        menubar = tk.Menu(self.root)
        prof = tk.Menu(menubar, tearoff=0)
        prof.add_command(label="Save profile", command=self.save_profile)
        prof.add_command(label="Load profile", command=self.load_profile)
        menubar.add_cascade(label="Profile", menu=prof)

        theme_menu = tk.Menu(menubar, tearoff=0)
        for t in THEMES:
            theme_menu.add_command(label=t, command=lambda x=t: self.set_theme(x))
        menubar.add_cascade(label="Theme", menu=theme_menu)

        menubar.add_command(label="Port settings", command=self.port_settings)
        menubar.add_command(label="Save log", command=self.save_log)

        self.root.config(menu=menubar)

        paned = ttk.Panedwindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned)
        paned.add(left, weight=3)

        self.log = tk.Text(left, font=("Menlo", 11))
        self.log.pack(fill="both", expand=True)

        bottom = ttk.Frame(left)
        bottom.pack(fill="x")

        self.entry = ttk.Entry(bottom)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self.send_entry)

        ttk.Button(bottom, text="Send", command=self.send_entry).pack(side="left")
        ttk.Button(bottom, text="Repeat", command=self.repeat_last).pack(side="left")

        self.hex_label = ttk.Label(left, text="HEX:", cursor="hand2")
        self.hex_label.pack(fill="x")
        self.hex_label.bind("<Button-1>", self.copy_hex_to_clipboard)

        # virtual inject
        if self.cfg["port"] == "VIRTUAL":
            sim = ttk.Frame(left)
            sim.pack(fill="x")
            self.sim_entry = ttk.Entry(sim)
            self.sim_entry.pack(side="left", fill="x", expand=True)
            self.sim_entry.bind("<Return>", self.inject_virtual)
            ttk.Button(sim, text="Inject RX", command=self.inject_virtual).pack(side="left")

        # right commands
        right = ttk.Frame(paned, width=300)
        paned.add(right, weight=1)

        self.listbox = tk.Listbox(right)
        self.listbox.pack(fill="both", expand=True)

        self.commands = self.cfg.get("commands", [""] * LINES_COUNT)
        for c in self.commands:
            self.listbox.insert("end", c)

        self.listbox.bind("<Double-Button-1>", self.edit_line)
        self.listbox.bind("<Button-1>", self.click_line)   # теперь просто клик = отправка + копия в entry

    # -------- HOTKEYS --------
    def bind_hotkeys(self):
        self.root.bind("<Control-x>", self.exit_app)      # Ctrl+X → выход
        self.root.bind("<Control-c>", self.clear_all)     # Ctrl+C → очистить всё
        self.root.bind("<Control-s>", self.save_log_auto) # Ctrl+S → сохранить лог с автонеймом
        self.root.bind("<Control-f>", self.save_profile_default)  # Ctrl+F → сохранить профиль по умолчанию

    def exit_app(self, event=None):
        self.backend.close()
        self.root.destroy()

        def exit_app(self, event=None):
            self.cleanup()
            self.root.quit()          # завершает главный цикл Tk
            self.root.destroy()       # уничтожает окно

        def on_window_close(self):
            self.cleanup()
            self.root.quit()
            self.root.destroy()

        def cleanup(self):
            self.backend.close()      # останавливает reader и закрывает порт
            self.running = False      # если где-то есть такой флаг — на всякий случай
            # Отменяем все запланированные after
            try:
                self.root.after_cancel(self.loop_id)  # если сохраняете id
            except:
                pass

# В __init__ после build_ui добавьте:
        self.root.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def clear_all(self, event=None):
        self.log.delete("1.0", "end")
        self.log_buffer.clear()
        self.hex_label.config(text="HEX:")
        self.log.see("end")

    def save_log_auto(self, event=None):
        now = datetime.now()
        filename = now.strftime("%Y-%m-%d-%H-%M-%S-term.txt")
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("".join(self.log_buffer))
            messagebox.showinfo("Сохранено", f"Лог сохранён:\n{filename}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def save_profile_default(self, event=None):
        data = self.cfg.copy()
        data["commands"] = self.commands
        try:
            with open(DEFAULT_PROFILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            messagebox.showinfo("Профиль", f"Сохранён профиль по умолчанию:\n{DEFAULT_PROFILE}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # -------- THEME --------
    def set_theme(self, name):
        self.cfg["theme"] = name
        self.apply_theme()

    def apply_theme(self):
        t = THEMES.get(self.cfg.get("theme", "dark"))
        self.log.config(bg=t["bg"], fg=t["fg"], insertbackground="white")

    # -------- RX --------
    def on_rx(self, data: bytes):
        self.last_packet = data
        self.root.after(0, lambda: self.display_rx(data))

    def display_rx(self, data):
        txt = data.decode(errors="ignore")
        self.log.insert("end", txt)
        self.log.see("end")
        self.log_buffer.append(txt)

        hx = " ".join(f"{b:02X}" for b in data)
        self.hex_label.config(text=f"HEX: {hx}")

    # -------- SEND --------
    def send_entry(self, event=None):
        txt = self.entry.get().strip()
        if txt:
            self.send(txt)
            self.entry.delete(0, "end")

    def send(self, txt):
        self.last_cmd = txt
        data = (txt + "\r").encode()
        self.backend.write(data)
        self.log.insert("end", f">> {txt}\n")
        self.log_buffer.append(f">> {txt}\n")
        self.log.see("end")

    def repeat_last(self):
        if self.last_cmd:
            self.send(self.last_cmd)

    # -------- LISTBOX --------
    def click_line(self, event):
        """Один клик → отправить + скопировать в поле ввода"""
        idx = self.listbox.nearest(event.y)
        txt = self.listbox.get(idx)
        if txt:
            self.entry.delete(0, "end")
            self.entry.insert(0, txt)
            self.send(txt)

    def edit_line(self, event):
        idx = self.listbox.curselection()
        if not idx:
            return
        idx = idx[0]
        old = self.listbox.get(idx)
        new = simpledialog.askstring("Edit command", "Command:", initialvalue=old)
        if new is not None:
            self.listbox.delete(idx)
            self.listbox.insert(idx, new)
            self.commands[idx] = new

    # -------- HEX COPY --------
    def copy_hex_to_clipboard(self, event=None):
        text = self.hex_label.cget("text")
        if text.startswith("HEX: "):
            hex_only = text[5:]
            self.root.clipboard_clear()
            self.root.clipboard_append(hex_only)
            self.root.update()  # чтобы сразу скопировалось

    # -------- VIRTUAL --------
    def inject_virtual(self, event=None):
        txt = self.sim_entry.get().strip()
        if txt:
            self.backend.inject_virtual(txt + "\n")
            self.sim_entry.delete(0, "end")

    # -------- PROFILE --------
    def save_profile(self):
        name = simpledialog.askstring("Profile", "Имя профиля:")
        if not name:
            return
        data = self.cfg.copy()
        data["commands"] = self.commands
        with open(f"{PROFILE_DIR}/{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load_profile(self):
        file = filedialog.askopenfilename(initialdir=PROFILE_DIR)
        if not file:
            return
        with open(file, encoding="utf-8") as f:
            data = json.load(f)

        self.backend.close()
        self.cfg = data
        self.commands = data.get("commands", [""] * LINES_COUNT)

        self.log.delete("1.0", "end")
        self.listbox.delete(0, "end")
        for c in self.commands:
            self.listbox.insert("end", c)

        self.backend = SerialBackend(self.cfg, self.on_rx)
        self.apply_theme()

    # -------- SETTINGS --------
    def port_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Port settings")
        tk.Label(win, text="Baudrate:").pack()
        baud = tk.Entry(win)
        baud.insert(0, self.cfg["baud"])
        baud.pack()

        def apply():
            self.cfg["baud"] = int(baud.get())
            win.destroy()

        ttk.Button(win, text="Apply", command=apply).pack()

    # -------- LOG SAVE (ручной) --------
    def save_log(self):
        file = filedialog.asksaveasfilename(defaultextension=".txt")
        if file:
            with open(file, "w", encoding="utf-8") as f:
                f.write("".join(self.log_buffer))

    def show_help(self, event=None):
        self.log.delete("1.0", "end")
        help_text = """
Engineer Serial IDE - горячие клавиши и управление

Ctrl + X      →  Выход из программы
Ctrl + C      →  Очистить терминал и буфер
Ctrl + S      →  Сохранить лог в ГГГГ-ММ-ДД-ЧЧ-ММ-СС-term.txt
Ctrl + F      →  Сохранить профиль по умолчанию (profile_usb_st.json)
Ctrl + H      →  Показать эту справку
Esc           →  Вернуть обычный терминал

Один клик по строке в правой панели → отправить + скопировать в поле ввода
Двойной клик по строке            → редактировать
Клик по HEX: ...                  → скопировать hex-строку в буфер обмена

Профили хранятся в папке profiles/
При запуске загружается profile_usb_st.json (если есть)
        """
        self.log.insert("end", help_text.strip())
        self.log.see("end")
        self.help_mode = True

    def restore_terminal(self, event=None):
        if hasattr(self, 'help_mode') and self.help_mode:
            self.log.delete("1.0", "end")
            for line in self.log_buffer:
                self.log.insert("end", line)
            self.log.see("end")
            self.help_mode = False

# В метод bind_hotkeys добавить:
    def bind_hotkeys(self):
        self.root.bind("<Control-x>", self.exit_app)
        self.root.bind("<Control-c>", self.clear_all)
        self.root.bind("<Control-s>", self.save_log_auto)
        self.root.bind("<Control-f>", self.save_profile_default)
        self.root.bind("<Control-h>", self.show_help)          # ← добавлено
        self.root.bind("<Escape>", self.restore_terminal)      # ← добавлено
    # -------- LOOP --------
    def loop(self):
        self.root.after(10, self.loop)
        if self.root.winfo_exists():
            self.root.after(10, self.loop)


# ================= MAIN =================

def select_port():
    ports = [p.device for p in serial.tools.list_ports.comports()]
    ports.append("VIRTUAL")

    win = tk.Tk()
    win.title("Выберите порт")
    lb = tk.Listbox(win, width=50, height=15)
    lb.pack(fill="both", expand=True, padx=10, pady=10)

    for p in ports:
        lb.insert("end", p)

    res = {"p": None}

    def ok():
        sel = lb.curselection()
        if sel:
            res["p"] = lb.get(sel[0])
        win.destroy()

    ttk.Button(win, text="Открыть", command=ok).pack(pady=5)
    win.mainloop()
    return res["p"]


def main():
    # Загружаем профиль по умолчанию
    if os.path.exists(DEFAULT_PROFILE):
        with open(DEFAULT_PROFILE, encoding="utf-8") as f:
            cfg = json.load(f)
    else:
        cfg = {"port": None, "baud": 115200, "theme": "dark"}

    # Если порт отсутствует — предлагаем выбрать
    available_ports = [p.device for p in serial.tools.list_ports.comports()]
    if cfg.get("port") is None or (cfg["port"] != "VIRTUAL" and cfg["port"] not in available_ports):
        port = select_port()
        if not port:
            return
        cfg["port"] = port

    root = tk.Tk()

    async def run():
        App(root, cfg)
        while True:
            root.update()
            await asyncio.sleep(0.01)

    asyncio.run(run())


if __name__ == "__main__":
    main()
