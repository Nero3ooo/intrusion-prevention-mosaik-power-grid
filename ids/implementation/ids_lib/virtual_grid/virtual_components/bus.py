# bus.py
# by Verena
# version 0.1
'''
Bus class
Represents the virtual bus in the monitoring system
'''
import virtual_grid.virtual_components.power_line

from virtual_grid.virtual_components.component import component


class bus(component):
    '''
    A virtual bus between various powerlines that can be observed and checked in the monitoring system
    '''
    def __init__(self, name, inc, outg):
        super().__init__(name)

        self.__incoming_lines = inc
        self.__outgoing_lines = outg
        pass

    def get_incoming_lines(self):
        '''Returns an array of all incoming power lines at the bus'''
        return self.__incoming_lines

    def get_outgoing_lines(self):
        '''Returns an array of all outgoing power lines at that bus'''
        return self.__outgoing_lines

    def add_inc(self, line):
        '''Adds 'line' to the array of incoming power lines of the bus'''
        self.__incoming_lines.append(line)

    def add_outg(self, line):
        '''Adds 'line' to the array of outgoing power lines of the bus'''
        self.__outgoing_lines.append(line)
