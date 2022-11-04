# switch.py
# by Verena
# version 0.1
'''
Switch class
Represents the virtual switch in the monitoring system
'''
import virtual_grid.virtual_components.power_line
import virtual_grid.virtual_components.bus

from virtual_grid.virtual_components.component import component


class switch(component):
    '''
    Virtual respresentaion of switches.
    Switches carry a name and are assigned/attached to a bus and a powerline.
    The state is a value that can be set to 0, which means it's open and any other number, to close it.
    TODO: Might be better to use a bool here instead of number? I mean there are only two states for a switch anyway.
    '''
    def __init__(self, name, bus, power_line):
        super().__init__(name)
        self.__assigned_bus = bus
        self.__assigned_power_line = power_line
        self.__state = 0
        pass

    def update_state(self, new_state):
        '''Sets the state of the switch to 'new_state'''
        self.__state = new_state

    def get_state(self):
        '''Returns the current state of the switch'''
        return self.__state

    def get_assigned_bus(self):
        '''Returns the bus, that the switch is assigned to'''
        return self.__assigned_bus

    def get_assinged_power_line(self):
        '''Returns the power line that the switch is assigned to'''
        return self.__assigned_power_line
