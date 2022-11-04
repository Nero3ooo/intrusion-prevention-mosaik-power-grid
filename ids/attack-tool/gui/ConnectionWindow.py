import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
import rtu_attack_engine
import gui


class ConnectionWindow:
    def __init__(self, master: gui.App):
        self.master = master

        self.window = tk.Toplevel(master.window)
        self.window.transient(master.window)
        self.window.geometry("260x230")
        self.window.resizable(False, False)
        self.window.title("Connect to RTU")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window.focus_set()

        self.path = tk.StringVar(self.window)
        self.ip = tk.StringVar(self.window)
        self.port = tk.StringVar(self.window)
        self.rtu_attack_engine = None

        # INIT PATH LABEL AND ENTRY
        self.label_path = tk.Label(self.window, text="Config Path:")
        self.label_path.place(x=20, y=20)
        self.txt_path = tk.Entry(self.window, width=25)
        self.txt_path.place(x=20, y=40)
        self.txt_path.configure(state='disabled')

        # INIT IP LABEL AND ENTRY
        self.label_ip = tk.Label(self.window, text="IP:")
        self.label_ip.place(x=20, y=80)
        self.txt_ip = tk.Entry(self.window, width=25)
        self.txt_ip.place(x=20, y=100)
        self.txt_ip.configure(state='disabled')

        # INIT PORT LABEL AND ENTRY
        self.label_port = tk.Label(self.window, text="Port:")
        self.label_port.place(x=20, y=120)
        self.txt_port = tk.Entry(self.window, width=25)
        self.txt_port.place(x=20, y=140)
        self.txt_port.configure(state='disabled')

        self.btn_select = tk.Button(self.window, text="Select File", command=self.select_file)
        self.btn_select.place(x=180, y=37)

        self.btn_connect = tk.Button(self.window, text="Connect", command=self.connect)
        self.btn_connect.place(relx=0.5, rely=0.85, anchor=tk.CENTER)
        self.btn_connect.configure(state='disabled')
        self.window.grab_set()

    def select_file(self):
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        self.path = filedialog.askopenfilename(filetypes=[("RTU Config files", "*.xml")])
        try:
            self.window.attributes('-disabled', False)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        if self.path == '':
            messagebox.showerror("Error", "No file location given")
            return
        self.txt_path.configure(state='normal')
        self.txt_path.delete(0, 'end')
        self.txt_path.insert(0, self.path)
        self.txt_path.configure(state='disabled')

        # TODO fehlerbehandlung
        self.rtu_attack_engine = rtu_attack_engine.RTUAttackEngine(self.path)
        self.txt_ip.configure(state='normal')
        self.txt_ip.delete(0, 'end')
        self.txt_ip.insert(0, self.rtu_attack_engine.parser.ip)
        self.txt_ip.configure(state='disabled')
        self.txt_port.configure(state='normal')
        self.txt_port.delete(0, 'end')
        self.txt_port.insert(0, self.rtu_attack_engine.parser.port)
        self.txt_port.configure(state='disabled')

        self.btn_connect.configure(state='normal')

    def connect(self):
        self.master.reactivate_window_and_add_rtu(self.rtu_attack_engine)
        self.window.grab_release()
        self.window.destroy()

    def on_close(self):
        if messagebox.askokcancel("Quit", "Do you want to close the Connection Window?"):
            self.master.reactivate_window_and_add_rtu(None)
            self.window.grab_release()
            self.window.destroy()
