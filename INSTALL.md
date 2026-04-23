# Installation Guide - Serial IDE v08

Complete installation instructions for Serial IDE on all platforms.

## 📦 Prerequisites

### Required
- **Python 3.8+**
- **pyserial** library
- **tkinter** GUI library

### Check Python Version
```bash
python3 --version
# Should show: Python 3.8.x or higher
```

If Python 3.8+ is not installed, install it first.

---

## 🍎 macOS Installation

### Option 1: System Python (Recommended)

macOS includes Python 3 with tkinter pre-installed.

```bash
# Check if python3 is available
python3 --version

# Install pyserial
pip3 install pyserial

# Download my23term.py
chmod +x my23term.py

# Run
./my23term.py
```

### Option 2: Homebrew Python

```bash
# Install Python with tkinter support
brew install python-tk

# Install pyserial
pip3 install pyserial

# Run
./my23term.py
```

### Option 3: pyenv

```bash
# Install tcl-tk
brew install tcl-tk

# Install Python with tk support
PYTHON_CONFIGURE_OPTS='--with-tcltk-includes=-I$(brew --prefix tcl-tk)/include --with-tcltk-libs=-L$(brew --prefix tcl-tk)/lib' pyenv install 3.14.0

# Install pyserial
pip install pyserial

# Run
./my23term.py
```

---

## 🐧 Linux Installation

### Debian/Ubuntu/Linux Mint

```bash
# Install Python 3 and tkinter
sudo apt-get update
sudo apt-get install python3 python3-tk

# Install pyserial
pip3 install pyserial

# Or via apt
sudo apt-get install python3-serial

# Download and run
chmod +x my23term.py
./my23term.py
```

### Fedora/RHEL/CentOS

```bash
# Install Python 3 and tkinter
sudo dnf install python3 python3-tkinter

# Install pyserial
pip3 install pyserial

# Or via dnf
sudo dnf install python3-pyserial

# Download and run
chmod +x my23term.py
./my23term.py
```

### Arch Linux

```bash
# Install Python 3 and tkinter
sudo pacman -S python python-tk

# Install pyserial
pip install pyserial

# Or via pacman
sudo pacman -S python-pyserial

# Download and run
chmod +x my23term.py
./my23term.py
```

### Serial Port Permissions (Linux)

```bash
# Add user to dialout group for serial port access
sudo usermod -a -G dialout $USER

# Log out and log back in for changes to take effect

# Or use sudo for temporary access
sudo ./my23term.py
```

---

## 🪟 Windows Installation

### Option 1: Python.org Installer

1. Download Python 3.8+ from https://www.python.org/downloads/
2. Run installer
3. **IMPORTANT**: Check "Add Python to PATH"
4. **IMPORTANT**: Check "tcl/tk and IDLE" (includes tkinter)
5. Click "Install Now"

```cmd
# Open Command Prompt or PowerShell

# Install pyserial
pip install pyserial

# Navigate to download location
cd path\to\USBs

# Run
python my23term.py

# Or if in PATH
my23term.py
```

### Option 2: Microsoft Store

```cmd
# Install Python from Microsoft Store
# Search "Python 3.10" or later

# Install pyserial
pip install pyserial

# Run
python my23term.py
```

### Serial Drivers (Windows)

Most USB-serial devices work automatically. If not:

1. **CP210x** (Silicon Labs): https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
2. **FTDI**: https://www.ftdichip.com/Drivers/VCP.htm
3. **CH340**: http://www.wch.cn/download/CH341SER_EXE.html

---

## 📱 Termux (Android) Installation

### Install Termux App

1. Install Termux from F-Droid (recommended): https://f-droid.org/en/packages/com.termux/
2. Or from Google Play (older version)

### Install Packages

```bash
# Update packages
pkg update

# Install Python
pkg install python

# Install tkinter
pkg install python-tk

# Install pyserial
pip install pyserial

# Download my23term.py (use wget or curl)
wget https://raw.githubusercontent.com/yourusername/USBs/main/my23term.py

# Make executable
chmod +x my23term.py

# Run
./my23term.py
```

### Note on Serial Ports in Termux

Termux needs root access for direct serial port access:
```bash
# Give Termux root access (requires rooted device)
su

# Run with root
./my23term.py
```

