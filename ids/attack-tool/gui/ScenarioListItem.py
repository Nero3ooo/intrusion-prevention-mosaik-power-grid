import tkinter as tk


class ScenarioListItem:
    def __init__(self, scenario, path, check_button: tk.Checkbutton, remove_button: tk.Button,
                 save_button: tk.Button, var):
        self.scenario = scenario
        self.path = path
        self.check_button = check_button
        self.remove_button = remove_button
        self.save_button = save_button
        self.var = var
