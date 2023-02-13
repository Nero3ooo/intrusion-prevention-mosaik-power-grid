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
    res = True
    #stepcounter = 0

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

        global newvalue
        newvalue = 0


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

        self.stepcounter = 0
        self.physical_violations = {}

        # Setup Logging for this package
        logging.getLogger('pymodbus3').setLevel(logging.CRITICAL)
        logging.getLogger('asyncua.uaprotocol').setLevel(logging.CRITICAL)
        # logging.getLogger('mosaik_api').setLevel(logging.CRITICAL)

        global logger
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.WARNING)

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
                    logger.warning("Entity without the node is {}".format(eid))
                    logger.warning("Attrs: {}".format(attrs))
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

        self.stepcounter += 1
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
                # ----------print(f"\n switch {v['dev']}\n value data in switch:{self.data.get( v['reg_type'], v['index'],1)[0]} \n value in v array: {v['value']}")
                #if switch or transformer has a new value
                if self.data.get( v['reg_type'], v['index'],1)[0] != v['value'] or IPS:
                    #if the testbed was started in the ips do not connect to the validation because this is the validation
                    if not IPS:
                        try:
                            #check if new value of switch is valid
                            asyncio.run(self.__validate_commands(
                                time,
                                inputs.items(),
                                v['reg_type'], 
                                v['index'], 
                                self.data.get( v['reg_type'], v['index'],1)[0]), debug = False)
                        except BaseException as e:
                            logger.error(e)
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
                            commands[src][dest]['switchstates'] = switchstates
                        else:
                            commands[src][dest]['switchstates'].update(switchstates)
                    else:
                        self.data.set(v['reg_type'], v['index'], v['value'])
                        logger.info("\n\n-----Reset switch because of validation fails-----\n\n")
        
        # set counter for checking zero sensors to null
        if IPS:
            global global_sensor_zero_counter
            sensor_zero_counter = 0
        global newvalue
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
                            if (dev_id == 'sensor_13-node_b19' and newvalue != value):
                                firstprint = False
                                print(f"{dev_id}: {value}")
                                newvalue = value 
                            
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
        
        # check if it is a relevant step for the rtu (Step with new sensor values)
        if (IPS and self.sid == "RTUSim-0"):
            relevant_step = ((self.stepcounter-1)%30 == 0 or self.stepcounter == 1 or self.stepcounter == 3)
        elif (IPS and self.sid == "RTUSim-1"):
            relevant_step = ((self.stepcounter-2)%30 == 0 or self.stepcounter == 2 or self.stepcounter == 4)
        
        # check requirements 3, 7 and 8 here (IPS only)
        if(IPS and relevant_step):
            self._check_req_3()
            self._check_req_7_and_8()

        fd_1.write("--- One RTU step done (for" + str(self.sid) + '.' +
                   str(self.rtueid) + "). ---\n\n")

        if bool(switchstates) and RECORD_TIMES:
            rtu_model.log_event("NC")
        logger.debug(f"mosaik set data: {commands}")
        yield self.mosaik.set_data(commands)

        # use max of zero counter and global zero counter to global zero counter
        if IPS and sensor_zero_counter > global_sensor_zero_counter:
            global_sensor_zero_counter = sensor_zero_counter

        return time + 60

    def finalize(self):
        #self.worker.stop()
        #print("Worker Stopped")
        self.server.stop()
        logger.info("Server Stopped")
        logger.info("\n\n")

        #after stopping server send result of validation to validation-compontent
        if(IPS):
            asyncio.run(self.__return_result_to_validation(), debug = False)

        logger.info(f'{self.sid}: Finished')

    def get_data(self, outputs):  # Return the data for the requested attributes in outputs
        #outputs is a dict mapping entity IDs to lists of attribute names whose values are requested:
        # 'eid_1': ['attr_1', 'attr_2', ...],
        #{    'eid_1: {}      'attr_1': 'val_1', 'attr_2': 'val_2', ...
        logger.debug("Output of RTU: {}".format(outputs))
        data = {}
        for eid, attrs in outputs.items():
            for attr in attrs:
                try:
                    val = self._entities[eid][attr]
                except KeyError:
                    logger.error("No such Key")
                    val = None
                data.setdefault(eid, {})[attr] = val
        return data

    def _check_req_3(self):
        """Checks Requirement 3 (local scope): There is no current on a power line with an open switch."""
    #     # Get all power lines with open switch
        open_switch_lines = []
        for s, v in self._cache.items():
            if "switch" in s and v["value"] == False:
                print(f"switch {s} is open")
                open_switch_lines.append(v["place"])
        for s, v in self._cache.items():
            if "sensor" in s and v["place"] in open_switch_lines and float(v['value']) != 0.0:
                self._add_physical_violation("S3", s)
                logger.warning(f"S3 violation value:{v['value']} on {v['place']}")

    def _check_req_7_and_8(self):
        """Checks Requirement S7 and S8: Safety threshold regarding voltage and current is met at every meter."""
        for s, v in self._cache.items():
            if("sensor" in v["dev"]):
                for a, b in self._cache.items():
                    number = v["dev"]
                    number = number.replace("sensor_", "")
                    if(a == "max"+str(number)+"-"+str(v['place'])):
                        logger.debug(f"mymax {b['value']} for sensor {s} with value {v['value']}")
                        if(float(v["value"]) > float(b["value"])):
                            print(f"mymax {b['value']} for sensor {s} with value {v['value']}")
                            if("node" in s):
                                self._add_physical_violation("S7", s)
                                logger.warning(f"S7 violation value:{v['value']} higher than {b['value']}")
                            else:
                                self._add_physical_violation("S8", s)
                                logger.warning(f"S8 violation value:{v['value']} higher than {b['value']}")
    
    #violation helper to add violations for IPS
    def _add_physical_violation(self, violation, sensor):
        if not violation in self.physical_violations:
            self.physical_violations[violation] = {}
        if sensor in self.physical_violations[violation]:
            self.physical_violations[violation][sensor] += 1
        else:
            self.physical_violations[violation][sensor] = 1

    # validation method connects to validation server and sets parameter after validation
    async def __validate_commands(self, time, items, reg_type, index, newValue) -> None:

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

        # connecting to validation server (retrying up to 5 times)
        break_counter = 0
        while True:
            try:
                await client_val.connect()
                logger.info("Connected to validation Server")
                break
            except BaseException as e:
                if break_counter == 4:
                    logger.error(f"{self.uuid} Could not reach validation Server after trying 5 times.")
                    return
                break_counter += 1
                logger.error(f"{self.uuid} Connection error while connecting to validation Server. Retrying in 5 seconds")
                await asyncio.sleep(5)
            
            

        await client_val.load_data_type_definitions()
        nsidx = await client_val.get_namespace_index(self.namespace)
        logger.info(f"Namespace Index for '{self.namespace}': {nsidx}")

        # create rtu data, switches array and others array for rtu 0 and rtu 1
        rtu0_data = ua.RTUData()
        rtu0_data.switches = []
        rtu0_data.others = []
        rtu1_data = ua.RTUData()
        rtu1_data.switches = []
        rtu1_data.others = []

        for s, v in self._cache.items():
            
            # create switch data and add it to switch array 
            if( "switch" in v["dev"]):
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
            
            # create other data for transformers, sensors and max values and add it to others array
            elif( "transformer" in v["dev"] or "sensor" in v["dev"] or "max" in v["dev"]):
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

        # calling validation method on validation server 
        validation_result = await client_val.nodes.objects.call_method(f"{nsidx}:validate", rtu0_data, rtu1_data, time)
        logger.info(f"Calling ServerMethod returned {validation_result}")
        self.res = True
        if validation_result.zero_sensors > 0 and validation_result.zero_sensors <= 2:
            logger.warning("\n\n-----WARNING: There are a few zero sensors-----\n\n")
        elif validation_result.zero_sensors > 2:
            logger.warning("\n\n-----ERROR: There are multiple zero sensors-----\n\n")
            self.res = False
        if validation_result.physical_violations:
            print(validation_result.physical_violations)
        

    # return count of zero sensors and physical violations to IPS
    async def __return_result_to_validation(self) -> None:
        self.uuid = "1234"
        global global_sensor_zero_counter
        client_val = Client(url=self.val_address, watchdog_intervall=1000)
        await client_val.connect()
        await client_val.load_data_type_definitions()
        nsidx = await client_val.get_namespace_index(self.namespace)
        
        # call function on server
        await client_val.nodes.objects.call_method(f"{nsidx}:return_zeros", self.conf["port"], global_sensor_zero_counter)
        
        # map violations to OPC-Objects, because OPC does not allow to use dictionaries
        violations = ua.PhysicalViolations()
        violations.physical_violations = []
        for code in self.physical_violations:
            violation = ua.PhysicalViolation()
            violation.code = code
            violation.physical_violation_sensors = []
            for sensor_name in self.physical_violations[code]: 
                sensor = ua.PhysicalViolationSensor()
                sensor.sensor_name = sensor_name
                sensor.count = self.physical_violations[code][sensor_name]
                violation.physical_violation_sensors.append(sensor)
            violations.physical_violations.append(violation)

        # call function on server
        await client_val.nodes.objects.call_method(f"{nsidx}:return_physical_violations", self.conf["port"], violations)

def main():
    return mosaik_api.start_simulation(MonitoringRTU())

if __name__ == '__main__':
    main()    