import tkinter
import customtkinter as CTk
from customtkinter import CTkScrollableFrame, CTkFrame, CTkLabel, CTkImage
from pynput import keyboard
from PIL import Image
import concurrent.futures
import os
import glob
import win32gui
import win32ui
import win32con
import win32api
import ctypes
from ctypes import windll
import subprocess
import threading
import json
import time
import sys
from rapidfuzz import process, fuzz
import queue
import win32com.shell.shell as shell
import win32com.shell.shellcon as shellcon

try:
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

GRID_COLUMNS = 6
MAX_RESULTS = 25
DEFAULT_TILE_COLOR = "#2d2d2d"
HIGHLIGHT_TILE_COLOR = "#3b82f6"
ICON_CACHE_SIZE = 48
ICON_DISPLAY_SIZE = 36
ICON_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons_cache")

def get_store_apps():
    apps = {}
    try:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "Get-StartApps | Select-Object Name,AppID | ConvertTo-Csv -NoTypeInformation"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().splitlines()
            for line in lines[1:]:
                try:
                    name, appid = [x.strip('"') for x in line.split(",", 1)]
                    if name and appid:
                        apps[name] = {
                            "type": "store",
                            "appid": appid
                        }
                except:
                    pass
    except:
        pass
    return apps

def get_installed_apps():
    cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "apps_cache.json")
    if os.path.exists(cache_file):
        try:
            if time.time() - os.path.getmtime(cache_file) < 3600:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    for name, app in cached.items():
                        yield name, app
                    return
        except:
            pass
    apps = {}
    paths = [
        os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ["AppData"], "Microsoft", "Windows", "Start Menu", "Programs")
    ]
    for path in paths:
        if not os.path.isdir(path):
            continue
        for link in glob.iglob(os.path.join(path, "**", "*.lnk"), recursive=True):
            name = os.path.basename(link)[:-4]
            if name in apps:
                continue
            try:
                import win32com.client
                shell_com = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell_com.CreateShortcut(link)
                target = shortcut.TargetPath
            except Exception:
                continue
            if not target or not os.path.exists(target):
                continue
            app = {"type": "file", "path": target}
            apps[name] = app
            yield name, app
    current_dir = os.path.dirname(os.path.abspath(__file__))
    for name, app in get_store_apps().items():
        if name in apps:
            continue
        apps[name] = app
        yield name, app
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False)
    except:
        pass

def set_rounded_corners(hwnd, w, h, r=20):
    reg = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
    ctypes.windll.user32.SetWindowRgn(hwnd, reg, True)

