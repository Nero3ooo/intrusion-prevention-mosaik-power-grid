# rtu.py
# Mosaik Simulator representing a RTU
# originally developed by Chromik
# small adaptions/test outputs done by Verena, my comments are marked starting with "V: "
# version 0.2

import mosaik_api
import os
from datetime import datetime
from mosaikrtu import rtu_model
import logging
logger = logging.getLogger('demo_main')
ch = logging.StreamHandler()
ch.setLevel(logging.WARN)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)
from topology_loader.topology_loader import topology_loader
from distutils.util import strtobool

# for validation component
import sys
import asyncio
from asyncua import ua
from asyncua import Client
import time

import warnings
warnings.filterwarnings("ignore")

try:
    os.remove('./outputs/output_during_rtu_step.txt')
except OSError:
    pass

META = {
    'type': 'time-based',
    'models': {
        'RTU': {
            'public': True,
            'params': ['rtu_ref'],
            'attrs': ['switchstates'],
        },
        'sensor': {
            'public': True,
            'params': ['node', 'branch'],  # V: Parameter
            'attrs': [
                'I_real', 'I_imag', 'Vm'
            ],  # V: Meters reading voltage and current -> Incoming values from simulation
        },
        'switch': {
            'public': True,
            'params':
            ['init_status', 'branch'
             ],  # read from the file and mark as "on" if line is online. 
            'attrs': ['online'],
        },
    },
}


