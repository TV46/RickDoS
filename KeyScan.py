import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.c_ulong),
        ("scanCode", ctypes.c_ulong),
        ("flags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.c_void_p)
    ]

@ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM
)
def kb_proc(nCode, wParam, lParam):
    if nCode >= 0:
        kb = ctypes.cast(
            lParam,
            ctypes.POINTER(KBDLLHOOKSTRUCT)
        )[0]

        if wParam == 0x0100:  # key down
            print(
                f"VK: {hex(kb.vkCode)}  Scan: {hex(kb.scanCode)}"
            )

    return user32.CallNextHookEx(None, nCode, wParam, lParam)


hook = user32.SetWindowsHookExW(
    13,  # WH_KEYBOARD_LL
    kb_proc,
    None,
    0
)

msg = wintypes.MSG()

while True:
    if user32.GetMessageW(ctypes.byref(msg), None, 0, 0):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))