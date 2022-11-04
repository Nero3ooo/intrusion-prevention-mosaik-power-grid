import tkinter as tk
from tkinter import ttk
import gui


class ScenarioWindow:
    def __init__(self, master: gui.App, scenario):
        self.master = master
        self.scenario = scenario

        self.window = tk.Toplevel(master.window)
        self.window.transient(master.window)
        self.window.resizable(False, False)
        self.window.title(f"Manipulations for {self.scenario.name}")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        self.window.focus_set()

        self.manipulation_table_frame = tk.Frame(self.window)
        self.manipulation_table_frame.grid(row=0, column=0, sticky='n, s, e, w', padx=10, pady=10)

        self.manipulation_table_columns = ('rtu', 'component', 'element', 'value', 'delay')
        self.manipulation_table = ttk.Treeview(self.manipulation_table_frame, columns=self.manipulation_table_columns,
                                               show='headings', selectmode="browse")
        self.manipulation_table.column('rtu', anchor=tk.CENTER, width=100)
        self.manipulation_table.column('component', anchor=tk.CENTER, width=120)
        self.manipulation_table.column('element', anchor=tk.CENTER, width=100)
        self.manipulation_table.column('value', anchor=tk.CENTER, width=100)
        self.manipulation_table.column('delay', anchor=tk.CENTER, width=100)
        self.manipulation_table.heading('rtu', text='RTU')
        self.manipulation_table.heading('component', text='Component')
        self.manipulation_table.heading('element', text='Element ID')
        self.manipulation_table.heading('value', text='Value')
        self.manipulation_table.heading('delay', text='Delay')
        self.manipulation_table.pack(expand=True, fill='both', side=tk.LEFT, padx=(10, 0), pady=10)
        self.manipulation_table_scrollbar = ttk.Scrollbar(self.manipulation_table_frame, orient=tk.VERTICAL,
                                                          command=self.manipulation_table.yview)
        self.manipulation_table.configure(yscroll=self.manipulation_table_scrollbar.set)
        self.manipulation_table_scrollbar.pack(expand=False, fill='y', side=tk.RIGHT, padx=(0, 10), pady=10)

        self._read_commands()

    def on_close(self):
        self.master.reactivate_window_and_add_rtu(None)
        self.window.grab_release()
        self.window.destroy()

    def _read_commands(self):
        for command in self.scenario.commands:
            # Get the component from the command type.
            if 'trafo' in command['type']:
                component = 'Transformer'
            elif 'switch' in command['type']:
                component = 'Switch'
            elif 'volt_sensor' in command['type']:
                component = 'Voltage Sensor'
            elif 'max_volt' in command['type']:
                component = 'Max Voltage Sensor'
            elif 'current_sensor' in command['type']:
                component = 'Current Sensor'
            elif 'max_current' in command['type']:
                component = 'Max Current Sensor'
            else:
                component = 'Invalid'

            # Get the IP and port of the RTU for the command.
            rtu_id = command['rtu']
            rtu_dict = self.scenario.rtus[rtu_id]
            rtu = f"{rtu_dict['ip']}:{rtu_dict['port']}"

            # Get the value of the command.
            # As read commands don't contain a value, this would get set to a "-" string instead.
            # However our GUI doesn't support read commands in attack scenarios yet
            # so this would only be important if you would like implement something like that.
            value = command.get('value')
            if value is None:
                value = "-"

            self.manipulation_table.insert(
                "", "end", values=(
                    rtu,
                    component,
                    command['element_id'],
                    value,
                    command['delay']
                )
            )
