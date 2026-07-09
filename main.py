import ctypes
import threading
import time
import subprocess
from ctypes import wintypes
from pycaw.pycaw import AudioUtilities


user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32  = ctypes.windll.shell32

user32.CreateDesktopW.restype = ctypes.c_void_p
user32.OpenDesktopW.restype = ctypes.c_void_p

user32.CallNextHookEx.restype = ctypes.c_ssize_t
user32.CallNextHookEx.argtypes = [
    ctypes.c_void_p,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]

user32.SetCursorPos.restype = wintypes.BOOL
user32.SetCursorPos.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
]

user32.GetSystemMetrics.restype = ctypes.c_int
user32.GetSystemMetrics.argtypes = [
    ctypes.c_int,
]

user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowThreadProcessId.restype = wintypes.DWORD

SW_RESTORE = 9

stop        = threading.Event()
hooks_ready = threading.Event()

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong),
                ("flags",  ctypes.c_ulong), ("time",     ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


keys_down = set()

VK_WIN= 0x5B # win
VK_CTRL_KEYS = {0x11, 0xA2, 0xA3}
VK_T = 0x54 # t

@ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM
)

def kb_proc(nCode, wParam, lParam):
    if nCode >= 0 and lParam:
        kb = ctypes.cast(
            lParam,
            ctypes.POINTER(KBDLLHOOKSTRUCT)
        )[0]

        vk = kb.vkCode

        # Key down
        if wParam == 0x0100 or wParam == 0x0104:
            keys_down.add(vk)

        # Key up
        elif wParam == 0x0101 or wParam == 0x0105:
            keys_down.discard(vk)

        # Check Ctrl + Shift + Esc
        if (
            VK_WIN in keys_down and
            any(ctrl in keys_down for ctrl in VK_CTRL_KEYS) and
            VK_T in keys_down
        ):
            stop.set()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

VIDEO_URL = "https://anondrop.net/1519715400626081836/Rick%20Astley%20-%20Never%20Gonna%20Give%20You%20Up%20(Official%20Video)%20(4K%20Remaster).mp4"
SM_CXSCREEN = 0
SM_CYSCREEN = 1

SW_HIDE = 0
SW_SHOW = 5

def hide_taskbar():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, SW_HIDE)

def show_taskbar():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, SW_SHOW)


class SEI(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong), ("fMask", ctypes.c_ulong),
        ("hwnd", ctypes.c_void_p), ("lpVerb", ctypes.c_wchar_p),
        ("lpFile", ctypes.c_wchar_p), ("lpParameters", ctypes.c_wchar_p),
        ("lpDirectory", ctypes.c_wchar_p), ("nShow", ctypes.c_int),
        ("hInstApp", ctypes.c_void_p), ("lpIDList", ctypes.c_void_p),
        ("lpClass", ctypes.c_wchar_p), ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", ctypes.c_ulong), ("hIconOrMonitor", ctypes.c_void_p),
        ("hProcess", ctypes.c_void_p),
    ]

def trigger():
    sei = SEI()
    sei.cbSize = ctypes.sizeof(SEI)
    sei.fMask  = 0x00000040
    sei.lpVerb = "runas"
    sei.lpFile = "cmd.exe"
    sei.lpParameters = "/c exit"
    sei.nShow  = 0
    shell32.ShellExecuteExW(ctypes.byref(sei))
    if sei.hProcess:
        kernel32.CloseHandle(sei.hProcess)

def hook_thread():
    h_kb = user32.SetWindowsHookExW(13, kb_proc, None, 0)
    hooks_ready.set()
    m = ctypes.wintypes.MSG()
    while not stop.is_set():
        if user32.PeekMessageW(ctypes.byref(m), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(m))
            user32.DispatchMessageW(ctypes.byref(m))
        time.sleep(0.0005)
    user32.UnhookWindowsHookEx(h_kb)

def toggle(h_poc, h_def):
    while not stop.is_set():
        user32.SwitchDesktop(h_poc)
        user32.SwitchDesktop(h_def)

def mouse_thread(x, y):
    while not stop.is_set():
        user32.SetCursorPos(x, y)

def set_volume(percent, mute):
    speakers = AudioUtilities.GetSpeakers()
    volume = speakers.EndpointVolume

    volume.SetMute(mute, None)
    volume.SetMasterVolumeLevelScalar(percent / 100.0, None)

def bring_process_to_front(pid, timeout=5):
    hwnd = None
    end = time.time() + timeout

    EnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM
    )

    while time.time() < end:
        def callback(h, l):
            nonlocal hwnd

            proc = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(proc))

            if proc.value == pid and user32.IsWindowVisible(h):
                hwnd = h
                return False  # stop enumeration
            return True

        user32.EnumWindows(EnumProc(callback), 0)

        if hwnd:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            return hwnd

        time.sleep(0.1)

    return None

def main():

    H_POC = user32.CreateDesktopW("PoCSecureDesktop", None, None, 0x0001, 0x10000000, None)
    H_DEF = user32.OpenDesktopW("Default", 0, False, 0x00000100)

    X = user32.GetSystemMetrics(SM_CXSCREEN) - 1
    Y = user32.GetSystemMetrics(SM_CYSCREEN) - 1

    user32.SwitchDesktop(H_POC)
    threading.Thread(target=trigger, daemon=True).start()
    time.sleep(0.05)
    user32.SwitchDesktop(H_DEF)

    chrome = subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--kiosk",
        VIDEO_URL
    ])
    set_volume(0, False)
    hide_taskbar()
    bring_process_to_front(chrome.pid)

    threading.Thread(
        target=hook_thread,
        daemon=False
    ).start()

    hooks_ready.wait()

    threading.Thread(
        target=toggle,
        args=(H_POC, H_DEF),
        daemon=True
    ).start()

    threading.Thread(
        target=mouse_thread,
        args=(X, Y),
        daemon=True,
    ).start()

    stop.wait()
    time.sleep(0.1)
    user32.SwitchDesktop(H_DEF)
    set_volume(25, True)
    show_taskbar()
    user32.CloseDesktop(H_POC)
    user32.CloseDesktop(H_DEF)
    chrome.terminate()
    chrome.wait()

if __name__ == "__main__":
    main()