class SearchLauncher:
    def __init__(self, root):
        self.root = root
        self.apps = {}
        self.sorted_names = []
        self.search_window = None
        self._visible_names = []
        self._update_job = None
        self._apps_ready = False
        self._window_built = False
        self._prev_selected = -1
        self._last_text = None
        self._build_window()
        self._pending_tile_callbacks = {}
        FREQ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "freq_cache.json")
        self.freq_file = FREQ_FILE
        self.open_counts = self._load_freq()
        self.pool = []
        self._visible_names = []
        self._build_pool()
        self._ensure_icon_cache()
        self._icon_queue = queue.Queue()
        self._extracting_icons = set()
        self._icon_executor = concurrent.futures.ThreadPoolExecutor(max_workers=6)
        for _ in range(6):
            self._icon_executor.submit(self._icon_worker_com)
        threading.Thread(target=self._load_apps, daemon=True).start()

    def _load_freq(self):
        if os.path.exists(self.freq_file):
            try:
                with open(self.freq_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _ensure_icon_cache(self):
        if not os.path.exists(ICON_CACHE_DIR):
            os.makedirs(ICON_CACHE_DIR)

    def _get_icon_source(self, name, app):
        if app["type"] == "file":
            return app["path"]
        elif app["type"] == "store":
            return f"shell:AppsFolder\\{app['appid']}"
        elif app["type"] == "python":
            return sys.executable
        return None

    def _extract_icon_file(self, source_path, output_path):
        screen_dc = None
        hdc = None
        hdc2 = None
        hicon = None
        hbmp = None
        try:
            if source_path.startswith("shell:"):
                return self._extract_uwp_icon(source_path, output_path)

            hicon = None
            for idx in range(6):
                try:
                    large, small = win32gui.ExtractIconEx(source_path, idx)
                except Exception:
                    break
                if large and large[0]:
                    hicon = large[0]
                    break

            if not hicon:
                import win32com.shell.shell as shell
                import win32com.shell.shellcon as shellcon

                flags = shellcon.SHGFI_ICON | shellcon.SHGFI_LARGEICON
                info = shell.SHGetFileInfo(source_path, 0, flags)
                if info and info[0]:
                    hicon = info[0]
                else:
                    flags = shellcon.SHGFI_ICON | shellcon.SHGFI_LARGEICON | shellcon.SHGFI_USEFILEATTRIBUTES
                    info = shell.SHGetFileInfo(".exe", shellcon.FILE_ATTRIBUTE_NORMAL, flags)
                    if not info or info[0] == 0:
                        return False
                    hicon = info[0]
            ico_x = ICON_CACHE_SIZE
            ico_y = ICON_CACHE_SIZE
            bmi = ctypes.create_string_buffer(40 + 4)
            ctypes.memset(bmi, 0, 40)
            ctypes.c_uint32.from_buffer(bmi, 0).value = 40
            ctypes.c_int32.from_buffer(bmi, 4).value = ico_x
            ctypes.c_int32.from_buffer(bmi, 8).value = -ico_y
            ctypes.c_uint16.from_buffer(bmi, 12).value = 1
            ctypes.c_uint16.from_buffer(bmi, 14).value = 32
            ctypes.c_uint32.from_buffer(bmi, 16).value = 0
            screen_dc = win32gui.GetDC(0)
            hdc = win32ui.CreateDCFromHandle(screen_dc)
            hdc2 = hdc.CreateCompatibleDC()
            buf = ctypes.c_void_p()
            hbmp_raw = ctypes.windll.gdi32.CreateDIBSection(
                hdc2.GetHandleOutput(), bmi, 0, ctypes.byref(buf), None, 0
            )
            if not hbmp_raw:
                return False
            hbmp = win32ui.CreateBitmapFromHandle(hbmp_raw)
            old_obj = hdc2.SelectObject(hbmp)
            ctypes.windll.user32.DrawIconEx(
                hdc2.GetHandleOutput(), 0, 0, hicon,
                ico_x, ico_y, 0, None, 0x0003
            )
            hdc2.SelectObject(old_obj)
            old_obj = None
            size = ico_x * ico_y * 4
            raw_bits = ctypes.string_at(buf.value, size)
            img = Image.frombuffer('RGBA', (ico_x, ico_y), raw_bits, 'raw', 'BGRA', ico_x * 4, 1)
            img.save(output_path, 'PNG', compress_level=1)
            return True

        except Exception:
            return False
        finally:
            try:
                if 'hbmp' in locals() and hbmp:
                    del hbmp
            except:
                pass
            try:
                if 'old_obj' in locals() and old_obj:
                    hdc2.SelectObject(old_obj)
            except:
                pass
            try:
                hdc2.DeleteDC()
            except:
                pass
            try:
                hdc.DeleteDC()
            except:
                pass
            try:
                if screen_dc:
                    win32gui.ReleaseDC(0, screen_dc)
            except:
                pass
            try:
                if hicon:
                    win32gui.DestroyIcon(hicon)
            except:
                pass

    def _extract_uwp_icon(self, shell_path, output_path):
        hdc = None
        hbitmap = None
        try:
            ole32 = ctypes.windll.ole32
            shell32 = ctypes.windll.shell32
            gdi32 = ctypes.windll.gdi32
            user32 = ctypes.windll.user32

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_uint32),
                    ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            def make_guid(s):
                import uuid
                u = uuid.UUID(s)
                g = GUID()
                g.Data1 = u.time_low
                g.Data2 = u.time_mid
                g.Data3 = u.time_hi_version
                g.Data4[:] = u.bytes[8:]
                return g

            CLSID_IShellItem = make_guid("{43826d1e-e718-42ee-bc55-a1e261c37bfe}")
            IID_IShellItemImageFactory = make_guid("{bcc18b79-ba16-442f-80c4-8a59c30c463b}")
            shell_item = ctypes.c_void_p()
            hr = shell32.SHCreateItemFromParsingName(
                shell_path, None, ctypes.byref(CLSID_IShellItem), ctypes.byref(shell_item)
            )
            if hr != 0 or not shell_item.value:
                return False
            vtbl = ctypes.cast(shell_item, ctypes.POINTER(ctypes.c_void_p))[0]
            query_interface = ctypes.cast(
                ctypes.c_void_p(ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[0]),
                ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
            )
            add_ref = ctypes.cast(
                ctypes.c_void_p(ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[1]),
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            )
            release = ctypes.cast(
                ctypes.c_void_p(ctypes.cast(vtbl, ctypes.POINTER(ctypes.c_void_p))[2]),
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
            )

            img_factory = ctypes.c_void_p()
            hr = query_interface(shell_item, ctypes.byref(IID_IShellItemImageFactory), ctypes.byref(img_factory))
            release(shell_item)
            if hr != 0 or not img_factory.value:
                return False
            vtbl2 = ctypes.cast(img_factory, ctypes.POINTER(ctypes.c_void_p))[0]
            class SIZE(ctypes.Structure):
                _pack_ = 4
                _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

            get_image = ctypes.cast(
                ctypes.c_void_p(ctypes.cast(vtbl2, ctypes.POINTER(ctypes.c_void_p))[3]),
                ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(SIZE), ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))
            )

            size = ICON_CACHE_SIZE
            s = SIZE(size, size)

            SIIGBF_ICONONLY = 0x00000004
            SIIGBF_BIGGERSIZEOK = 0x00000001
            flags = SIIGBF_ICONONLY | SIIGBF_BIGGERSIZEOK

            hbitmap = ctypes.c_void_p()
            hr = get_image(img_factory, ctypes.byref(s), flags, ctypes.byref(hbitmap))
            release(img_factory)
            if hr != 0 or not hbitmap.value:
                return False
            ico_x = size
            ico_y = size

            bmi = ctypes.create_string_buffer(40 + 4)
            ctypes.memset(bmi, 0, 40)
            ctypes.c_uint32.from_buffer(bmi, 0).value = 40
            ctypes.c_int32.from_buffer(bmi, 4).value = ico_x
            ctypes.c_int32.from_buffer(bmi, 8).value = -ico_y
            ctypes.c_uint16.from_buffer(bmi, 12).value = 1
            ctypes.c_uint16.from_buffer(bmi, 14).value = 32
            ctypes.c_uint32.from_buffer(bmi, 16).value = 0

            hdc = user32.GetDC(0)
            pixel_buf = ctypes.create_string_buffer(ico_x * ico_y * 4)
            lines = gdi32.GetDIBits(
                hdc, hbitmap, 0, ico_y,
                pixel_buf, bmi, 0
            )
            user32.ReleaseDC(0, hdc)
            hdc = None

            gdi32.DeleteObject(hbitmap)
            hbitmap = None

            if lines == 0:
                return False

            img = Image.frombuffer(
                'RGBA', (ico_x, ico_y), pixel_buf.raw,
                'raw', 'BGRA', ico_x * 4, 1
            )
            img.save(output_path, 'PNG', compress_level=1)
            return True

        except Exception:
            return False
        finally:
            try:
                if hdc:
                    user32.ReleaseDC(0, hdc)
            except:
                pass
            try:
                if hbitmap:
                    gdi32.DeleteObject(hbitmap)
            except:
                pass

    def _queue_icon_extraction(self, tile, name, app):
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        output_path = os.path.join(ICON_CACHE_DIR, f"{safe_name}.png")
        if os.path.exists(output_path):
            if os.path.getsize(output_path) < 100:
                os.remove(output_path)
            else:
                self.root.after(0, self._apply_icon_to_tile, tile, name, output_path)
                return
        if output_path in self._extracting_icons:
            if tile is not None:
                self._pending_tile_callbacks[output_path] = tile
            return
        source = self._get_icon_source(name, app)
        if not source:
            return
        self._extracting_icons.add(output_path)
        self._icon_queue.put((tile, name, source, output_path))

    def _apply_icon_to_tile(self, tile, expected_name, path):
        if tile.name != expected_name:
            return
        try:
            if os.path.getsize(path) < 100:
                os.remove(path)
                return
            img = Image.open(path)
            if img.size == (0, 0):
                os.remove(path)
                return
            img = Image.open(path)
            img.load()
            ctk_img = CTkImage(img, size=(ICON_DISPLAY_SIZE, ICON_DISPLAY_SIZE))
            tile.icon_label.configure(image=ctk_img, text="")
            tile._icon_ref = ctk_img
        except Exception:
            pass

    def _get_icon_path(self, name):
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        path = os.path.join(ICON_CACHE_DIR, f"{safe_name}.png")
        return path if os.path.exists(path) else None

    def _icon_worker_com(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            self._icon_worker()
        finally:
            pythoncom.CoUninitialize()

    def _icon_worker(self):
        while True:
            try:
                tile, name, source, output_path = self._icon_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            success = self._extract_icon_file(source, output_path)
            if success:
                if tile:
                    self.root.after(
                        0,
                        self._apply_icon_to_tile,
                        tile,
                        name,
                        output_path
                    )
                pending_tile = self._pending_tile_callbacks.pop(output_path, None)
                if pending_tile:
                    self.root.after(
                        0,
                        self._apply_icon_to_tile,
                        pending_tile,
                        name,
                        output_path
                    )
            self._extracting_icons.discard(output_path)
            self._icon_queue.task_done()

    def _save_freq(self):
        try:
            with open(self.freq_file, "w", encoding="utf-8") as f:
                json.dump(self.open_counts, f, ensure_ascii=False)
        except:
            pass

    def record_open(self, name):
        now = time.time()
        if name not in self.open_counts:
            self.open_counts[name] = {"count": 0, "last": 0}
        self.open_counts[name]["count"] += 1
        self.open_counts[name]["last"] = now
        self._save_freq()

    def get_freq_sorted(self):
        scored = []
        for name in self.sorted_names:
            if name in self.open_counts:
                entry = self.open_counts[name]
                scored.append((name, entry["count"], entry["last"]))
            else:
                scored.append((name, 0, 0))
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return [name for name, _, _ in scored]

    class Tile:
        def __init__(self, parent, launcher):
            self.launcher = launcher
            self.frame = CTkFrame(
                parent, width=80, height=80,
                corner_radius=8, fg_color=DEFAULT_TILE_COLOR
            )
            self.frame.grid_propagate(False)
            self.icon_label = CTkLabel(
                self.frame, text="", font=("Segoe UI", 26), text_color="white"
            )
            self.icon_label.pack(pady=(4, 0))
            self.text_label = CTkLabel(
                self.frame, text="", font=("Segoe UI", 10),
                text_color="white", wraplength=72
            )
            self.text_label.pack(pady=(0, 5))
            self.name = None
            self.frame.bind("<Double-Button-1>", self._on_double_click)
            self.frame.bind("<Button-1>", lambda e: launcher.entry.focus_force())

        def set_app(self, name):
            self.name = name
            self.icon_label.configure(image="", text="")
            self._icon_ref = None
            self.text_label.configure(text=name)
            icon_path = self.launcher._get_icon_path(name)
            if icon_path:
                try:
                    ctk_img = CTkImage(Image.open(icon_path), size=(ICON_DISPLAY_SIZE, ICON_DISPLAY_SIZE))
                    self._icon_ref = ctk_img
                    self.icon_label.configure(image=self._icon_ref, text="")
                except:
                    self.icon_label.configure(text="📦")
            else:
                self.icon_label.configure(image="", text="📦")
                self._icon_ref = None

        def clear(self):
            self.name = None
            self.text_label.configure(text="")
            self.icon_label.configure(image="", text="")
            self._icon_ref = None

        def highlight(self, active):
            self.frame.configure(
                fg_color=HIGHLIGHT_TILE_COLOR if active else DEFAULT_TILE_COLOR
            )

        def _on_double_click(self, event):
            if self.name:
                self.launcher.launch_by_name(self.name)

    def _build_pool(self):
        for i in range(18):
            tile = self.Tile(self.scroll_frame, self)
            self.pool.append(tile)

    def _app_added(self, name):
        if not self._window_built:
            return
        if self.search_window.winfo_viewable():
            text = self.entry.get().strip().lower()
            if not text:
                self._do_update()

    def _precache_icons_com(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            self._precache_icons()
        finally:
            pythoncom.CoUninitialize()

    def _precache_icons(self):
        visible_names = set(self.get_freq_sorted()[:50])
        for name, app in self.apps.items():
            if name not in visible_names:
                continue
            self._queue_precache(name, app)
        for name, app in self.apps.items():
            if name in visible_names:
                continue
            self._queue_precache(name, app)

    def _queue_precache(self, name, app):
        safe_name = "".join(
            c for c in name
            if c.isalnum() or c in (' ', '-', '_')
        ).rstrip()
        safe_name = safe_name.replace(' ', '_')
        output_path = os.path.join(
            ICON_CACHE_DIR,
            f"{safe_name}.png"
        )
        if os.path.exists(output_path):
            if os.path.getsize(output_path) < 100:
                os.remove(output_path)
            else:
                return
        source = self._get_icon_source(name, app)
        if not source:
            return
        self._icon_queue.put((None, name, source, output_path))

    def _load_apps(self):
        import pythoncom
        pythoncom.CoInitialize()
        try:
            self._load_apps_impl()
        finally:
            pythoncom.CoUninitialize()

    def _load_apps_impl(self):
        self.apps = {}
        self.sorted_names = []
        self.search_names = []
        self.search_lower = []

        for name, app in get_installed_apps():
            self.apps[name] = app
            self.sorted_names.append(name)
            self.search_lower.append(name.lower())
        self.sorted_names.sort(key=str.casefold)
        self.search_names = self.sorted_names.copy()
        self.search_lower = [n.lower() for n in self.search_names]
        self._apps_ready = True
        threading.Thread(
            target=self._precache_icons_com,
            daemon=True
        ).start()
        self.root.after(0, self._do_update)

    def _build_window(self):
        if self._window_built:
            return
        self._window_built = True

        self.search_window = CTk.CTkToplevel(self.root)
        self.search_window.overrideredirect(True)
        self.search_window.attributes("-topmost", True)
        self.search_window.configure(fg_color="#1e1e1e")
        self.search_window.withdraw()

        width = 500
        height = 280
        self.search_window.geometry(f"{width}x{height}")

        self.entry = CTk.CTkEntry(self.search_window,
                                  font=("Segoe UI", 14),
                                  fg_color="#2d2d2d",
                                  text_color="white",
                                  border_color="#484848",
                                  border_width=1)
        self.entry._entry.configure(insertbackground="white")
        self.entry.pack(pady=10, padx=10, fill="x")

        self.scroll_frame = CTkScrollableFrame(
            self.search_window,
            fg_color="#1a1a1a",
            scrollbar_button_color="#484848",
            scrollbar_fg_color="#2d2d2d"
        )
        canvas = self.scroll_frame._parent_canvas
        canvas.configure(yscrollincrement=20)
        self.scroll_frame.pack(pady=5, padx=10, fill="both", expand=True)
        for i in range(GRID_COLUMNS):
            self.scroll_frame.grid_columnconfigure(i, weight=1, uniform="cols")

        self.selected_index = 0

        self.entry.bind("<KeyRelease>", self._on_key)
        self.search_window.bind("<Return>", self.launch_selected)
        self.search_window.bind("<Escape>", lambda e: self.search_window.withdraw())
        self.search_window.bind("<FocusOut>", self.on_focus_out)
        self.search_window.update_idletasks()
        self.hwnd = int(self.search_window.wm_frame(), 16)
        self.entry.bind("<Down>", lambda e: self.move_highlight(1))
        self.entry.bind("<Up>", lambda e: self.move_highlight(-1))
        self.search_window.bind("<Down>", lambda e: self.move_highlight(1))
        self.search_window.bind("<Up>", lambda e: self.move_highlight(-1))
        self.search_window.bind("<Left>", lambda e: self.move_highlight(-1))
        self.search_window.bind("<Right>", lambda e: self.move_highlight(1))

    def show_window(self):
        if not self._window_built:
            self.root.after(50, self.show_window)
            return

        width = 500
        height = 280
        pos = win32api.GetCursorPos()
        mon = win32api.MonitorFromPoint(pos, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(mon)
        work = info["Work"]
        sw = work[2] - work[0]
        sh = work[3] - work[1]
        if not hasattr(self, "_scale"):
            hdc = ctypes.windll.user32.GetDC(0)
            self._scale = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88) / 96.0
            ctypes.windll.user32.ReleaseDC(0, hdc)
        scale = self._scale
        x = int(work[0] + (sw / 2) - (width * scale / 2))
        y = int(work[1] + (sh / 2) - (height * scale / 2))
        win32gui.MoveWindow(self.hwnd, x, y, int(width * scale), int(height * scale), True)
        if not hasattr(self, "_corners_set"):
            set_rounded_corners(self.hwnd, int(width * scale), int(height * scale), 30)
            self._corners_set = True

        self.search_window.deiconify()
        self.search_window.attributes("-alpha", 0.95)
        self.entry.delete(0, "end")
        self._last_text = None
        self._do_update()
        self.force_focus(self.search_window)

    def _on_key(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Escape"):
            return
        self.update_list()

    def force_focus(self, window):
        hwnd = self.hwnd
        fg = ctypes.windll.user32.GetForegroundWindow()
        fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
        my_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        ctypes.windll.user32.AttachThreadInput(fg_thread, my_thread, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.BringWindowToTop(hwnd)
        ctypes.windll.user32.AttachThreadInput(fg_thread, my_thread, False)
        self.entry.focus_force()

    def update_list(self, event=None):
        self._do_update()

    def _do_update(self):
        text = self.entry.get().strip().lower()

        if not text:
            names = self.get_freq_sorted()[:18]
        else:
            results = process.extract(
                text,
                self.search_lower,
                scorer=fuzz.WRatio,
                limit=18
            )
            names = [
                self.search_names[idx]
                for _, score, idx in results
                if score >= 60
            ]

        self._visible_names = names
        for i, tile in enumerate(self.pool):
            if i < len(names):
                tile.set_app(names[i])
                tile.frame.grid(row=i // 6, column=i % 6, padx=2, pady=2, sticky="nsew")
            else:
                tile.clear()
                tile.frame.grid_forget()

        self._prev_selected = -1
        self.selected_index = 0
        if names:
            self.highlight_tile(0)

    def launch_selected(self, event=None):
        if not self._visible_names:
                return "break"
        index = self.selected_index if 0 <= self.selected_index < len(self._visible_names) else 0
        name = self._visible_names[index]
        self.record_open(name)
        self.launch_by_name(name)
        return "break"

    def on_focus_out(self, event):
        if event.widget == self.search_window:
            self.search_window.after(100, self.check_focus)

    def check_focus(self):
        if self.search_window.focus_get() is None:
            self.search_window.withdraw()

    def highlight_tile(self, index):
        prev = self._prev_selected
        if prev == index:
            return
        if 0 <= prev < len(self._visible_names):
            self.pool[prev].highlight(False)
        if 0 <= index < len(self._visible_names):
            self.pool[index].highlight(True)
        self._prev_selected = index
        self.selected_index = index

    def move_highlight(self, direction):
        total = len(self._visible_names)
        if not total:
            return "break"

        current = self.selected_index
        row, col = divmod(current, 6)

        if direction == "left":
            new_index = current - 1 if col > 0 else current
        elif direction == "right":
            new_index = current + 1 if col < 5 and current < total - 1 else current
        elif direction == "up":
            new_index = current - 6 if row > 0 else current
        elif direction == "down":
            new_index = current + 6 if current + 6 < total else total - 1
        else:
            return "break"

        self.highlight_tile(new_index)
        return "break"

    def launch_by_name(self, name):
        app = self.apps.get(name)
        if app is None:
            return
        if app["type"] == "store":
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['appid']}"])
        elif app["type"] == "file":
            os.startfile(app["path"])
        elif app["type"] == "python":
            subprocess.Popen([sys.executable, app["path"]], cwd=os.path.dirname(app["path"]))
        self.search_window.withdraw()

main_root = CTk.CTk()
main_root.withdraw()
launcher = SearchLauncher(main_root)

def on_hotkey():
    main_root.after(0, launcher.show_window)

listener = keyboard.GlobalHotKeys({"<alt>+x": on_hotkey})
listener.start()
main_root.mainloop()
