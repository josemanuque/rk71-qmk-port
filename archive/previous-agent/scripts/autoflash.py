#!/usr/bin/env python3
"""
Auto-flash QMK by:
1. Launching the official RK71 firmware EXE
2. Finding its window and clicking the Flash/Update button
3. Detecting ISP mode (VID=0x0C45) and immediately killing the EXE
4. Running flash_qmk.py to flash QMK firmware

No extra packages needed — uses ctypes (Windows built-in).
"""
import sys, os, time, subprocess, ctypes, ctypes.wintypes

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FW_EXE   = os.path.join(SCRIPT_DIR, "RK71 RGB Firmware_V1.12_190603.exe")
FLASH_PY = os.path.join(SCRIPT_DIR, "flash_qmk.py")

NORMAL_VID = 0x05AC
NORMAL_PID = 0x024F
ISP_VID    = 0x0C45
ISP_PIDS   = [0x8006, 0x7040, 0x7900, 0x7010]

# Windows API
user32 = ctypes.windll.user32
EnumWindows      = user32.EnumWindows
EnumChildWindows = user32.EnumChildWindows
GetWindowTextW   = user32.GetWindowTextW
GetClassNameW    = user32.GetClassNameW
SendMessageW     = user32.SendMessageW
PostMessageW     = user32.PostMessageW
IsWindowVisible  = user32.IsWindowVisible
BringWindowToTop = user32.BringWindowToTop

BN_CLICKED = 0
WM_COMMAND  = 0x0111
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
BM_CLICK       = 0x00F5

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND,
                              ctypes.wintypes.LPARAM)

def get_window_text(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    GetWindowTextW(hwnd, buf, 256)
    return buf.value

def get_class(hwnd):
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value

def find_rk71_window():
    """Find the RK71 firmware EXE main window."""
    found = []
    keywords = ['rk', 'firmware', 'update', 'keyboard', 'royal kludge', 'rk71']

    @WNDPROC
    def cb(hwnd, _):
        if IsWindowVisible(hwnd):
            title = get_window_text(hwnd).lower()
            if any(k in title for k in keywords):
                found.append(hwnd)
        return True

    EnumWindows(cb, 0)
    return found[0] if found else None

def find_buttons(hwnd):
    """Find all button child windows of a parent window."""
    buttons = []

    @WNDPROC
    def cb(child, _):
        cls = get_class(child)
        if cls.lower() in ('button', 'tbutton', 'tnewbutton', 'tbitbtn'):
            text = get_window_text(child)
            buttons.append((child, text))
        return True

    EnumChildWindows(hwnd, cb, 0)
    return buttons

def click_flash_button(parent_hwnd):
    """Find and click the Flash/Update button in the EXE window."""
    buttons = find_buttons(parent_hwnd)
    print(f"  Found {len(buttons)} buttons:")
    for hwnd, text in buttons:
        print(f"    {hwnd:#010x}: '{text}'")

    # Priority keywords for the flash/update button
    flash_keywords = ['flash', 'update', 'upgrade', 'burn', 'write', 'program',
                      'start', 'begin', 'ok', 'confirm']

    target = None
    for hwnd, text in buttons:
        tl = text.lower().strip()
        for kw in flash_keywords:
            if kw in tl:
                target = (hwnd, text)
                break
        if target: break

    if not target and buttons:
        # Last resort: click the first visible button
        target = buttons[0]
        print(f"  No flash-specific button found, trying first: '{target[1]}'")

    if target:
        hwnd, text = target
        print(f"  Clicking button: '{text}' ({hwnd:#010x})")
        SendMessageW(hwnd, BM_CLICK, 0, 0)
        return True

    print("  No buttons found!")
    return False

def check_isp():
    try:
        import hid
        for d in hid.enumerate():
            if d['vendor_id'] == ISP_VID and d['product_id'] in ISP_PIDS:
                return d['product_id']
    except Exception:
        pass
    return None

def check_normal():
    try:
        import hid
        return bool(hid.enumerate(NORMAL_VID, NORMAL_PID))
    except Exception:
        return False

def main():
    print("=== RK71 Auto-Flash via Official EXE ===\n")

    if not os.path.exists(FW_EXE):
        print(f"ERROR: EXE not found: {FW_EXE}")
        sys.exit(1)

    pid = check_isp()
    if pid:
        print(f"[+] Already in ISP mode (PID=0x{pid:04X})")
        print("[*] Flashing QMK...")
        sys.exit(subprocess.run([sys.executable, FLASH_PY], cwd=SCRIPT_DIR).returncode)

    if not check_normal():
        print("ERROR: Keyboard not found in normal mode")
        sys.exit(1)

    print("[+] Keyboard found")
    print(f"[*] Launching EXE: {os.path.basename(FW_EXE)}")

    proc = subprocess.Popen([FW_EXE], cwd=SCRIPT_DIR)
    print(f"    PID: {proc.pid}")

    # Wait for the window to appear (up to 10s)
    print("[*] Waiting for EXE window...")
    win = None
    for _ in range(100):
        time.sleep(0.1)
        win = find_rk71_window()
        if win:
            break

    if not win:
        print("[!] Window not found — trying to list all visible windows:")
        @WNDPROC
        def cb2(hwnd, _):
            if IsWindowVisible(hwnd):
                title = get_window_text(hwnd)
                if title:
                    print(f"    {hwnd:#010x}: '{title}'")
            return True
        EnumWindows(cb2, 0)
        print("\n[!] Clicking Flash without window focus (sending to proc)...")
    else:
        print(f"[+] Window found: '{get_window_text(win)}' ({win:#010x})")
        BringWindowToTop(win)
        time.sleep(0.5)

        print("[*] Clicking Flash button...")
        click_flash_button(win)

    # Monitor for ISP mode
    print("\n[*] Monitoring for ISP mode (VID=0x0C45)...")
    deadline = time.time() + 30
    isp_pid = None
    while time.time() < deadline:
        isp_pid = check_isp()
        if isp_pid:
            break
        # Keep trying to click buttons in case dialog appeared
        if win and int(time.time() * 2) % 4 == 0:
            new_win = find_rk71_window()
            if new_win:
                btns = find_buttons(new_win)
                if btns:
                    click_flash_button(new_win)
        time.sleep(0.2)

    if not isp_pid:
        print("[!] ISP not detected in 30s — killing EXE")
        proc.terminate()
        sys.exit(1)

    print(f"\n[+] ISP detected! VID=0x{ISP_VID:04X} PID=0x{isp_pid:04X}")
    print("[*] Killing EXE...")
    proc.terminate()
    try: proc.wait(timeout=3)
    except: proc.kill()

    time.sleep(0.5)
    print("[*] Flashing QMK...")
    result = subprocess.run([sys.executable, FLASH_PY], cwd=SCRIPT_DIR)

    if result.returncode == 0:
        print("\n[SUCCESS] QMK flashed! Future reflash: hold Space+B during plug-in.")
    else:
        print("\n[FAILED] Flash failed — see output above")
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
