import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import os
import threading
import time
import queue
import gui
import attack_scenario

# variable values are refreshed every VARIABLE_REFRESH_INTERVAL ms if any have been fetched
VARIABLE_REFRESH_INTERVAL = 6000
# dedicated thread fetches the variable values if the previously fetched values have already
# been refreshed every FETCHING_INTERVAL ms
FETCHING_INTERVAL = 5000


class App:
    def __init__(self):
        # create array of rtu checklist items (one for each connected rtu)
        # items contain:
        #   rtu attack engine
        #   checkbutton for display settings
        #   button to disconnect
        #   variable for checkbutton
        self.rtu_checklist_items = []
        # counter for placing rtus in rtu checklist
        self.next_rtu_checklist_item_in_row = 0

        self.scenario_list_items = []
        self.next_scenario_list_item_in_row = 0
        self.current_scenario = attack_scenario.AttackScenario()

        # create main window
        self.window = tk.Tk()
        self.window.title("Attack Manager")
        self.window.geometry("960x540")
        self.window.minsize(960, 540)
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # preparing images for display settings
        self.image_eye_open = tk.PhotoImage(file='./assets/eye_open.png')
        self.image_eye_closed = tk.PhotoImage(file='./assets/eye_closed.png')

        # create frames and lay them out in the main window
        self.left_frame = tk.Frame(self.window)
        self.display_frame = tk.LabelFrame(self.window, text=" Display ", height=50)
        self.variable_frame = tk.LabelFrame(self.window, text=" Variables ")
        self.manipulate_frame = tk.LabelFrame(self.window, text=" Manipulate Variable ")
        self.button_frame = tk.Frame(self.window)
        self.left_frame.grid(row=0, column=0, sticky='n, s, w', padx=(10, 5), pady=10, rowspan=4)
        self.display_frame.grid(row=0, column=1, sticky='n, e, w', padx=(5, 10), pady=10)
        self.variable_frame.grid(row=1, column=1, sticky='n, s, e, w', padx=(5, 10), pady=(5, 10))
        self.manipulate_frame.grid(row=2, column=1, sticky='s, e, w', padx=(5, 10), pady=5)
        self.button_frame.grid(row=3, column=1, sticky='s, w, e', padx=(5, 10), pady=10)
        self.window.grid_columnconfigure(0, minsize=100, weight=0)
        self.window.grid_columnconfigure(1, minsize=200, weight=1)
        self.window.grid_rowconfigure(0, weight=0)
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_rowconfigure(2, weight=0)
        self.window.grid_rowconfigure(3, weight=0)

        self.rtu_frame = tk.LabelFrame(self.left_frame, text=" RTUs ", width=200)
        self.scenario_frame = tk.LabelFrame(self.left_frame, text=" Scenarios ", width=230)
        self.rtu_frame.grid(row=0, column=0, sticky='n, s, w', pady=(0, 10))
        self.scenario_frame.grid(row=1, column=0, sticky='n, s, w')
        self.left_frame.rowconfigure(0, weight=1)
        self.left_frame.rowconfigure(1, weight=1)

        # rtu frame content
        self.rtu_list = tk.Frame(self.rtu_frame)
        self.rtu_list.grid(row=0, sticky='n,e,w', pady=(5, 0))
        self.rtu_button = tk.Button(self.rtu_frame, text="Add RTU", command=self.open_connection_window, width=31)
        self.rtu_button.grid(row=1, sticky='s,e,w')
        self.rtu_frame.rowconfigure(0, weight=1)

        # scenario frame content
        self.scenario_list = tk.Frame(self.scenario_frame)
        self.scenario_list.grid(row=0, sticky='n,e,w', pady=(5, 0))
        self.scenario_create_button = tk.Button(self.scenario_frame, text="Create new scenario",
                                                command=self.create_scenario, width=31)
        self.scenario_create_button.grid(row=1, sticky='s,e,w')
        self.scenario_load_button = tk.Button(self.scenario_frame, text="Load scenario", command=self.load_scenario,
                                              width=31)
        self.scenario_load_button.grid(row=2, sticky='s,e,w')
        self.scenario_frame.rowconfigure(0, weight=1)

        # display frame content
        self.display_switches_value = tk.BooleanVar()
        self.display_switches_value.set(True)
        self.display_switches_button = tk.Checkbutton(
            self.display_frame,
            var=self.display_switches_value,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  Switches",
            anchor="w",
            compound="left",
            width=150,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=self.refresh_variables_to_display
        )
        self.display_transformers_value = tk.BooleanVar()
        self.display_transformers_value.set(True)
        self.display_transformers_button = tk.Checkbutton(
            self.display_frame,
            var=self.display_transformers_value,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  Transformers",
            anchor="w",
            compound="left",
            width=150,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=self.refresh_variables_to_display
        )
        self.display_current_value = tk.BooleanVar()
        self.display_current_value.set(True)
        self.display_current_button = tk.Checkbutton(
            self.display_frame,
            var=self.display_current_value,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  Current Sensors",
            anchor="w",
            compound="left",
            width=150,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=self.refresh_variables_to_display
        )
        self.display_voltage_value = tk.BooleanVar()
        self.display_voltage_value.set(True)
        self.display_voltage_button = tk.Checkbutton(
            self.display_frame,
            var=self.display_voltage_value,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  Voltage Sensors",
            anchor="w",
            compound="left",
            width=150,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=self.refresh_variables_to_display
        )
        self.display_switches_button.grid(row=0, column=0, padx=(10, 5), pady=(2, 5))
        self.display_transformers_button.grid(row=0, column=1, padx=5, pady=(2, 5))
        self.display_current_button.grid(row=0, column=2, padx=5, pady=(2, 5))
        self.display_voltage_button.grid(row=0, column=3, padx=5, pady=(2, 5))

        # variable table content
        self.variable_table_columns = ('rtu_name', 'component', 'element', 'value', 'max_value')
        self.variable_table = ttk.Treeview(self.variable_frame, columns=self.variable_table_columns, show='headings',
                                           selectmode="browse")
        self.variable_table.bind("<<TreeviewSelect>>", self.select_variable_for_manipulation)
        self.variable_table.column('rtu_name', anchor=tk.CENTER, width=100)
        self.variable_table.column('component', anchor=tk.CENTER, width=100)
        self.variable_table.column('element', anchor=tk.CENTER, width=100)
        self.variable_table.column('value', anchor=tk.CENTER, width=100)
        self.variable_table.column('max_value', anchor=tk.CENTER, width=100)
        self.variable_table.heading('rtu_name', text='RTU')
        self.variable_table.heading('component', text='Component')
        self.variable_table.heading('element', text='Element ID')
        self.variable_table.heading('value', text='Value')
        self.variable_table.heading('max_value', text='Max Value')
        self.variable_table.pack(expand=True, fill='both', side=tk.LEFT, padx=(10, 0), pady=(5, 10))
        self.variable_table_scrollbar = ttk.Scrollbar(self.variable_frame, orient=tk.VERTICAL,
                                                      command=self.variable_table.yview)
        self.variable_table.configure(yscroll=self.variable_table_scrollbar.set)
        self.variable_table_scrollbar.pack(expand=False, fill='y', side=tk.RIGHT, padx=(0, 10), pady=(5, 10))

        # manipulation frame content
        self.name_label = tk.Label(self.manipulate_frame, text="Name:")
        self.name_entry = tk.Entry(self.manipulate_frame, width=18)
        self.name_entry.configure(state='disabled')
        self.new_value_label = tk.Label(self.manipulate_frame, text="New Value:")
        self.new_value_entry = tk.Entry(self.manipulate_frame, width=12)
        self.new_value_entry.configure(state='disabled')
        self.delay_label = tk.Label(self.manipulate_frame, text="Delay:")
        self.delay_entry = tk.Entry(self.manipulate_frame, width=12)
        self.delay_entry.configure(state='disabled')
        self.manipulate_button = tk.Button(self.manipulate_frame, text="Add Manipulation", width=18,
                                           command=self.add_manipulation)
        self.manipulate_button.configure(state='disabled')
        self.manipulate_max_value = tk.BooleanVar()
        self.manipulate_max_value.set(False)
        self.manipulate_max_button = tk.Checkbutton(
            self.manipulate_frame,
            var=self.manipulate_max_value,
            indicatoron=False,
            text="  Max Value  ",
            anchor="w",
            compound="left",
            relief="flat",
            highlightthickness=0,
            command=self.select_variable_for_manipulation
        )
        self.manipulate_max_button.configure(state='disabled')
        self.name_label.grid(row=0, column=0, padx=(5, 0), pady=5)
        self.name_entry.grid(row=0, column=1, padx=5, pady=5)
        self.manipulate_max_button.grid(row=0, column=2, padx=5, pady=5)
        self.new_value_label.grid(row=0, column=3, padx=(5, 0), pady=5)
        self.new_value_entry.grid(row=0, column=4, padx=5, pady=5)
        self.delay_label.grid(row=0, column=5, padx=(5, 0), pady=5)
        self.delay_entry.grid(row=0, column=6, padx=5, pady=5)
        self.manipulate_button.grid(row=0, column=7, padx=5, pady=5, sticky='w')

        self.manipulation_table_frame = tk.Frame(self.manipulate_frame)
        self.manipulation_table_columns = ('value', 'delay')
        self.manipulation_table = ttk.Treeview(self.manipulation_table_frame, columns=self.manipulation_table_columns,
                                               show='headings', selectmode="browse", height=5)
        self.manipulation_table.bind("<<TreeviewSelect>>", self.select_manipulation)
        self.manipulation_table.column('value', anchor=tk.CENTER, width=230)
        self.manipulation_table.column('delay', anchor=tk.CENTER, width=230)
        self.manipulation_table.heading('value', text='Value')
        self.manipulation_table.heading('delay', text='Delay')
        self.manipulation_table.pack(expand=True, fill='both', side=tk.LEFT)
        self.manipulation_table_scrollbar = ttk.Scrollbar(self.manipulation_table_frame, orient=tk.VERTICAL,
                                                          command=self.manipulation_table.yview)
        self.manipulation_table.configure(yscroll=self.manipulation_table_scrollbar.set)
        self.manipulation_table_scrollbar.pack(expand=False, fill='y', side=tk.RIGHT)

        self.remove_manipulation_button = tk.Button(self.manipulate_frame, text="Remove Manipulation", width=18,
                                                    command=self.remove_manipulation)
        self.remove_manipulation_button.configure(state='disabled')

        self.manipulation_table_frame.grid(row=1, column=0, padx=5, pady=10, sticky='n,s', columnspan=7)
        self.remove_manipulation_button.grid(row=1, column=7, padx=5, pady=5, sticky='w')
        self.manipulate_frame.grid_rowconfigure(0, weight=0)
        self.manipulate_frame.grid_rowconfigure(1, weight=1)
        self.manipulate_frame.grid_rowconfigure(2, weight=2)

        # button frame content
        self.run_attack_button = tk.Button(self.button_frame, text="Run Attack", command=self.run_attack)
        self.run_attack_button.grid(row=0, column=0, sticky='n,w', padx=5)
        self.reset_all_button = tk.Button(self.button_frame, text="Reset All Variables", command=self.reset_all)
        self.reset_all_button.grid(row=0, column=1, sticky='n,e', padx=5)
        self.show_manipluations_button = tk.Button(self.button_frame, text="Show All Manipulations",
                                                   command=lambda: self.open_scenario_window(self.current_scenario))
        self.show_manipluations_button.grid(row=0, column=2, sticky='n,e', padx=(5, 50))
        self.quit_button = tk.Button(self.button_frame, text="Quit", command=self.on_close)
        self.quit_button.grid(row=0, column=3, sticky='n,e', padx=5)
        self.button_frame.columnconfigure(3, weight=1)

        # create a queue for the fetched variable values (python queues are thread safe!)
        self.fetched_values = queue.Queue()
        self.currently_fetching = True
        self.currently_disconnecting = False
        # create and start a thread for fetching variable values
        self.thread = threading.Thread(target=self.fetch_variable_values, daemon=True)
        self.thread.start()
        # refresh the fetched values in the variable table
        # automatically runs again after VARIABLE_REFRESH_INTERVAL ms if there are no (more) values in the queue
        self.refresh_variable_values()

        self.window.mainloop()

    # disables the main window and opens the connection window
    def open_connection_window(self):
        self.rtu_button.configure(state='disabled')
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        gui.ConnectionWindow(self)

    # opens the scenario window
    def open_scenario_window(self, scenario):
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        gui.ScenarioWindow(self, scenario)

    # adds the variables from a given rtu attack engine to the table of variables
    # displays new variables according to display settings
    def add_variables_from_rtu_to_table(self, attack_engine):
        for var in attack_engine.get_switches():
            self.variable_table.insert(
                "", "end", App._get_variable_identifier(attack_engine, var, "Switch"), text="Name", values=(
                    attack_engine.get_address(),
                    "Switch",
                    var['index'],
                    "-",
                    "-"
                )
            )
        for var in attack_engine.get_transformers():
            self.variable_table.insert(
                "", "end", App._get_variable_identifier(attack_engine, var, "Transformer"), values=(
                    attack_engine.get_address(),
                    "Transformer",
                    var['index'],
                    "-",
                    "-"
                )
            )
        for var in attack_engine.get_current_sensors():
            self.variable_table.insert(
                "", "end", App._get_variable_identifier(attack_engine, var, "Current Sensor"), values=(
                    attack_engine.get_address(),
                    "Current Sensor",
                    var['index'],
                    "-",
                    "-"
                )
            )
        for var in attack_engine.get_voltage_sensors():
            self.variable_table.insert(
                "", "end", App._get_variable_identifier(attack_engine, var, "Voltage Sensor"), values=(
                    attack_engine.get_address(),
                    "Voltage Sensor",
                    var['index'],
                    "-",
                    "-"
                )
            )
        self.refresh_variables_to_display()

    # refreshes the displayed variables according to display settings
    # called when changing the state of any display checkbutton or when adding a new rtu
    def refresh_variables_to_display(self):
        for item in self.rtu_checklist_items:
            if self.display_switches_value.get() and item.var.get():
                for var in item.attack_engine.get_switches():
                    self.variable_table.move(App._get_variable_identifier(item.attack_engine, var, "Switch"), "", "end")
            else:
                for var in item.attack_engine.get_switches():
                    self.variable_table.detach(App._get_variable_identifier(item.attack_engine, var, "Switch"))
            if self.display_transformers_value.get() and item.var.get():
                for var in item.attack_engine.get_transformers():
                    self.variable_table.move(App._get_variable_identifier(item.attack_engine, var, "Transformer"), "",
                                             "end")
            else:
                for var in item.attack_engine.get_transformers():
                    self.variable_table.detach(App._get_variable_identifier(item.attack_engine, var, "Transformer"))
            if self.display_current_value.get() and item.var.get():
                for var in item.attack_engine.get_current_sensors():
                    self.variable_table.move(App._get_variable_identifier(item.attack_engine, var, "Current Sensor"),
                                             "", "end")
            else:
                for var in item.attack_engine.get_current_sensors():
                    self.variable_table.detach(App._get_variable_identifier(item.attack_engine, var, "Current Sensor"))
            if self.display_voltage_value.get() and item.var.get():
                for var in item.attack_engine.get_voltage_sensors():
                    self.variable_table.move(App._get_variable_identifier(item.attack_engine, var, "Voltage Sensor"),
                                             "", "end")
            else:
                for var in item.attack_engine.get_voltage_sensors():
                    self.variable_table.detach(App._get_variable_identifier(item.attack_engine, var, "Voltage Sensor"))

    # refreshes the values of every variable
    def refresh_variable_values(self):
        # empty() being true does not guarantee that a subsequent get() won't block since another thread could
        # have emptied the queue in the meantime
        # => if get(block=False) throws the Empty exception, stop trying to get values
        while not self.fetched_values.empty():
            try:
                temp = self.fetched_values.get(block=False)
                # only use the fetched value when still fetching values
                # if not, discard it since it could belong to an rtu that has already been disconnected
                if self.currently_fetching:
                    if temp[2]:
                        self.variable_table.set(temp[0], "max_value", temp[1])
                    else:
                        self.variable_table.set(temp[0], "value", temp[1])
            except queue.Empty:
                break
        self.window.after(VARIABLE_REFRESH_INTERVAL, self.refresh_variable_values)

    # fetches the variable values if the previously fetched values have already been used every FETCHING_INTERVAL ms
    # constantly running in the background on a dedicated thread
    def fetch_variable_values(self):
        while 1:
            if not self.currently_fetching and not self.currently_disconnecting:
                # discard fetched values if fetching has stopped since some of them might be from an rtu that has
                # been disconnected
                while not self.fetched_values.empty():
                    try:
                        self.fetched_values.get(block=False)
                    except queue.Empty:
                        break
                # restart fetching if not in the process of disconnecting from an rtu anymore
                self.currently_fetching = True
            if self.currently_fetching and self.fetched_values.empty():
                self._fetch_variable_values_internal()
            time.sleep(FETCHING_INTERVAL / 1000)

    # since fetching values might take a lot of time:
    #   - check if still fetching before fetching a value (stopped when disconnecting from rtu)
    #   - check if the rtu/variable type should (still) be displayed before fetching a value
    def _fetch_variable_values_internal(self):
        for item in self.rtu_checklist_items:
            for var in item.attack_engine.get_switches():
                if not self.currently_fetching:
                    return
                if not self.display_switches_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Switch"),
                     item.attack_engine.read_switch(var['index']),
                     False]
                )
            for var in item.attack_engine.get_transformers():
                if not self.currently_fetching:
                    return
                if not self.display_transformers_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Transformer"),
                     item.attack_engine.read_trafo(var['index']),
                     False]
                )
            for var in item.attack_engine.get_current_sensors():
                if not self.currently_fetching:
                    return
                if not self.display_current_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Current Sensor"),
                     round(item.attack_engine.read_current_sensor(var['index']), 5),
                     False]
                )
                if not self.currently_fetching:
                    return
                if not self.display_voltage_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Current Sensor"),
                     round(item.attack_engine.read_max_current(var['index']), 5),
                     True]
                )
            for var in item.attack_engine.get_voltage_sensors():
                if not self.currently_fetching:
                    return
                if not self.display_voltage_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Voltage Sensor"),
                     round(item.attack_engine.read_volt_sensor(var['index']), 5),
                     False]
                )
                if not self.currently_fetching:
                    return
                if not self.display_voltage_value.get() or not item.var.get():
                    break
                self.fetched_values.put(
                    [App._get_variable_identifier(item.attack_engine, var, "Voltage Sensor"),
                     round(item.attack_engine.read_max_volt(var['index']), 5),
                     True]
                )

    def add_manipulation(self):
        command, var, rtu_info = self._get_info_for_selected_variable()
        self.current_scenario.add_command(
            rtu_info, command, var['index'], float(self.new_value_entry.get()), int(self.delay_entry.get())
        )
        self.select_variable_for_manipulation()

    def remove_manipulation(self):
        command, var, rtu_info = self._get_info_for_selected_variable()
        selected_manipulation = self.manipulation_table.item(self.manipulation_table.selection()[0], "values")
        self.current_scenario.delete_command(
            rtu_info, command, var['index'], float(selected_manipulation[0]), int(selected_manipulation[1])
        )
        self.select_variable_for_manipulation()

    # changes the selected variable for manipulation
    # automatically called when selecting an item in the variable table
    def select_variable_for_manipulation(self, event=None):
        self.remove_manipulation_button.configure(state='disabled')
        if not self.variable_table.selection():
            return
        for item in self.variable_table.selection():
            component = self.variable_table.item(item, "values")[1]
            if component == 'Transformer' or component == 'Switch':
                self.manipulate_max_button.configure(state='disabled')
            else:
                self.manipulate_max_button.configure(state='normal')
        self.manipulate_button.configure(state='normal')
        self.new_value_entry.configure(state='normal')
        self.new_value_entry.delete(0, 'end')
        self.name_entry.configure(state='normal')
        self.name_entry.delete(0, 'end')
        self.delay_entry.configure(state='normal')
        self.delay_entry.delete(0, 'end')
        for item in self.variable_table.selection():
            self.name_entry.insert(0, self.variable_table.item(item, "values")[1] + " " +
                                   self.variable_table.item(item, "values")[2])
        self.name_entry.configure(state='disabled')
        for item in self.manipulation_table.get_children():
            self.manipulation_table.delete(item)
        command, var, rtu_info = self._get_info_for_selected_variable()
        for manipulation in self.current_scenario.commands:
            if (manipulation['type'] == command and
                    manipulation['rtu'] == self.current_scenario.rtus.index(rtu_info) and
                    manipulation['element_id'] == var['index']):
                self.manipulation_table.insert(
                    "", "end", values=(
                        manipulation['value'],
                        manipulation['delay']
                    )
                )

    def select_manipulation(self, event=None):
        self.remove_manipulation_button.configure(state='normal')

    def _get_info_for_selected_variable(self):
        for selected in self.variable_table.selection():
            for item in self.rtu_checklist_items:
                for var in item.attack_engine.get_switches():
                    if selected == App._get_variable_identifier(item.attack_engine, var, "Switch"):
                        rtu_info = {'ip': item.attack_engine.get_ip(), 'port': item.attack_engine.get_port()}
                        return "write_switch", var, rtu_info
                for var in item.attack_engine.get_transformers():
                    if selected == App._get_variable_identifier(item.attack_engine, var, "Transformer"):
                        rtu_info = {'ip': item.attack_engine.get_ip(), 'port': item.attack_engine.get_port()}
                        return "write_trafo", var, rtu_info
                for var in item.attack_engine.get_current_sensors():
                    if selected == App._get_variable_identifier(item.attack_engine, var, "Current Sensor"):
                        rtu_info = {'ip': item.attack_engine.get_ip(), 'port': item.attack_engine.get_port()}
                        command = "write_max_current" if self.manipulate_max_value.get() else "write_current_sensor"
                        return command, var, rtu_info
                for var in item.attack_engine.get_voltage_sensors():
                    if selected == App._get_variable_identifier(item.attack_engine, var, "Voltage Sensor"):
                        rtu_info = {'ip': item.attack_engine.get_ip(), 'port': item.attack_engine.get_port()}
                        command = "write_max_volt" if self.manipulate_max_value.get() else "write_volt_sensor"
                        return command, var, rtu_info

    # resets the manipulation frame to its initial state
    # TODO call when disconnecting from the rtu the selected variable belongs to
    def reset_manipulation_frame(self):
        self.manipulate_button.configure(state='disabled')
        self.new_value_entry.configure(state='normal')
        self.new_value_entry.delete(0, 'end')
        self.new_value_entry.configure(state='disabled')
        self.name_entry.configure(state='normal')
        self.name_entry.delete(0, 'end')
        self.name_entry.configure(state='disabled')
        self.delay_entry.configure(state='normal')
        self.delay_entry.delete(0, 'end')
        self.delay_entry.configure(state='disabled')

    # reactivates this window and adds rtu if given by parameter
    # to be called by connection window
    def reactivate_window_and_add_rtu(self, attack_engine):
        self.rtu_button.configure(state='normal')
        try:
            self.window.attributes('-disabled', False)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        if attack_engine is None:
            return
        for item in self.rtu_checklist_items:
            if item.attack_engine.get_address() == attack_engine.get_address():
                messagebox.showerror("Error", "Already connected to " + attack_engine.get_address())
                return
        var = tk.StringVar(value=attack_engine.get_address())
        check_button = tk.Checkbutton(
            self.rtu_list,
            var=var,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  " + attack_engine.get_address(),
            onvalue=attack_engine.get_address(),
            offvalue="",
            anchor="w",
            compound="left",
            width=146,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=self.refresh_variables_to_display
        )
        remove_button = tk.Button(
            self.rtu_list,
            text="Disconnect",
            width=9,
            command=lambda: self.disconnect_rtu(attack_engine)
        )
        self.rtu_checklist_items.append(gui.RTUChecklistItem(attack_engine, check_button, remove_button, var))
        check_button.grid(row=self.next_rtu_checklist_item_in_row, column=0)
        remove_button.grid(row=self.next_rtu_checklist_item_in_row, column=1)
        self.next_rtu_checklist_item_in_row += 1
        self.add_variables_from_rtu_to_table(attack_engine)

    # disconnects a given rtu
    # called by pushing the corresponding disconnect button
    def disconnect_rtu(self, attack_engine):
        if messagebox.askyesno("Disconnect",
                               "Do you really want to disconnect from " + attack_engine.get_address() + "?"):
            self.currently_disconnecting = True
            self.currently_fetching = False
            for item in self.rtu_checklist_items:
                if attack_engine == item.attack_engine:
                    item.check_button.grid_forget()
                    item.remove_button.grid_forget()
                    self.rtu_checklist_items.remove(item)
            for var in attack_engine.get_switches():
                self.variable_table.delete(App._get_variable_identifier(attack_engine, var, "Switch"))
            for var in attack_engine.get_transformers():
                self.variable_table.delete(App._get_variable_identifier(attack_engine, var, "Transformer"))
            for var in attack_engine.get_current_sensors():
                self.variable_table.delete(App._get_variable_identifier(attack_engine, var, "Current Sensor"))
            for var in attack_engine.get_voltage_sensors():
                self.variable_table.delete(App._get_variable_identifier(attack_engine, var, "Voltage Sensor"))
            self.currently_disconnecting = False

    @staticmethod
    def _get_variable_identifier(attack_engine, var, component_type):
        return attack_engine.get_address() + " " + component_type + " " + str(var['index'])

    def save_scenario(self, scenario):
        if messagebox.askyesno("Save Scenario", "Do you want to save the specified manipulations?"):
            for item in self.scenario_list_items:
                if item.scenario == scenario:
                    item.var.set(True)
                    try:
                        self.current_scenario.save(item.path)
                    except RuntimeError as e:
                        messagebox.showerror("Error", str(e))
                else:
                    item.var.set(False)

    def create_scenario(self):
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        path = filedialog.asksaveasfilename(filetypes=[("Attack Scenario files", "*.json")])
        error = False
        if path == '':
            messagebox.showerror("Error", "No file location given")
            error = True
        try:
            self.window.attributes('-disabled', False)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        if error:
            return
        try:
            if messagebox.askyesno("New Scenario",
                                   "Do you want keep the specified manipulations for the new scenario?"):
                self.current_scenario.save(path)
            else:
                attack_scenario.AttackScenario().save(path)
        except RuntimeError as e:
            messagebox.showerror("Error", str(e))
        scenario = attack_scenario.load_scenario(path)
        for item in self.scenario_list_items:
            item.var.set(False)
        self.current_scenario = scenario
        self._add_scenario_to_list(self.current_scenario, path)
        for item in self.scenario_list_items:
            if self.current_scenario == item.scenario:
                item.var.set(True)
        self.select_variable_for_manipulation()

    def load_scenario(self):
        try:
            self.window.attributes('-disabled', True)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        path = filedialog.askopenfilename(filetypes=[("Attack Scenario files", "*.json")])
        try:
            self.window.attributes('-disabled', False)
        except tk.TclError as tclErr:
            # catch bad attribute error because of an open issue in tkinter since august 2019 
            # last seen 20.01.2022 https://github.com/PySimpleGUI/PySimpleGUI/issues/1799
            if "bad attribute" in str(tclErr):
                pass
            else:
                raise tclErr
        if path == '':
            messagebox.showerror("Error", "No file location given")
            return
        for temp in self.scenario_list_items:
            if temp.path == path:
                messagebox.showerror("Error", "File is already opened")
                return
        scenario = attack_scenario.load_scenario(path)
        self._add_scenario_to_list(scenario, path)
        self.select_variable_for_manipulation()

    def _add_scenario_to_list(self, scenario, path):
        var = tk.BooleanVar()
        var.set(False)
        check_button = tk.Checkbutton(
            self.scenario_list,
            var=var,
            indicatoron=False,
            image=self.image_eye_closed,
            selectimage=self.image_eye_open,
            text="  " + os.path.splitext(os.path.basename(path))[0],
            onvalue=True,
            offvalue=False,
            anchor="w",
            compound="left",
            width=115,
            height=18,
            relief="flat",
            highlightthickness=0,
            command=lambda: self.select_scenario(scenario)
        )
        save_button = tk.Button(
            self.scenario_list,
            text="Save",
            width=5,
            command=lambda: self.save_scenario(scenario)
        )
        remove_button = tk.Button(
            self.scenario_list,
            text="Remove",
            width=7,
            command=lambda: self.remove_scenario(scenario)
        )
        self.scenario_list_items.append(
            gui.ScenarioListItem(scenario, path, check_button, remove_button, save_button, var))
        check_button.grid(row=self.next_scenario_list_item_in_row, column=0)
        save_button.grid(row=self.next_scenario_list_item_in_row, column=1)
        remove_button.grid(row=self.next_scenario_list_item_in_row, column=2)
        self.next_scenario_list_item_in_row += 1

    def select_scenario(self, scenario):
        old_item = None
        new_item = None
        for item in self.scenario_list_items:
            if scenario == item.scenario:
                new_item = item
            elif item.var.get() is True:
                old_item = item
        if old_item is None:
            new_item.var.set(True)
            self.current_scenario = attack_scenario.load_scenario(new_item.path)
        elif messagebox.askyesno(
                "Switch Scenario", "Do you really want to switch to another scenario? Unsaved changes might be lost!"
        ):
            old_item.var.set(False)
            self.current_scenario = attack_scenario.load_scenario(new_item.path)
        else:
            old_item.var.set(True)
            new_item.var.set(False)
        self.select_variable_for_manipulation()

    def remove_scenario(self, scenario):
        if messagebox.askyesno("Remove Scenario", "Do you really want to remove this scenario?"):
            for item in self.scenario_list_items:
                if scenario == item.scenario:
                    item.check_button.grid_forget()
                    item.save_button.grid_forget()
                    item.remove_button.grid_forget()
                    self.scenario_list_items.remove(item)

    def reset_all(self):
        if messagebox.askyesno("Reset Manipulations", "Do you really want to reset all manipulations?"):
            self.current_scenario.commands = []
            self.select_variable_for_manipulation()

    def run_attack(self):
        if messagebox.askyesno("Run Attack", "Do you really want to run the attack?"):
            engines = []
            for item in self.rtu_checklist_items:
                engines.append(item.attack_engine)
            self.current_scenario.execute(engines)

    # display messagebox when trying to quit
    # called by pushing quit button or trying to close the window
    def on_close(self):
        if messagebox.askyesno("Quit", "Do you really want to quit?"):
            self.window.destroy()
            exit()
