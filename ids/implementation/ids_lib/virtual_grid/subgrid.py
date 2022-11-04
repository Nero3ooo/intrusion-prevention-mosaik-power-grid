# subgrid.py
# by Verena
# version 0.1
'''
Subgrid class
Represents the virtual (local) subgrid region in the monitoring system
Inheritates from the virtual_grid_region
'''

import json
import asyncio
from virtual_grid.virtual_components.power_line import power_line
from virtual_grid.virtual_components.switch import switch
from virtual_grid.virtual_components.meter import meter
from virtual_grid.virtual_components.bus import bus

from virtual_grid.virtual_grid_region import virtual_grid_region


class subgrid(virtual_grid_region):
    def __init__(self, name, topology):
        super().__init__(name, topology, "L")
        self.__name = name
        self.__config_file_name = topology

        self.__detailed_print = 1  # 0 = uses the basic alert/print system , 1 = uses the detailed alert/print system

        self.__all_meters = []
        self.__all_switches = []
        self.__all_buses = []
        self.__all_power_lines = []

        pass

    def check_local_requirements(self):
        '''
        main functionality of the subgrid
        checks all available requirements sequentially on its components
        We added a tolerance range for nearly all requirements, because the simulation is not able to read and evaluate
        the given values as fast and as accurate as needed for a sensitive real-time system.
        '''

        self.check_req_1()
        self.check_req_2()
        self.check_req_3_loc()
        self.check_req_4_loc()
        self.check_req_7()
        self.check_req_8()

    # REQ 1 L always fails, since outgoing never equals incoming
    def check_req_1(self):
        '''
        Function to check, if requirement 1L is violated
        REQ 1L: All buses have to have the same value for current incoming and outgoing
        (sum of incoming lines and sum of outgoing lines is calculated)
        '''

        err = 0
        for bus in self.get_all_buses():
            error = 0
            sum_current_incoming = 0
            sum_current_outgoing = 0

            for line in bus.get_incoming_lines():
                meter = self.find_meter(line, bus)
                if meter:
                    sum_current_incoming += meter.get_current()

            for line in bus.get_outgoing_lines():
                meter = self.find_meter(line, bus)
                if meter:
                    sum_current_outgoing += meter.get_current()

            #TODO The tolerance range is way too big (50 ampere) but it's the only way it's working with the live simulation
            incoming_tolerance = [sum_current_incoming-0.05, sum_current_incoming+0.05]
            outgoing_tolerance = [sum_current_outgoing-0.05, sum_current_outgoing+0.05]

            #if sum_incoming_current is not within the tolerance range of sum_current_outgoing and vice versa an error will be registered
            if not ((sum_current_incoming >= outgoing_tolerance[0] and sum_current_incoming <= outgoing_tolerance[1])
                     or (sum_current_outgoing >= incoming_tolerance[0] and sum_current_outgoing <= incoming_tolerance[1])):
                error = 1
                err += 1

            if error:
                asyncio.run(self.report_violation(1, bus))
                
            if self.__detailed_print:
                self.print_detailed_result(1, error, bus)
                if error:
                    print("---- incoming current ----")
                    print(sum_current_incoming)
                    print("---- outgoing current ---")
                    print(sum_current_outgoing)

        if not self.__detailed_print:
            self.print_result(1, err)


    def check_req_2(self):
        '''
        Function to check, if requirement 2L is violated
        REQ 2: All voltages measured by all meters of one bus are equal
        '''
        err = 0
        for bus in self.get_all_buses():
            error = 0

            if self.find_meter(bus.get_incoming_lines()[0], bus):
                ref_voltage = round(
                    float((self.find_meter(bus.get_incoming_lines()[0],
                                           bus)).get_voltage()), 2
                )  # rounding was added due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                for line in bus.get_incoming_lines():
                    meter = self.find_meter(line, bus)
                    if meter:
                        if round(float(meter.get_voltage()), 2) != ref_voltage:
                            error = 1
                            err += 1

                for line in bus.get_outgoing_lines():
                    meter = self.find_meter(line, bus)
                    if meter:
                        if round(float(meter.get_voltage()), 2) != ref_voltage:
                            error = 1
                            err += 1

            if error != 0:
                asyncio.run(self.report_violation(2, bus))
            
            if self.__detailed_print:
                self.print_detailed_result(2, error, bus)
                if error!=0:
                    print("---- Reference voltage was " + str(ref_voltage) + " volts, but " + bus.get_name() + " measured a different value. ----")
        if not self.__detailed_print:
            self.print_result(2, err)

    def check_req_3_loc(self):
        '''
        Function to check, if requirement 3L is violated
        REQ 3L: If a powerline has an open switch, the powerlines meters are suppposed to measure zero current,
        because there shouldnt be any curren to measure.
        (is only executed on local powerlines as REQ 3N is checked by the neighbourhood monitor)
        '''
        err = 0
        for line in self.get_all_power_lines():
            error = 0
            if line.is_local():
                for switch in line.get_assigned_switches():
                    if (switch.get_state()) == "False":
                        for meter in line.get_assigned_meters():
                            if meter.get_current():
                                error = 1
                                err += 1
                                
            if error and (line.is_local() == 1):
                asyncio.run(self.report_violation(3, line))
                
            if self.__detailed_print and (line.is_local() == 1):
                self.print_detailed_result(3, error, line)
        if not self.__detailed_print:
            self.print_result(3, err)

    def check_req_4_loc(self):
        '''
        Function to check, if requirement 4L is violated
        REQ 4L: All meters of a power line measure the same current and voltage throughout the powerline
        (is only executed on local powerlines as REQ 3N is checked by the neighbourhood monitor)
        '''
        err = 0
        for line in self.get_all_power_lines():
            error = 0
            if line.is_local():
                if (line.get_assigned_meters()):
                    error_meter_voltage = [] #list(len(line.get_assigned_meters()))
                    error_meter_current = [] #list(len(line.get_assigned_meters()))

                    ref_current = round(
                    float(line.get_assigned_meters()[0].get_current()), 2)
                    # deactivated due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                    ref_voltage = round(
                        float(line.get_assigned_meters()[0].get_voltage()), 2)

                    for meter in line.get_assigned_meters():
                        #if round(float(meter.get_current()), 2) != ref_current:
                        #error = 1
                        #err += 1
                        if not (round(float(meter.get_current()), 2) >= ref_current - 0.05
                                and round(float(meter.get_current()), 2) <= ref_current + 0.05):

                            error_meter_current.append(meter.get_current())
                            error = 1
                            err += 1
                        # deactivated due to inaccuracy within the simulation, see the Evaluation Chapter for more details

                        # if the meter voltage is not in the tolerance range of 0.5 volts of the ref_voltage, then an error is thrown
                        if not(round(float(meter.get_voltage()), 2) >= ref_voltage-0.05
                                and round(float(meter.get_voltage()), 2) <= ref_voltage+0.05):

                            error_meter_voltage.append(meter.get_voltage())
                            error = 1
                            err += 1
            
            if error and (line.is_local() == 1):
                asyncio.run(self.report_violation(4, line))
            
            if self.__detailed_print and (line.is_local() == 1):
                self.print_detailed_result(4, error, line)
                if error:
                    if error_meter_current:
                        print("---- difference in current ----")
                        for current in error_meter_current:
                            print(str(current - ref_current) + " ampere")

                    if error_meter_voltage:
                        print( "---- difference in voltage ----")
                        for voltage in error_meter_voltage:
                            print(str(voltage - ref_voltage) + " volts")

        if not self.__detailed_print:
            self.print_result(4, err)

    def check_req_7(self):
        '''
        Function to check, if requirement 7L is violated
        REQ 7L: All meters should report a current that is equal or smaller than the amount of current that exceeds
        the safety threshold (it could be considered one of the most important requirements)
        '''
        err = 0
        for meter in self.get_all_meters():
            error = 0
            if float(meter.get_current()) >= float(meter.get_s_current()):
                error = 1
                err += 1
            
            if error:
                asyncio.run(self.report_violation(7, meter))
                
            if self.__detailed_print:
                self.print_detailed_result(7, error, meter)
        if not self.__detailed_print:
            self.print_result(7, err)

    def check_req_8(self):
        '''
        Function to check, if requirement 8L is violated
        REQ 8L: All meters should report a voltage that is equal or smaller than the amount of voltage that exceeds
        the safety threshold (it could be considered one of the most important requirements)
        '''
        err = 0
        for meter in self.get_all_meters():
            error = 0
            if float(meter.get_voltage()) >= float(meter.get_s_voltage()):
                error = 1
                err += 1
            
            if error:
                asyncio.run(self.report_violation(8, meter))
            
            if self.__detailed_print:
                self.print_detailed_result(8, error, meter)
        if not self.__detailed_print:
            self.print_result(8, err)


