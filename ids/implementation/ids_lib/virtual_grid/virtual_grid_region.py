#virtual_grid_region.py
# by Verena
# version 0.1
'''
virtual_grid_region
This class is the base class for all virtual representation of an electrical grid region within the monitoring system. 
'''
import time
import asyncio
import websockets
import json
from termcolor import colored, cprint


class virtual_grid_region():
    def __init__(self, name, topology, scope):
        self.id = name
        self.__config_file_name = topology
        self.__scope_name = scope

    def update_values(self):
        '''
        Stud and reminder that every virtual region needs to realize one 'update_values' function to update
        the values of every of their components
        '''
        pass

    def print_result(self, req, err):
        '''
        print function as a substitue for a distinct "alert" functionality
        reports if a requirement is violated or not
        '''
        if err:
            cprint(
                "Alert! REQ " + str(req) + " " + str(self.__scope_name) +
                " violated.", 'red')
        else:
            cprint("REQ " + str(req) + " " + str(self.__scope_name) + " OK.", 'green')

    def print_detailed_result(self, req, error, component):
        '''
        print function as a substitue for a distinct "alert" functionality
        reports which component has violated a requirement or has passed
        '''
        if error:
            cprint(
                "Alert! REQ " + str(req) + " " + str(self.__scope_name) +
                " violated by " + str(component.get_name()), 'red')
        else:
            cprint("REQ " + str(req) + " " + str(self.__scope_name) +
                "  OK for " + str(component.get_name()), 'green')
    
    async def report_violation(self, req, component):
        try:
            async with websockets.connect("ws://websocket:8777") as websocket:
                print('connected to websoc')
                report = { "type": "report", "timestamp": int(time.time()), "requirement": req, "component_id": component.id }
                await websocket.send(json.dumps(report))
        except Exception:
            pass