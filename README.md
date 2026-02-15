# USB Serial IDE

A powerful yet very lightweight terminal for engineers. Specially tuned for daily work with UART, STM32, ESP, nRF, etc.

![Screenshot](screenshots/main.png)

## Features

- Hotkeys for everything
- Quick command list (single click = send)
- Repeat transmission with configurable interval and repeat count
- Automatic log saving with nice filename
- Profiles (saves all settings + commands)
- Full tolerance to USB port disconnection
- Dark/light themes
- Virtual mode for debugging

## Hotkeys

| Key           | Action                                           |
|---------------|--------------------------------------------------|
| **Ctrl + X**  | Quit program                                     |
| **Ctrl + C**  | Clear terminal and buffer                        |
| **Ctrl + S**  | Save log (`YYYY-MM-DD_HH-MM-SS_term.txt`)        |
|               | automatically copies it to the system clipboard. |
| **Ctrl + F**  | Save default profile                             |
| **Ctrl + H**  | Show this help                                   |
| **Esc**       | Return from help back to log                     |
| **Enter**     | Send command                                     |
| **Click on right panel line** | Send + copy to input field       |
| **Double-click on line**      | Edit command                     |
| **Click on HEX**              | Copy hex string to clipboard     |

Pressing Ctrl + S now not only saves the log to a file, 
but also automatically copies it to the system clipboard.
You can paste it directly (Cmd + V / Ctrl + V) into 
any editor, chat, notes, etc.

## Installation & Run

```bash
git clone https://github.com/your-username/usbs-serial-ide.git
cd usbs-serial-ide
pip install -r requirements.txt
python usbs_term.py

## Dependencies

- Python 3.8+
- pyserial (`pip install pyserial`)

tkinter is usually already installed with Python.

If not, install the `python3-tk` / `python-tk` package (Linux) or `python-tk` via brew (macOS).