class MonitoringRTU(mosaik_api.Simulator):
    

    url = "opc.tcp://192.168.0.19:4840/freeopcua/server/"
    val_address = url
    namespace = "http://itsis-blackout.ids/"
    res = False

    def __init__(self):
        super().__init__(META)
        self.rtu_ref = ""
        self.conf = ""
        self.sid = None
        self.data = ""
        self.rtueid = ""
        self._rtus = []
        self.entities = {}
        self._entities = {}
        self._cache = {}
        self.worker = ""
        self.server = ""
        topoloader = topology_loader()
        conf = topoloader.get_config()
        global RECORD_TIMES
        RECORD_TIMES = bool(strtobool(conf['recordtimes'].lower()))
        global RTU_STATS_OUTPUT  # configuriert, ob die Daten in output/readings geschrieben werden sollen
        RTU_STATS_OUTPUT = False
        #RTU_STATS_OUTPUT = bool(strtobool(conf['rtu_stats_output'].lower()))

        #IPS is constant for differing between physical rtu simulation and rtu simulation for validation component
        global IPS
        IPS = bool(strtobool(conf['ips'].lower()))

        if IPS:
            self.res = True

        global global_sensor_zero_counter
        global_sensor_zero_counter = 0

        # Setup Logging for this package
        logging.getLogger('pymodbus3').setLevel(logging.CRITICAL)

        global logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

        #handler = OPCNetworkLogger()
        #logger.addHandler(handler)

        handler = logging.StreamHandler(sys.stderr)
        logger.addHandler(handler)

        #### Verena
        global fd_1
        fd_1 = open('./outputs/output_during_rtu_step.txt', 'w+')
        intro_text = "This file saves data generated by the rtu.py file.\nDuring the update process of all components in a simulation step, the file saves the name of the component, the register it should be written to and the value itself.\nThe code responsible for this outputs can be found in the step(self, time, inputs)-method.\n \n"
        fd_1.write(intro_text)
        ####

    def init(self, sid, time_resolution):
        if float(time_resolution) != 1.:
            raise ValueError('MonitoringRTU only supports time_resolution=1., but'
                             ' %s was set.' % time_resolution)
        self.sid = sid
        return self.meta

    def create(self, num, model, rtu_ref=None):
        rtu = []
        for i in range(num):
            rtu_idx = len(self._rtus)
            if rtu_ref:
                self.rtu_ref = rtu_ref
                self.conf = rtu_model.load_rtu(
                    self.rtu_ref
                )  # use rtu_model.load_rtu to load the configuration
                self.data = rtu_model.create_datablock(
                    self.conf
                )  # create_datablock should take the dt into account
                self._cache, entities = rtu_model.create_cache(
                    self.conf["registers"])
                self.server = rtu_model.create_server(self.conf, self.data)
                self.server.start()
            self._rtus.append(rtu)
            children = []
            for eid, attrs in sorted(entities.items()):
                assert eid not in self._entities
                self._entities[eid] = attrs
                if 'node' not in attrs:
                    print("Entity without the node is {}".format(eid))
                    print("Attrs: {}".format(attrs))
                children.append({
                    'eid': eid,
                    'type': attrs['etype'],
                    'node': attrs['node'],
                    'branch': attrs['branch'],
                })
            self.rtueid = rtu_model.make_eid('rtu', rtu_idx)
            rtu.append({
                'eid': self.rtueid,
                'type': 'RTU',
                'children': children,
            })
        return rtu

    def step(self, time, inputs, max_advance):
        commands = {}  # set commands for switches
        switchstates = {}
        src = self.sid + '.' + self.rtueid  # RTUSim-0.0-rtu%
        dest = 'PyPower-0.PyPower'  # V: <- PyPower Simulator from Simulation
        commands[src] = {}
        commands[src][dest] = {}

        fd_1.write("--- Starting one RTU step (for" + str(self.sid) + '.' +
                   str(self.rtueid) + "). ---\n")

        for s, v in self._cache.items():
            if 'switch' in s or 'transformer' in s:
                print(f"\n switch {v['dev']}\n value data in switch:{self.data.get( v['reg_type'], v['index'],1)[0]} \n value in v array: {v['value']}")
                #if switch or transformer has a new value
                if self.data.get( v['reg_type'], v['index'],1)[0] != v['value'] or IPS:
                    #if the testbed was started in the ips do not connect to the validation because this is the validation
                    if not IPS:
                        try:
                            #check if new value of switch is valid
                            asyncio.run(self.__validate_commands(
                                inputs.items(),
                                v['reg_type'], 
                                v['index'], 
                                self.data.get( v['reg_type'], v['index'],1)[0]))
                        except BaseException as e:
                            print(e)
                    if RTU_STATS_OUTPUT:  # V: write to output file "model_readings.csv"
                        rtu_model.save_readings(
                            self.sid, 
                            v['reg_type'] + str(v['index']), 
                            "state",
                            v['value'])

                    if(self.res or "transformer" in v['place']):
                        self._cache[s]['value'] = self.data.get(v['reg_type'], v['index'], 1)[0]
                        switchstates[v['place']] = v['value']

                        if commands[src][dest] == {}:
                            print("##########Switch state changed.")
                            commands[src][dest]['switchstates'] = switchstates
                        else:
                            if (self.res):
                                print("##########Switch state changed.")
                                commands[src][dest]['switchstates'].update(
                                switchstates)
                    else:
                        self.data.set(v['reg_type'], v['index'], v['value'])

        if IPS:
            global global_sensor_zero_counter
            sensor_zero_counter = 0
        for eid, data in inputs.items():

            for attr, values in data.items():  # attr is like I_real etc.
                if attr in ['I_real', 'Vm']:
                    for src, value in values.items():
                        if "grid" in src:
                            continue
                        else:
                            src = src.split("-")[2]
                            dev_id = eid + "-" + src  # dev_id, e.g. sensor_2-node_d1, sensor_2-branch_17, sensor_1-branch_16
                            assert dev_id in self._cache

                            self._cache[dev_id]["value"] = value
                            print(f"new data in cache and modbus for dev_id {dev_id}: {value}")
                            if IPS and value == 0.0 :
                                sensor_zero_counter += 1
                            self.data.set(
                                self.conf['registers'][dev_id][0],
                                self.conf['registers'][dev_id][1], value,
                                self.conf['registers'][dev_id][2]
                            )  # V: write the new values to the matching register

                            fd_1.write(
                                str(eid) + " " +
                                str(self.conf['registers'][dev_id][1]) + " " +
                                str(self._cache[dev_id]["value"]) + "\n"
                            )  # V: Write to output file "output_during_rtu_step.csv" the currently updated value as (name, register, value)

                            if RTU_STATS_OUTPUT:  # V: write to output file "model_readings.csv"
                                rtu_model.save_readings(
                                    self.sid, dev_id, attr, value)

        fd_1.write("--- One RTU step done (for" + str(self.sid) + '.' +
                   str(self.rtueid) + "). ---\n\n")

        if bool(switchstates) and RECORD_TIMES:
            rtu_model.log_event("NC")
        print(f"mosaik set data: {commands}")
        yield self.mosaik.set_data(commands)
        if IPS and sensor_zero_counter > global_sensor_zero_counter:
            global_sensor_zero_counter = sensor_zero_counter

        if IPS:
            return time + 60
        return time + 60

    def finalize(self):
        #self.worker.stop()
        #print("Worker Stopped")
        self.server.stop()
        print("Server Stopped")
        print("\n\n")
        print('Finished')
        if(IPS and global_sensor_zero_counter > 0):
            raise Exception('zero-sensors',global_sensor_zero_counter)


    def get_data(self, outputs
                 ):  # Return the data for the requested attributes in outputs
        #outputs is a dict mapping entity IDs to lists of attribute names whose values are requested:
        # 'eid_1': ['attr_1', 'attr_2', ...],
        #{    'eid_1: {}      'attr_1': 'val_1', 'attr_2': 'val_2', ...
        #print("Output of RTU: {}".format(outputs))
        data = {}
        for eid, attrs in outputs.items():
            for attr in attrs:
                try:
                    val = self._entities[eid][attr]
                except KeyError:
                    print("No such Key")
                    val = None
                data.setdefault(eid, {})[attr] = val
        return data

    async def __validate_commands(self, items, reg_type, index, newValue) -> None:

        #self.uuid = str(config.uuid)
        self.uuid = "1234"
        client_val = Client(url=self.val_address, watchdog_intervall=1000)

        # # security settings
        # await client_c2.set_security(
        #     SecurityPolicyBasic256Sha256,
        #     certificate=self.config.cert,
        #     private_key=self.config.private_key,
        #     private_key_password=self.config.private_key_password,
        #     server_certificate=self.config.c2_cert
        # )

        while True:
            try:
                await client_val.connect()
                logger.info("Connected to validation Server")
                break
            except BaseException as e:
                logger.error(f"{self.uuid} Connection error while connecting to validation Server. Retrying in 5 seconds")
                await asyncio.sleep(5)

        await client_val.load_data_type_definitions()
        nsidx = await client_val.get_namespace_index(self.namespace)
        print(f"Namespace Index for '{self.namespace}': {nsidx}")
        rtu0_data = ua.RTUData()
        rtu0_data.switches = []
        rtu0_data.others = []
        rtu1_data = ua.RTUData()
        rtu1_data.switches = []
        rtu1_data.others = []
        for s, v in self._cache.items():
            print(f"\n item s {s} \n item v: {v}")
            if( "switch" in v["dev"]):
                print("\n add Switch\n")
                switch = ua.SwitchData()
                switch.dev = v["dev"]
                switch.place = v["place"]
                switch.reg_type = v["reg_type"]
                switch.index = v["index"]
                switch.datatype = v["datatype"]
                # if switch has new value use this else use the old one
                if newValue != v['value'] and index == v['index'] and reg_type == v['reg_type']:
                    switch.value = newValue
                else:
                    switch.value = v["value"]
                #select rtu to add data
                if(self.sid == "RTUSim-0"):
                    rtu0_data.switches.append(switch)
                elif(self.sid == "RTUSim-1"):
                    rtu1_data.switches.append(switch)
            elif( "transformer" in v["dev"] or "sensor" in v["dev"] or "max" in v["dev"]):
                print("\n add Other\n")
                other = ua.OtherData()
                other.dev = v["dev"]
                other.place = v["place"]
                other.reg_type = v["reg_type"]
                other.index = v["index"]
                other.datatype = v["datatype"]
                other.value = float(v["value"])
                #select rtu to add data
                if(self.sid == "RTUSim-0"):
                    rtu0_data.others.append(other)
                elif(self.sid == "RTUSim-1"):
                    rtu1_data.others.append(other)

        # for eid, data in items:
        #     for attr, values in data.items():  # attr is like I_real etc.
        #         if attr in ['I_real', 'Vm']:
        #             for src, value in values.items():
        #                 if "grid" in src:
        #                     continue
        #                 else:
        #                     print(f"\n source: {src}\n value: {value} \n \n")

        # Calling a method
        self.res = await client_val.nodes.objects.call_method(f"{nsidx}:validate", rtu0_data, rtu1_data)
        await print(f"Calling ServerMethod returned {self.res}")


        #async def __build_rtu_data_object(self, ) -> None:

def main():
    return mosaik_api.start_simulation(MonitoringRTU())

if __name__ == '__main__':
    main()    