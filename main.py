import ctypes
import threading
import time
import subprocess
from ctypes import wintypes
from pycaw.pycaw import AudioUtilities
import tempfile
import os

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

VIDEO_URL = "https://rickroll.it/rickroll.mp4"

html_content = """
<!DOCTYPE html>
<html>
<head><style>
html, body {
  margin: 0;
  padding: 0;
  overflow: hidden;
  background: black;
}
video {
  width: 100vw;
  height: 100vh;
  object-fit: cover;
  display: block;
  pointer-events: none;
}
</style></head>
<body>
<video src="VIDEO_URL_PLACEHOLDER" autoplay loop></video>
</body>
</html>
""".replace("VIDEO_URL_PLACEHOLDER", VIDEO_URL)

with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
    f.write(html_content)
    temp_path = f.name

file_url = "file:///" + temp_path.replace("\\", "/")


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


def main():

    H_POC = user32.CreateDesktopW("PoCSecureDesktop", None, None, 0x0001, 0x10000000, None)
    H_DEF = user32.OpenDesktopW("Default", 0, False, 0x00000100)

    X = user32.GetSystemMetrics(0) - 1
    Y = user32.GetSystemMetrics(1) - 1

    user32.SwitchDesktop(H_POC)
    time.sleep(0.05)
    user32.SwitchDesktop(H_DEF)
    hide_taskbar()
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    user32.EnumWindows(enum_proc_factory(True), 0)
    chrome = subprocess.Popen([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "--kiosk",
        "--autoplay-policy=no-user-gesture-required",
       # VIDEO_URL
        file_url
    ])
    set_volume(25, False)

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
    user32.SwitchDesktop(H_DEF)
    set_volume(0, True)
    user32.CloseDesktop(H_POC)
    user32.CloseDesktop(H_DEF)
    user32.EnumWindows(enum_proc_factory(False), 0)
    chrome.terminate()
    chrome.wait()
    os.remove(temp_path)
    show_taskbar()

if __name__ == "__main__":
    main()
