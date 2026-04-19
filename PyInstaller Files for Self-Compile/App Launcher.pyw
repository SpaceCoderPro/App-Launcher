import tkinter as tk
from pynput import keyboard
import os
import glob
import win32gui
import win32con
import win32com.client
import subprocess
import sys

def get_installed_apps():
    paths = [
        os.path.join(os.environ["ProgramData"], "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(os.environ["AppData"], "Microsoft", "Windows", "Start Menu", "Programs")
    ]
    
    found_apps = {}
    for path in paths:
        for link in glob.glob(path + "/**/*.lnk", recursive=True):
            name = os.path.basename(link).replace(".lnk", "")
            found_apps[name] = link
            
    current_dir = os.path.dirname(sys.executable)
    puppy_path = os.path.join(current_dir, "puppy.exe")
    utils_path = os.path.join(current_dir, "index.exe")
    if os.path.exists(utils_path):
        found_apps["Run Utilities"] = utils_path
    if os.path.exists(puppy_path):
        found_apps["Puppy Companion"] = puppy_path
        
    return found_apps

class SearchLauncher:
    def __init__(self, root):
        self.root = root
        self.apps = get_installed_apps()
        self.search_window = None

    def show_window(self):
        if self.search_window and self.search_window.winfo_exists():
            self.search_window.deiconify()
            self.force_focus(self.search_window)
            return

        self.search_window = tk.Toplevel(self.root)
        self.search_window.title("Quick Search")
        self.search_window.geometry("450x320")
        self.search_window.configure(bg="#2d2d2d")
        self.search_window.attributes("-topmost", True)
        
        self.entry = tk.Entry(self.search_window, font=("Segoe UI", 14), bg="#3d3d3d", fg="white", insertbackground="white")
        self.entry.pack(pady=10, padx=10, fill='x')
        
        self.listbox = tk.Listbox(self.search_window, font=("Segoe UI", 12), bg="#2d2d2d", fg="white", 
                                  selectbackground="#0078d7", borderwidth=0, highlightthickness=0)
        self.listbox.pack(pady=5, padx=10, fill='both', expand=True)
        
        self.entry.bind("<KeyRelease>", self.update_list)
        self.search_window.bind("<Return>", self.launch_selected)
        self.search_window.bind("<Escape>", lambda e: self.search_window.withdraw())
        self.entry.bind("<Down>", lambda e: self.listbox.focus_set())

        self.update_list()
        self.root.after(100, lambda: self.force_focus(self.search_window))

    def force_focus(self, window):
        hwnd = window.winfo_id()
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys('{ESC}')
        shell.SendKeys('%')
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        try: 
            win32gui.SetForegroundWindow(hwnd)
        except: 
            pass
        self.entry.focus_force()

    def update_list(self, event=None):
        search_term = self.entry.get().lower()
        self.listbox.delete(0, tk.END)
        for name in sorted(self.apps.keys(), key=str.lower):
            if search_term in name.lower():
                self.listbox.insert(tk.END, name)
        if self.listbox.size() > 0:
            self.listbox.select_set(0)

    def launch_selected(self, event=None):
        selection = self.listbox.curselection()
        if selection:
            app_name = self.listbox.get(selection)
            path = self.apps[app_name]
            if app_name == "Run Utilities" or app_name == "Puppy Companion":
                subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                os.startfile(path)
            self.search_window.withdraw() 

main_root = tk.Tk()
main_root.withdraw() 
launcher = SearchLauncher(main_root)

def on_hotkey():
    main_root.after(0, launcher.show_window)

listener = keyboard.GlobalHotKeys({'<alt>+x': on_hotkey})
listener.start()

main_root.mainloop()
