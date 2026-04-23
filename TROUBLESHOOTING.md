# TROUBLESHOOTING GUIDE - Serial IDE

Common problems and solutions for Serial IDE v08.

## 🐛 Critical Issues

### Issue: Select Column Disappears After Execution

**Versions Affected**: v01-v22  
**Fixed In**: v23 (my23term.py)

**Symptoms**:
- After running tests, Select checkbox column vanishes
- Line numbers show command names instead (e.g., "ATS04")
- Checkboxes appear in wrong columns
- Cannot re-select commands for another run

**Root Cause**:
`_update_command_status()` method used 3-column format instead of 4-column format.

**Solution**:
Upgrade to `my23term.py` (v08) where this is fixed.

**Technical Details**:
```python
# WRONG (v01-v22):
values=(cmd_index+1, self.commands[cmd_index], status)  # 3 columns

# CORRECT (v23):
selected = "☑" if cmd_index in self.selected_commands else "☐"
values=(selected, cmd_index+1, self.commands[cmd_index], status)  # 4 columns
```

---

## 🔧 Installation Issues

### Problem: "tkinter not available" Error

**Symptoms**:
```
Error: tkinter not available: No module named 'tkinter'
```

**Solution by Platform**:

#### macOS
```bash
# Option 1: Use system Python
/usr/bin/python3 my23term.py

# Option 2: Install via Homebrew
brew install python-tk
```

#### Linux (Debian/Ubuntu)
```bash
sudo apt-get install python3-tk
```

#### Linux (Fedora)
```bash
sudo dnf install python3-tkinter
```

#### Termux (Android)
```bash
pkg install python-tk
```

#### Windows
```bash
# tkinter should be included
# If missing, reinstall Python from python.org
```

### Problem: "pyserial not installed"

**Solution**:
```bash
pip install pyserial
```

Or:
```bash
pip3 install pyserial
```

---

## 🔌 Connection Issues

### Problem: Cannot Open Serial Port

**Symptoms**:
- Port not listed in dropdown
- "Port busy" error
- Permission denied

**Solutions**:

#### Port Not Listed
```bash
# Check available ports
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"
```

#### Port Busy (Linux/macOS)
```bash
# Check what's using the port
lsof | grep tty.usb

# Kill the process
kill -9 <PID>
```

#### Port Busy (Windows)
- Close Arduino IDE, other terminal programs
- Check Device Manager for port conflicts

#### Permission Denied (Linux)
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and log back in
```

### Problem: Frequent Disconnections

**Symptoms**:
- Connection drops randomly
- "Disconnected" errors

**Solution**: Enable auto-reconnect (already enabled by default):
```python
self.auto_reconnect = True
self.reconnect_delay = 2000  # 2 seconds
self.max_reconnect_attempts = 5
```

**Manual Reconnect**: Click "Port settings" and reselect port.

---

## 🚀 Execution Issues

### Problem: Commands Not Executing

**Symptoms**:
- Click "Start" but nothing happens
- Commands in queue but no execution

**Checklist**:
1. **Port connected**: Status should show "connected"
2. **Commands loaded**: Should see 40 commands in list
3. **Pattern matching**: Check seq_pattern in config
4. **Execution mode**: Verify mode is selected (seq/repeat/range/selected)

**Solution**:
- Use **VIRTUAL** mode to test without hardware
- Check serial connection with other terminal
- Verify baud rate matches device

### Problem: Commands Stop After First One

**Symptoms**:
- First command executes
- Subsequent commands don't run

**Cause**: Pattern matching not detecting "Complete"

**Solution**:
1. Check your device sends "Complete" (or your pattern)
2. Adjust `seq_pattern` in config
3. Increase `seq_timeout` (default 10 seconds)
4. Use virtual mode to test pattern matching

### Problem: Timeout Errors

**Symptoms**:
- Commands timeout after 10 seconds
- Not waiting for device response

**Solution**:
```python
self.seq_timeout = cfg.get("seq_timeout", 10)  # Increase to 20 or 30
```

Or adjust to match your device's actual response time.

---

## 🎨 Visual Issues

### Problem: Text Hard to Read

**Symptoms**:
- Low contrast on dark themes
- Selected rows too dark

**Solution** (v23+):
Themes are optimized with:
- Selected rows: `#2d4d4d` (light green-gray)
- Status backgrounds: `#1a1a1a` (dark)
- Success text: `#00ff00` (bright green)
- Failed text: `#ff4444` (bright red)

**Manual Theme Change**: Use **Theme** menu to select different theme.

### Problem: Colors Look Wrong

**Symptoms**:
- Green/red colors not showing
- Background colors missing

**Cause**: Old version (v01-v22)

**Solution**: Upgrade to `my23term.py` (v23) with improved colors.

---

## 📋 Profile Issues

### Problem: Cannot Save Profile

**Symptoms**:
- Click "Save profile" but nothing happens
- No error message