Or use **VIRTUAL** mode for testing without hardware.

---

## 🔄 Verifying Installation

### Test Python

```bash
python3 --version
# Should show: Python 3.8.x or higher
```

### Test tkinter

```bash
python3 -c "import tkinter; print('tkinter OK')"
# Should show: tkinter OK
```

### Test pyserial

```bash
python3 -c "import serial; print('pyserial OK')"
# Should show: pyserial OK
```

### List Serial Ports

```bash
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
# Should show list of available ports
```

### Test my23term.py

```bash
# Syntax check
python3 -m py_compile my23term.py

# Run (should open window)
./my23term.py
```

---

## 📥 Download

### Method 1: Direct Download

```bash
# Download my23term.py
wget https://raw.githubusercontent.com/yourusername/USBs/main/my23term.py

# Or with curl
curl -O https://raw.githubusercontent.com/yourusername/USBs/main/my23term.py

# Make executable
chmod +x my23term.py
```

### Method 2: Git Clone

```bash
# Clone repository
git clone https://github.com/yourusername/USBs.git
cd USBs

# Run
./my23term.py
```

### Method 3: Download and Extract

1. Download ZIP from GitHub
2. Extract ZIP file
3. Open terminal in extracted directory
4. Run: `./my23term.py`

---

## 🎯 First Run

### 1. Launch Terminal

```bash
./my23term.py
```

### 2. Select Port

- Choose from dropdown (real port or VIRTUAL)
- VIRTUAL mode for testing without hardware

### 3. Set Baud Rate

- Default: 115200
- Match your device's baud rate

### 4. Load Commands

- Commands are auto-loaded or enter manually
- Up to 40 commands supported

### 5. Execute

- Select mode: Sequential / Repeat / Range / Selected
- Click **Start** to begin

---

## 🐛 Troubleshooting Installation

### Problem: "python3: command not found"

**Solution**: Install Python 3.8+
```bash
# macOS
brew install python

# Linux
sudo apt-get install python3

# Windows
# Download from python.org
```

### Problem: "tkinter not available"

**Solution**: Install python-tk
```bash
# macOS
brew install python-tk

# Linux Debian/Ubuntu
sudo apt-get install python3-tk

# Linux Fedora
sudo dnf install python3-tkinter

# Termux
pkg install python-tk
```

### Problem: "pyserial not installed"

**Solution**: Install pyserial
```bash
pip3 install pyserial
```

Or:
```bash
# Linux
sudo apt-get install python3-serial

# macOS
brew install pyserial
```

### Problem: Permission Denied

**Solution**: Make executable
```bash
chmod +x my23term.py
```

### Problem: "./my23term.py: No such file"

**Solution**: Check you're in correct directory
```bash
ls -la my23term.py
pwd
```

---

## 📦 What's Installed

After installation, you have:

```
USBs/
├── my23term.py          # Main terminal script
├── profiles/            # Auto-created profile storage
│   └── profile_*.json   # Your saved profiles
├── README.md            # User documentation
├── CHANGELOG.md         # Version history
├── INSTALL.md           # This file
└── TROUBLESHOOTING.md   # Problem solving guide
```

---

## 🔄 Updating

### Check Current Version

```bash
head -1 my23term.py
# Should show: #!/usr/bin/env python3
```

### Update to Latest

```bash
# Backup current version
cp my23term.py my23term_backup.py

# Download new version
wget https://raw.githubusercontent.com/yourusername/USBs/main/my23term.py

# Keep your profiles
# They're in ./profiles/ directory

# Run new version
./my23term.py
```

---

## 🎓 Next Steps

1. **Read**: [README.md](README.md) for feature overview
2. **Check**: [CHANGELOG.md](CHANGELOG.md) for version history
3. **Reference**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md) if problems occur

---

## 💡 Tips

- **First time?** Use VIRTUAL mode to test without hardware
- **Have hardware?** Check device baud rate before connecting
- **Save often?** Use profile system to save configurations
- **Theme preference?** Try all 5 themes in Theme menu
- **Select issues?** Upgrade to my23term.py (v08) for fix

---

**Last Updated**: 2026-04-21  
**Version**: v08 (my23term.py)

For troubleshooting, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
