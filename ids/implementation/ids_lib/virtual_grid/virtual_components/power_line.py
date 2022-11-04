# power_line.py
# by Verena
# version 0.1
'''
Power line class
Represents the virtual power line in the monitoring system
'''
import virtual_grid.virtual_components.meter
from virtual_grid.virtual_components.component import component


class power_line(component):
    '''
    Virtual powerline in the monitoring system
    A powerline is given a max current value (i_max), a voltage reference (v_ref) and a boolean that states
    if the powerline is only local or if it crosses another region and therefore is in a border region (is_local)
    Also it is assigned various meters and switches
    '''
    def __init__(self, name, i_max, v_ref, is_local):
        super().__init__(name)
        self.__i_max = i_max
        self.__v_ref = v_ref
        self.__is_local = is_local  # 1 = inner power line, 0 = connecting power line between two subgrids
        self.__assigned_meters = []
        self.__assigned_switches = []
        pass

    def attach_meter(self, new_meter):
        '''Adds 'new_meter' to the array of meters attached at the power line'''
        self.__assigned_meters.append(new_meter)

    def attach_switch(self, new_switch):
        '''Adds 'new_switch' to the array of switches attached to the power line'''
        self.__assigned_switches.append(new_switch)

    def get_i_max(self):
        '''Returns the maximum current on the power line'''
        return self.__i_max

    def get_v_ref(self):
        '''Returns the voltage refernece on the power line'''
        return self.__v_ref

    def is_local(self):
        '''
        Returns if the power line is a local, or a connecting power line between two subgrids
        1 = inner power line, 0 = connecting power line
        '''
        return self.__is_local

    def get_assigned_meters(self):
        '''Returns an array with all meters assigned to the power line'''
        return self.__assigned_meters

    def get_assigned_switches(self):
        '''Returns an array with all switches assigned to the power line'''
        return self.__assigned_switches
