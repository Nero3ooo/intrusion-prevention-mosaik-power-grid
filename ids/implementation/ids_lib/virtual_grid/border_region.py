# border_region.py
# by Verena
# version 0.1
'''
Border Region class
Represents the virtual neighbourhood in the monitoring system
Inheritates from the virtual_grid_region
'''

import json
import asyncio
from virtual_grid.virtual_components.power_line import power_line
from virtual_grid.virtual_components.meter import meter
from virtual_grid.virtual_components.switch import switch

from virtual_grid.virtual_grid_region import virtual_grid_region


class border_region(virtual_grid_region):
    '''
    The border region class is given a topology file, defining its attributes.
    The border region is particularly important for the neighbourhood monitor to be able to check
    all neighbourhood level requirements. Currently REQ3N and REQ4N are checked.
    '''
    def __init__(self, name, topology):
        super().__init__(name, topology, "N")
        self.__detailed_print = 1  # 0 = uses the basic alert/print system , 1 = uses the detailed alert/print system
        self.__all_power_lines = []
        self.__all_switches = []
        self.__all_meters = []

        self.__name = name
        self.__config_file_name = topology
        pass

    def check_neighbourhood_requirements(self):
        '''
        main functionality of the border region
        checks all available requirements sequentially on its components
        '''
        self.check_req_3_neigh()
        self.check_req_4_neigh()

    def check_req_3_neigh(self):
        '''
        Function to check, if requirement 3N is violated.
        REQ 3N: If a powerline has an open switch, the powerlines meters are suppposed to measure zero current,
        because there shouldnt be any curren to measure.
        We added a tolerance range, because the simulation is not able to read and evaluate the given values as fast
        and as accurate as needed for a sensitive real-time system.
        '''
        err = 0
        for line in self.get_all_power_lines():
            error = 0
            for switch in line.get_assigned_switches():
                if (switch.get_state()) == "False":
                    for meter in line.get_assigned_meters():
                        if meter.get_current():
                            error = 1
                            err += 1
            
            if error:
                asyncio.run(self.report_violation(3, line))
                
            if self.__detailed_print:
                self.print_detailed_result(3, error, line)
        if not self.__detailed_print:
            self.print_result(3, err)

    def check_req_4_neigh(self):
        '''
        Function to check, if requirement 4N is violated.
        REQ 4N: All meters of a power line measure the same current and voltage throughout the powerline
        We added a tolerance range, because the simulation is not able to read and evaluate the given values as fast
        and as accurate as needed for a sensitive real-time system.
        '''
        err = 0
        for line in self.get_all_power_lines():
            error = 0
            if (line.get_assigned_meters()):

                error_meter_voltage = []  # list(len(line.get_assigned_meters()))
                error_meter_current = []  # list(len(line.get_assigned_meters()))

                ref_current = round(float(line.get_assigned_meters()[0].get_current()), 2)
                # rounding was added due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                ref_voltage = round(float(line.get_assigned_meters()[0].get_voltage()), 2)
                # rounding was added due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                for meter in line.get_assigned_meters():
                    # if round(float(meter.get_current()),2) != ref_current:
                    if not (round(float(meter.get_current()), 2) >= ref_current - 0.05
                            and round(float(meter.get_current()), 2) <= ref_current + 0.05):
                        error_meter_current.append(meter.get_current())
                        error = 1
                        err += 1
                    # deactivated due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                    #if round(float(meter.get_voltage()), 2) != ref_voltage:
                    if not(round(float(meter.get_voltage()), 2) >= ref_voltage-0.05
                            and round(float(meter.get_voltage()), 2) <= ref_voltage+0.05):

                        error_meter_voltage.append(meter.get_voltage())
                        error = 1
                        err += 1
            if error:
                asyncio.run(self.report_violation(4, line))
            
            if self.__detailed_print:
                self.print_detailed_result(4, error, line)

                if error_meter_current:
                    print("---- difference in current ----")
                    for current in error_meter_current:
                        print(str(current - ref_current) + " ampere")

                if error_meter_voltage:
                    print("---- difference in voltage ----")
                    for voltage in error_meter_voltage:
                        print(str(voltage - ref_voltage) + " volts")

        if not self.__detailed_print:
            self.print_result(4, err)


# HELPER FUNCTIONS

    def load_topology(self):
        # loads the grid topology from the configuration files and creates the virtual representation of the border region

        with open(self.__config_file_name) as json_file:
            data = json.load(json_file)
            for power_line_ in data['power_lines']:
                # creation of power lines
                new_line = power_line(power_line_['id'], power_line_['i_max'],
                                      power_line_['v_ref'],
                                      power_line_['is_local'])
                self.assign_power_line(new_line)

            for switch_ in data['switches']:
                # creation of switches
                line_ = []
                for l in self.get_all_power_lines():
                    if l.get_name() == switch_['power_line_id']:
                        line_ = l
                new_switch = switch(switch_['id'], switch_['bus_id'], line_)
                self.assign_switch(new_switch)

            for meter_ in data['meters']:
                # creation of meters
                line_ = []
                for l in self.get_all_power_lines():
                    if l.get_name() == meter_['power_line_id']:
                        line_ = l
                new_meter = meter(meter_['id'], meter_['bus_id'], line_,
                                  meter_['s_current'], meter_['s_voltage'])
                self.assign_meter(new_meter)

            for line in self.get_all_power_lines():
                for m in self.get_all_meters():
                    if m.get_assinged_power_line() == line:
                        line.attach_meter(m)
                for s in self.get_all_switches():
                    if s.get_assinged_power_line() == line:
                        line.attach_switch(s)

    def update_values(self, switches, meter_voltage, meter_current):
        '''
        Takes three arrays of data updates (switches, meter_voltage and meter_current) in order
        and updates the values of the grid components
        '''
        i = 0
        for switch in self.get_all_switches():
            switch.update_state(switches[i])
            i += 1
        i = 0
        for meter in self.get_all_meters():
            meter.update_voltage(meter_voltage[i])
            meter.update_current(meter_current[i])
            i += 1

    def assign_power_line(self, new_power_line):
        '''
        adds 'new_power_line' to the array of power lines in the border region
        '''
        if not new_power_line.is_local():
            self.__all_power_lines.append(new_power_line)
        else:
            raise ValueError(
                "Tried to assign local power line to border region.")

    def assign_meter(self, new_meter):
        '''
        adds 'new_meter' to the array of meters in the border region
        '''
        self.__all_meters.append(new_meter)

    def assign_switch(self, new_switch):
        '''
        adds 'new_switch' to the array of switches in the border region
        '''
        self.__all_switches.append(new_switch)

    def get_all_power_lines(self):
        '''
        returns an array of all power lines within the border region
        '''
        return self.__all_power_lines

    def get_all_meters(self):
        '''
        returns an array of all meters within the border region
        '''
        return self.__all_meters

    def get_all_switches(self):
        '''
        returns an array of all switches within the border region
        '''
        return self.__all_switches

    def print_border_values(self):
        '''
        prints all current switch, current and voltage values
        '''
        i = 0
        for switch in self.get_all_switches():
            print(str(switch.get_name()) + " " + str(switch.get_state()))
            i += 1
        i = 0
        for meter in self.get_all_meters():
            print(
                str(meter.get_name()) + " I: " + str(meter.get_current()) +
                " V " + str(meter.get_voltage()))
            i += 1
