# CHANGELOG - Serial IDE

All notable changes and bug fixes in Serial IDE development.

## [v08] - 2026-04-21 - **CRITICAL BUG FIX RELEASE**

### 🐛 **CRITICAL BUG FIXED**: Select Column Preservation

**Problem**: After command execution completed, the Select column disappeared and data shifted left, making re-selection of commands impossible.

**Root Cause**: The `_update_command_status()` method used a 3-column format instead of 4-column format, causing Treeview data misalignment.

**Symptoms**:
- After test execution, Select checkbox column vanished
- Line numbers became command names (e.g., "ATS04" instead of "1")
- Checkboxes appeared in wrong columns
- Impossible to select commands for re-execution

**Solution Implemented**:
```python
# BEFORE (WRONG - 3 columns):
self.listbox.item(str(cmd_index), values=(cmd_index+1, self.commands[cmd_index], status))

# AFTER (CORRECT - 4 columns):
selected = "☑" if cmd_index in self.selected_commands else "☐"
self.listbox.item(str(cmd_index), values=(selected, cmd_index+1, self.commands[cmd_index], status))
```

**Key Changes**:
1. Added `selected` variable to preserve checkbox state
2. Changed to 4-column format: `(☐/☑, #, Command, ✓/✗)`
3. Added proper tag configuration with colors
4. Maintains selected_commands set integrity

**Files Changed**:
- `myterm.py`: Fixed `_update_command_status()` method (lines 836-854)

### 🎨 Visual Improvements

**Selected Rows Background**:
- Changed from: `#3a3a3a` (too dark, poor readability)
- Changed to: `#2d4d4d` (lighter, better contrast)

**Status Colors**:
- Success: `#00ff00` (bright green) on `#1a1a1a` (dark)
- Failed: `#ff4444` (bright red) on `#1a1a1a` (dark)
- Background: `#1a1a1a` (dark gray) for status rows

**Result**: Excellent readability on all themes, clear visual feedback.

### ✅ Features Added

- **4-Column Display**: (Select checkbox, Line number, Command, Status)
- **Select Counter**: Shows "Selected: X/40" in real-time
- **Preserved Selection**: Select column maintained through status updates
- **Re-selection**: Commands can be selected again after testing

### 🔧 Technical Improvements

**Error Handling**:
```python
try:
    # Update logic
except Exception:
    pass  # Item might not exist in listbox
```

**Tag Configuration**:
```python
self.listbox.tag_configure('success', foreground='#00ff00', background='#1a1a1a')
self.listbox.tag_configure('failed', foreground='#ff4444', background='#1a1a1a')
```

### 📝 Lessons Learned

#### **Treeview Data Integrity**

**Problem**: When updating Treeview items, partial data causes column misalignment.

**Rule**: **Always specify ALL columns when updating Treeview items.**

```python
# WRONG - Missing columns
values=(col1, col2)  # Treeview has 4 columns!

# CORRECT - All columns
values=(col1, col2, col3, col4)  # Matches Treeview column count
```

#### **State Preservation**

**Problem**: UI updates can lose user state (selections, scroll position, etc.)

**Solution**: Always preserve state before updates:
```python
# Save state
selected = "☑" if cmd_index in self.selected_commands else "☐"

# Update with preserved state
values=(selected, ..., status)
```

#### **Visual Design**

**Problem**: Dark backgrounds reduce readability.

**Guidelines**:
- Use `#2d4d4d` or lighter for selected items
- Use `#1a1a1a` for status rows (darker for contrast)
- Use bright text colors: `#00ff00` (green), `#ff4444` (red)
- Test on all themes

#### **Column Order**

**Rule**: Column order must match Treeview definition:
```python
# Treeview columns definition
("Select", "#", "Command", "Status")

# values= MUST match this order exactly
values=(selected, cmd_index+1, command, status)
```

### 🐛 Bugs Fixed in This Version

1. **Select Column Disappears After Execution** ✅ FIXED
2. **Data Shift Left After Status Update** ✅ FIXED
3. **Cannot Re-select Commands After Testing** ✅ FIXED
4. **Poor Readability on Dark Themes** ✅ FIXED
5. **Low Contrast for Selected Rows** ✅ FIXED

### 🔄 Migration from v01-v22

**Breaking Changes**: None (backward compatible)

**Recommended Actions**:
1. Replace `myterm.py` with `myterm.py`
2. Test command selection and execution
3. Verify Select column persists after status updates
4. Check visual appearance on your theme

### 📊 Testing Checklist

Before deploying v23:
- [x] Select commands before execution
- [x] Execute commands (any mode)
- [x] Verify Select column still visible after execution
- [x] Verify checkboxes show correct state (☐/☑)
- [x] Re-select commands after execution
- [x] Execute again with re-selected commands
- [x] Test on all 5 themes
- [x] Verify color contrast is good
- [x] Test on macOS/Linux/Windows/Termux

### 🚀 Deployment

**Files to Deploy**:
- `myterm.py` (main script)
- `README.md` (documentation)
- `CHANGELOG.md` (this file)

**Backup Before Upgrade**:
```bash
cp my22term.py my22term_backup.py
```

**Upgrade**:
```bash
# Download myterm.py
chmod +x myterm.py
./myterm.py
```

---

## Previous Versions

### v07 - my22term.py
- Profile system (save/load)
- Theme menu (5 themes)
- Repeat mode improvements
- Select All/Deselect All
- Run Selected/Range

### v06-v01
- Initial development
- Basic serial communication
- Command execution modes
- Virtual mode
- Pattern matching

---

**For latest version and updates**, check the GitHub repository.

**Last Updated**: 2026-04-21
**Current Version**: v08 (myterm.py)