**Solution**:
1. Ensure `./profiles/` directory exists
2. Check write permissions
3. Try "Save profile as..." and choose location

**Manual Fix**:
```bash
mkdir -p profiles
chmod +w profiles
```

### Problem: Profile Not Loading

**Symptoms**:
- Click "Load profile" but list doesn't update

**Solution**:
1. Verify profile file exists in `./profiles/`
2. Check JSON is valid:
```bash
python3 -m json.tool profiles/your_profile.json
```
3. Try "Load profile as..." and select manually

---

## 🔄 Repeat Mode Issues

### Problem: Repeat Mode Not Working

**Versions Affected**: v01-v06  
**Fixed In**: v07+

**Symptoms**:
- Click "Repeat" but only executes once
- Waits for response between repeats

**Solution**: Upgrade to `my23term.py` (v23) where repeat works without waiting.

**Technical Detail**: v07+ uses `_schedule_next_repeat()` instead of waiting for pattern match.

---

## 📊 Status Display Issues

### Problem: Status Not Showing After Execution

**Symptoms**:
- Commands execute but no ✓/✗ symbols
- Status column empty

**Cause**: Multiple possible causes

**Solutions**:
1. Check `_update_command_status()` is being called
2. Verify command_status dictionary is updated
3. Check tags are configured:
```python
self.listbox.tag_configure('success', foreground='#00ff00', background='#1a1a1a')
self.listbox.tag_configure('failed', foreground='#ff4444', background='#1a1a1a')
```

4. For v23: Ensure 4-column format is used

### Problem: Wrong Status Colors

**Symptoms**:
- Success not green
- Failed not red

**Solution** (v23+):
Colors are hardcoded:
```python
success: '#00ff00'  # Bright green
failed: '#ff4444'   # Bright red
```

If using older version, upgrade to v23.

---

## 🖥️ Platform-Specific Issues

### macOS

**Issue**: Window size wrong on startup  
**Fix**: Window geometry is saved and restored automatically

**Issue**: Cannot access /dev/cu.*  
**Fix**: Add user to dialout group or use sudo

### Linux

**Issue**: Port permission denied  
**Fix**:
```bash
sudo usermod -a -G dialout $USER
# Log out and back in
```

**Issue**: Python 3.8+ not available  
**Fix**:
```bash
# Ubuntu/Debian
sudo apt-get install python3.8+

# Fedora
sudo dnf install python3.8+
```

### Windows

**Issue**: COM port number > 9  
**Symptoms**: Cannot open COM10, COM11, etc.  
**Fix**: Use \\.\COMN syntax (handled automatically by pyserial)

**Issue**: Wrong baud rate  
**Fix**: Device Manager → Ports → Advanced → set correct baud

### Termux (Android)

**Issue**: Package not found  
**Fix**:
```bash
pkg install python-tk
pkg install pyserial
```

**Issue**: Permission denied for /dev/tty*  
**Fix**: Termux needs root access for serial ports

---

## 🐛 Debug Mode

### Enable Debug Logging

Add to `my23term.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Serial Data Flow

Add to `on_rx()`:
```python
def on_rx(self, data: bytes) -> None:
    print(f"RX: {data}")  # Debug print
    # ... rest of method
```

### Test Without Hardware

Use **VIRTUAL** mode:
```python
cfg = {
    "port": "VIRTUAL",
    "baud": 115200
}
```

This echoes sent data back without real hardware.

---

## 📞 Getting Help

### Information to Provide

When reporting issues, include:
1. **Version**: Which my##term.py?
2. **Platform**: macOS/Linux/Windows/Termux?
3. **Python Version**: `python3 --version`
4. **Error Message**: Full error traceback
5. **Steps to Reproduce**: What you did before problem
6. **Expected Behavior**: What should happen
7. **Actual Behavior**: What actually happened

### Common Debug Commands

```bash
# Check Python version
python3 --version

# Check pyserial installed
python3 -c "import serial; print(serial.__version__)"

# Check tkinter available
python3 -c "import tkinter; print('OK')"

# List serial ports
python3 -c "import serial.tools.list_ports; print([p.device for p in serial.tools.list_ports.comports()])"

# Validate profile JSON
python3 -m json.tool profiles/profile_name.json

# Test syntax
python3 -m py_compile my23term.py
```

---

## 🔄 Quick Fixes Summary

| Problem | Quick Fix |
|---------|-----------|
| Select column disappears | Upgrade to my23term.py (v23) |
| tkinter not available | Install python-tk for your platform |
| Port busy | Close other programs using port |
| Commands not executing | Check connection, try VIRTUAL mode |
| Pattern timeout | Increase seq_timeout in config |
| Poor readability | Change Theme or upgrade to v23 |
| Profile not saving | Create ./profiles/ directory |
| Repeat not working | Upgrade to my23term.py (v23) |

---

**Last Updated**: 2026-04-21  
**Version**: v08 (my23term.py)

For version history, see [CHANGELOG.md](CHANGELOG.md).
