"""NOVA AI 1.4 · icono en la bandeja de Windows (zona de notificación, junto al reloj).

Sin dependencias nuevas: Win32 con ctypes, como el overlay. Clic o doble clic abre la ventana; el clic
derecho muestra un menú (Abrir, MUTE, Modo reposo, Salir). Si algo falla, `ok` queda en False y Nova
se comporta como antes (cerrar la ventana cierra Nova), para no dejarla nunca escondida sin forma de salir.
"""
from __future__ import annotations

import logging
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

log = logging.getLogger("nova.tray")
IS_WINDOWS = sys.platform == "win32"


@dataclass
class MenuItem:
    label: Callable[[], str]          # texto (ya traducido) cada vez que se abre el menú
    action: Callable[[], None] | None  # None = separador
    checked: Callable[[], bool] | None = None
    default: bool = False             # en negrita: lo que hace el doble clic


SEPARATOR = MenuItem(lambda: "", None)


class Tray(threading.Thread):
    def __init__(self, icon: Path, tooltip: Callable[[], str], items: list[MenuItem]) -> None:
        super().__init__(daemon=True, name="bandeja")
        self.icon_path = Path(icon)
        self.tooltip = tooltip
        self.items = items
        self.ok = False
        self.error = ""
        self.ready = threading.Event()
        self._stop = threading.Event()
        self._notes: queue.Queue = queue.Queue()
        self._hwnd = None
        self._hicon = None
        self._wndproc = None  # referencia viva al callback (si no, Python lo libera y Windows se cuelga)
        self._tip = ""
        self._added = False
        self._last_click = 0.0

    # ------------------------------------------------------------------ API
    def notify(self, title: str, text: str) -> None:
        """Globo / notificación de Windows desde el icono."""
        self._notes.put((title, text))

    def stop(self) -> None:
        """Quita el icono ya (también desde otro hilo: al salir no debe quedar un icono fantasma)."""
        self._stop.set()
        if IS_WINDOWS and self._added and self._hwnd:
            try:
                _shell_icon(NIM_DELETE, self._nid())
            except Exception:  # noqa: BLE001
                log.debug("Quitar el icono", exc_info=True)
            self._added = False

    def wait_ready(self, timeout: float = 3.0) -> bool:
        self.ready.wait(timeout)
        return self.ok

    # --------------------------------------------------------------- hilo
    def run(self) -> None:
        if not IS_WINDOWS:
            self.error = "solo disponible en Windows"
            self.ready.set()
            return
        try:
            self._create()
            self._add()
            self.ok = True
        except Exception as e:  # noqa: BLE001
            log.exception("Bandeja")
            self.error = str(e)
            self.ready.set()
            return
        self.ready.set()
        last = 0.0
        while not self._stop.is_set():
            _pump(self._hwnd)
            now = time.time()
            if now - last > 1.0:
                last = now
                try:
                    tip = (self.tooltip() or "NOVA AI")[:127]
                    if tip != self._tip:
                        self._tip = tip
                        _shell_icon(NIM_MODIFY, self._nid(NIF_TIP))
                except Exception:  # noqa: BLE001
                    log.debug("Texto del icono", exc_info=True)
            try:
                title, text = self._notes.get_nowait()
                nid = self._nid(NIF_INFO)
                nid.szInfoTitle = title[:63]
                nid.szInfo = text[:255]
                nid.dwInfoFlags = NIIF_INFO
                _shell_icon(NIM_MODIFY, nid)
            except queue.Empty:
                pass
            except Exception:  # noqa: BLE001
                log.debug("Notificación", exc_info=True)
            time.sleep(0.05)
        self.stop()
        try:
            user32.DestroyWindow(self._hwnd)
        except Exception:  # noqa: BLE001
            pass

    # ---------------------------------------------------------- Win32
    def _create(self) -> None:
        hinst = kernel32.GetModuleHandleW(None)
        self._taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._wndproc = WNDPROC(self._proc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = "NovaAITray"
        if not user32.RegisterClassExW(ctypes.byref(wc)) and ctypes.get_last_error() != 1410:  # ya registrada
            raise ctypes.WinError(ctypes.get_last_error())
        # Ventana normal pero invisible (no «solo mensajes»: esas no reciben TaskbarCreated si se reinicia el Explorador)
        self._hwnd = user32.CreateWindowExW(0, "NovaAITray", "NOVA AI", 0, 0, 0, 0, 0, None, None, hinst, None)
        if not self._hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        size = user32.GetSystemMetrics(SM_CXSMICON) or 16
        self._hicon = None
        if self.icon_path.exists():
            self._hicon = user32.LoadImageW(None, str(self.icon_path), IMAGE_ICON, size, size, LR_LOADFROMFILE)
        if not self._hicon:
            self._hicon = user32.LoadIconW(None, IDI_APPLICATION)

    def _nid(self, flags: int = 0) -> "NOTIFYICONDATAW":
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = flags
        if flags & NIF_TIP:
            nid.szTip = self._tip or "NOVA AI"
            nid.uFlags |= NIF_SHOWTIP
        return nid

    def _add(self) -> None:
        nid = self._nid(NIF_MESSAGE | NIF_ICON | NIF_TIP)
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self._hicon
        self._tip = "NOVA AI"
        nid.szTip = self._tip
        if not _shell_icon(NIM_ADD, nid):
            raise OSError("Windows no aceptó el icono de la bandeja")
        self._added = True

    def _proc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == WM_TRAY:
                event = lparam & 0xFFFF
                if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    now = time.time()
                    if now - self._last_click > 1.5:  # un doble clic no abre dos ventanas
                        self._last_click = now
                        self._run_default()
                elif event in (WM_RBUTTONUP, WM_CONTEXTMENU):
                    self._menu()
                return 0
            if msg == self._taskbar_created and self._taskbar_created:
                self._added = False  # el Explorador se reinició: hay que volver a poner el icono
                self._add()
                return 0
        except Exception:  # noqa: BLE001
            log.exception("Bandeja")
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _run(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=_safe(fn), daemon=True, name="bandeja-accion").start()

    def _run_default(self) -> None:
        for it in self.items:
            if it.default and it.action:
                self._run(it.action)
                return

    def _menu(self) -> None:
        menu = user32.CreatePopupMenu()
        try:
            for i, it in enumerate(self.items, start=1):
                if it.action is None:
                    user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                    continue
                flags = MF_STRING | (MF_CHECKED if it.checked and it.checked() else 0)
                user32.AppendMenuW(menu, flags, i, it.label())
                if it.default:
                    user32.SetMenuDefaultItem(menu, i, False)
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self._hwnd)  # sin esto el menú no se cierra al pulsar fuera
            cmd = user32.TrackPopupMenu(menu, TPM_RETURNCMD | TPM_NONOTIFY | TPM_RIGHTBUTTON,
                                        pt.x, pt.y, 0, self._hwnd, None)
            user32.PostMessageW(self._hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
        if cmd and 0 < cmd <= len(self.items) and self.items[cmd - 1].action:
            self._run(self.items[cmd - 1].action)


def _safe(fn: Callable[[], None]) -> Callable[[], None]:
    def run() -> None:
        try:
            fn()
        except Exception:  # noqa: BLE001
            log.exception("Acción de la bandeja")
    return run


def focus_window(title_start: str) -> bool:
    """Trae al frente (y restaura si está minimizada) la ventana visible cuyo título empieza así."""
    if not IS_WINDOWS:
        return False
    found = []

    def cb(hwnd, _l):
        if user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if buf.value.startswith(title_start):
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    if not found:
        return False
    hwnd = found[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True


# ===================================================================== Win32 (ctypes)
if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
                    ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                    ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR),
                    ("hIconSm", wintypes.HICON)]

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8)]

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND), ("uID", wintypes.UINT),
                    ("uFlags", wintypes.UINT), ("uCallbackMessage", wintypes.UINT), ("hIcon", wintypes.HICON),
                    ("szTip", wintypes.WCHAR * 128), ("dwState", wintypes.DWORD), ("dwStateMask", wintypes.DWORD),
                    ("szInfo", wintypes.WCHAR * 256), ("uVersion", wintypes.UINT),
                    ("szInfoTitle", wintypes.WCHAR * 64), ("dwInfoFlags", wintypes.DWORD), ("guidItem", GUID),
                    ("hBalloonIcon", wintypes.HICON)]

    class MSG(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("message", wintypes.UINT), ("wParam", wintypes.WPARAM),
                    ("lParam", wintypes.LPARAM), ("time", wintypes.DWORD), ("pt", wintypes.POINT)]

    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
    user32.RegisterClassExW.restype = wintypes.ATOM
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterWindowMessageW.restype = wintypes.UINT
    user32.GetSystemMetrics.argtypes = [ctypes.c_int]
    user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                  wintypes.UINT]
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPVOID]
    user32.LoadIconW.restype = wintypes.HICON
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.SetMenuDefaultItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      wintypes.HWND, wintypes.LPVOID]
    user32.TrackPopupMenu.restype = wintypes.UINT
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PeekMessageW.argtypes = [ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    user32.TranslateMessage.argtypes = [ctypes.POINTER(MSG)]
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE

    WM_NULL, WM_CONTEXTMENU = 0x0000, 0x007B
    WM_LBUTTONUP, WM_LBUTTONDBLCLK, WM_RBUTTONUP = 0x0202, 0x0203, 0x0205
    WM_TRAY = 0x8000 + 1  # WM_APP + 1
    NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
    NIF_MESSAGE, NIF_ICON, NIF_TIP, NIF_INFO, NIF_SHOWTIP = 0x1, 0x2, 0x4, 0x10, 0x80
    NIIF_INFO = 0x1
    MF_STRING, MF_CHECKED, MF_SEPARATOR = 0x0, 0x8, 0x800
    TPM_RIGHTBUTTON, TPM_NONOTIFY, TPM_RETURNCMD = 0x2, 0x80, 0x100
    IMAGE_ICON, LR_LOADFROMFILE, SM_CXSMICON = 1, 0x10, 49
    IDI_APPLICATION = ctypes.c_void_p(32512)
    SW_RESTORE = 9
    PM_REMOVE = 0x1

    def _shell_icon(action: int, nid: "NOTIFYICONDATAW") -> bool:
        return bool(shell32.Shell_NotifyIconW(action, ctypes.byref(nid)))

    def _pump(hwnd) -> None:
        msg = MSG()
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
