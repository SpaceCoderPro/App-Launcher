import customtkinter as CTk
import tkinter as tk
from pynput import keyboard
import os
import glob
import win32gui
import win32con
import win32api
import ctypes
from ctypes import windll

try:
    windll.shcore.SetProcessDpiAwareness(1)
except:
    pass

def get_installed_apps():
    paths = [
        os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ["AppData"], "Microsoft", "Windows", "Start Menu", "Programs")
    ]

    apps = {}

    for path in paths:
        for link in glob.glob(path + "/**/*.lnk", recursive=True):
            name = os.path.basename(link).replace(".lnk", "")
            apps[name] = link

    current_dir = os.path.dirname(os.path.abspath(__file__))
    u = os.path.join(current_dir, "Cook for App/index.py")
    p = os.path.join(current_dir, "Cook for App/puppy.py")

    if os.path.exists(u):
        apps["Run Utilities"] = u
    if os.path.exists(p):
        apps["Puppy Companion"] = p

    return apps

def set_rounded_corners(hwnd, w, h, r=20):
    reg = ctypes.windll.gdi32.CreateRoundRectRgn(0, 0, w + 1, h + 1, r, r)
    ctypes.windll.user32.SetWindowRgn(hwnd, reg, True)

class SearchLauncher:
    def __init__(self, root):
        self.root = root
        self.apps = get_installed_apps()
        self.search_window = None

    def show_window(self):
        if self.search_window and self.search_window.winfo_exists():
            self.search_window.deiconify()
            self.entry.delete(0, tk.END)
            self.update_list()
            self.force_focus(self.search_window)
            return

        self.search_window = CTk.CTkToplevel(self.root)
        self.search_window.overrideredirect(True)
        self.search_window.attributes("-topmost", True)
        self.search_window.attributes("-alpha", 0.95)
        self.search_window.configure(fg_color="#1e1e1e")

        width = 500
        height = 400
        self.search_window.geometry(str(width) + "x" + str(height))
        self.search_window.update()

        self.entry = CTk.CTkEntry(self.search_window,
                                  font=("Segoe UI", 14),
                                  fg_color="#2d2d2d",
                                  text_color="white",
                                  border_color="#484848",
                                  border_width=1)
        self.entry._entry.configure(insertbackground="white")
        self.entry.pack(pady=10, padx=10, fill="x")

        self.listbox = tk.Listbox(self.search_window,
                                  font=("Segoe UI", 12),
                                  bg="#1a1a1a",
                                  fg="white",
                                  selectbackground="#4169E1",
                                  borderwidth=0,
                                  highlightthickness=0)
        self.listbox.pack(pady=5, padx=10, fill="both", expand=True)

        self.entry.bind("<KeyRelease>", self.update_list)
        self.search_window.bind("<Return>", self.launch_selected)
        self.search_window.bind("<Escape>", lambda e: self.search_window.withdraw())
        self.search_window.bind("<FocusOut>", self.on_focus_out)
        self.entry.bind("<Down>", lambda e: self.listbox.focus_set())

        self.update_list()
        self.listbox.bind("<Double-Button-1>", self.launch_selected)
        self.search_window.update()

        pos = win32api.GetCursorPos()
        mon = win32api.MonitorFromPoint(pos, win32con.MONITOR_DEFAULTTONEAREST)
        info = win32api.GetMonitorInfo(mon)
        work = info["Work"]

        sw = work[2] - work[0]
        sh = work[3] - work[1]

        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
        ctypes.windll.user32.ReleaseDC(0, hdc)
        scale = dpi / 96.0

        x = int(work[0] + (sw / 2) - (width * scale / 2))
        y = int(work[1] + (sh / 2) - (height * scale / 2))

        hwnd = int(self.search_window.wm_frame(), 16)
        win32gui.MoveWindow(hwnd, x, y, int(width * scale), int(height * scale), True)

        set_rounded_corners(hwnd, int(width * scale), int(height * scale), 30)

        self.root.after(100, lambda: self.force_focus(self.search_window))

    def force_focus(self, window):
        hwnd = int(window.wm_frame(), 16)
        fg = ctypes.windll.user32.GetForegroundWindow()
        fg_thread = ctypes.windll.user32.GetWindowThreadProcessId(fg, None)
        my_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        ctypes.windll.user32.AttachThreadInput(fg_thread, my_thread, True)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.BringWindowToTop(hwnd)
        ctypes.windll.user32.AttachThreadInput(fg_thread, my_thread, False)
        self.entry.focus_force()

    def update_list(self, event=None):
        text = self.entry.get().lower()
        self.listbox.delete(0, tk.END)
        for name in sorted(self.apps.keys(), key=str.lower):
            if text in name.lower():
                self.listbox.insert(tk.END, name)
        if self.listbox.size() > 0:
            self.listbox.select_set(0)

    def launch_selected(self, event=None):
        sel = self.listbox.curselection()
        if sel:
            name = self.listbox.get(sel)
            path = self.apps[name]
            if name == "Run Utilities" or name == "Puppy Companion":
                os.system('start python "' + path + '"')
            else:
                os.startfile(path)
            self.search_window.withdraw()

    def on_focus_out(self, event):
        if event.widget == self.search_window:
            self.search_window.after(100, self.check_focus)

    def check_focus(self):
        if self.search_window.focus_get() is None:
            self.search_window.withdraw()

main_root = CTk.CTk()
main_root.withdraw()

launcher = SearchLauncher(main_root)

def on_hotkey():
    main_root.after(0, launcher.show_window)

listener = keyboard.GlobalHotKeys({"<alt>+x": on_hotkey})
listener.start()

main_root.mainloop()