# HELPER FUNCTIONS

    def load_topology(self):
        '''
        Loads the grid topology from the configuration files and creates the virtual representation of the grid
        '''
        with open(self.__config_file_name) as json_file:
            data = json.load(json_file)
            for power_line_ in data['power_lines']:
                # creation of power lines
                new_line = power_line(power_line_['id'], power_line_['i_max'],
                                      power_line_['v_ref'],
                                      power_line_['is_local'])
                self.assign_power_line(new_line)

            for bus_ in data['buses']:
                # creation of buses
                new_bus = bus(bus_['id'], [], [])

                # TODO: Maybe change all ids to id and make them all arrays even if its only an element,
                #  might reduce confusion
                for line in self.get_all_power_lines():

                    if 'id' in bus_['power_lines_in']:
                        if line.get_name() == str(
                                bus_['power_lines_in']['id']):
                            new_bus.add_inc(line)
                            continue
                    elif 'ids' in bus_['power_lines_in']:
                        for elem in bus_['power_lines_in']['ids']:
                            if line.get_name() == str(elem):
                                new_bus.add_inc(line)
                                continue

                for line in self.get_all_power_lines():
                    if 'id' in bus_['power_lines_out']:
                        if line.get_name() == str(
                                bus_['power_lines_out']['id']):
                            new_bus.add_outg(line)
                            continue
                    elif 'ids' in bus_['power_lines_out']:
                        for elem in bus_['power_lines_out']['ids']:
                            if line.get_name() == str(elem):
                                new_bus.add_outg(line)
                                continue

                self.assign_bus(new_bus)

            for switch_ in data['switches']:
                # creation of switches
                for b in self.get_all_buses():
                    if b.get_name() == switch_['bus_id']:
                        bus_ = b
                line_ = []
                for l in self.get_all_power_lines():
                    if l.get_name() == switch_['power_line_id']:
                        line_ = l
                new_switch = switch(switch_['id'], bus_, line_)
                self.assign_switch(new_switch)

            for meter_ in data['meters']:
                # creation of meters
                bus_ = []
                for b in self.get_all_buses():
                    if b.get_name() == meter_['bus_id']:
                        bus_ = b
                line_ = []
                for l in self.get_all_power_lines():
                    if l.get_name() == meter_['power_line_id']:
                        line_ = l
                new_meter = meter(meter_['id'], bus_, line_,
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

    def find_meter(self, line, bus):
        '''
        Finds all meters which are attached to 'line' as well as to 'bus'
        '''
        for meter in self.get_all_meters():
            if meter.get_assinged_power_line() is line:
                if meter.get_assigned_bus() is bus:
                    return meter

    def print_subgrid_values(self):
        '''
        Prints all current switch, current and voltage values
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

    def get_all_switches(self):
        '''
        Returns an array of all available switches in the grid
        '''
        return self.__all_switches

    def assign_switch(self, new_switch):
        '''
        Adds 'new_switch' to the array of switches within the grid
        '''
        self.get_all_switches().append(new_switch)

    def get_all_buses(self):
        '''
        Returns an array of all available buses in the grid
        '''
        return self.__all_buses

    def assign_bus(self, new_bus):
        '''
        adds 'new_bus' to the array of buses in the grid
        '''
        self.get_all_buses().append(new_bus)

    def get_all_meters(self):
        '''
        returns an array of all available meters within the grid
        '''
        return self.__all_meters

    def assign_meter(self, new_meter):
        '''
        adds 'new_meter' to the array of meters in the grid
        '''
        self.get_all_meters().append(new_meter)

    def get_all_power_lines(self):
        '''
        returns an array of all available power lines within the grid
        '''
        return self.__all_power_lines

    def assign_power_line(self, new_power_line):
        '''
        adds 'new_power_line' to the array of power lines in the grid
        '''
        self.get_all_power_lines().append(new_power_line)
