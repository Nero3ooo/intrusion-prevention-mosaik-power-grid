import tkinter as tk


class RTUChecklistItem:
    def __init__(self, attack_engine, check_button: tk.Checkbutton, remove_button: tk.Button, var):
        self.attack_engine = attack_engine
        self.check_button = check_button
        self.remove_button = remove_button
        self.var = var
