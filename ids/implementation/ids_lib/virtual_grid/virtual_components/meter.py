# meter.py
# by Verena
# version 0.1
'''
Meter class
Represents the virtual meter in the monitoring system
'''

from virtual_grid.virtual_components.component import component


class meter(component):
    '''
    Virtual meter in the monitoring system.
    A meter is assigned/attached to a bus and a powerline and is given a security threshold for measuring the
    current (s_current) and voltage (s_voltage).
    '''
    def __init__(self, name, bus, power_line, s_current, s_voltage):
        super().__init__(name)
        self.__assigned_bus = bus
        self.__assigned_power_line = power_line

        self.__s_current = s_current
        self.__s_voltage = s_voltage

        self.__voltage = 0
        self.__current = 0
        pass

    def update_current(self, new_current):
        '''Set the current of the meter to new_current'''
        self.__current = new_current

    def update_voltage(self, new_voltage):
        '''Set the voltage of the meter to new_voltage'''
        self.__voltage = new_voltage

    def get_s_current(self):
        '''Returns the set point current for the meter'''
        return self.__s_current

    def get_s_voltage(self):
        '''Returns the set point voltage for the meter'''
        return self.__s_voltage

    def get_current(self):
        '''Returns the current current'''
        return self.__current

    def get_voltage(self):
        '''Returns the current voltage'''
        return self.__voltage

    def get_assigned_bus(self):
        '''Returns the bus, that the meter is attached to'''
        return self.__assigned_bus

    def get_assinged_power_line(self):
        '''Returns the power line, that the meter is attached to'''
        return self.__assigned_power_line