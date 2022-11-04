import json
import xml.etree.ElementTree as ET
import struct
import logging

# Set to True to test the parser by printing out the parsed elements.
TEST_PARSER = True

# Default path for the demo grid file
DEFAULT_GRID_FILE = "rtu-files/demo_mv_grid.json"


class RTUConfigParser:
    """A parser for reading out the contents of a given RTU config file."""

    def __init__(self, input_file, grid_file=DEFAULT_GRID_FILE, auto_parse=True):
        """Create the parser by initalizing all output variables and
        passing the location of the RTU config file that should be read."""
        self.input_file = input_file
        self.grid_file = grid_file
        self.ip = ''
        self.port = 0
        self.switches = []
        self.transformers = []
        self.voltage_sensors = []
        self.current_sensors = []
        self.transformer_taps = {}

        # Initialize a logger for warning the user if their RTU config file contains invalid entries.
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.WARNING)

        # Automatically parse the input file for the first time if enabled.
        if auto_parse:
            self.parse()

    def parse(self):
        """Parse the given RTU config file."""
        # Parse the grid file and get all transformer taps for every transformer beforehand.
        self._parse_trafo_taps()

        # Create an ElementTree from the config file and get its root.
        tree = ET.parse(self.input_file)
        root = tree.getroot()

        # Iterate over all childrens of the root and parse each child of interest.
        for child in root:
            if child.tag == 'ip':
                self.ip = child.text
            if child.tag == 'port':
                self.port = child.text
            if child.tag == 'reg':
                self._add_grid_element(child.attrib)

    def _parse_trafo_taps(self):
        """Parse all possible transformer taps for each transformer from the grid file."""
        # Get the transformer list & transformer types dictionary from the grid file.
        with open(self.grid_file) as f:
            data = json.load(f)
        trafos = data['trafo']
        trafo_types = data['trafo_types']

        # Add an entry to the transformer taps dictionary for each transformer in the transformer list.
        for trafo in trafos:
            # Get the name & type for the transformer
            name = trafo[0]
            trafo_type = trafo[3]

            # Get the according transformer type from the transformer types dictionary
            # and then the transformer taps dictionary for this type.
            trafo_taps_dict = trafo_types[trafo_type][6]

            # Convert the keys of the transformer taps dictionary from an integer representation of the first 16-bit
            # to a 64-bit float representation which also makes indexing these dictionaries way easier.
            for key in trafo_taps_dict:
                # Left shift the key to get the desired 64-bit float value as an integer
                shifted_key = int(key) << 48
                # Convert the integer to a 8 byte representation
                b8_key = struct.pack('Q', shifted_key)
                # Finally convert the 8 byte representation to a 64-bit float
                new_key = struct.unpack('d', b8_key)[0]

                # Change the key in the dictionary
                trafo_taps_dict[new_key] = trafo_taps_dict.pop(key)

            # Add the new entry to our own transformer taps dictionary (consisting of the transformer name as the key
            # and the modified transformer tap dictionary as the value).
            self.transformer_taps[name] = trafo_taps_dict

    def _add_grid_element(self, element):
        """Check what kind of grid element is currently being processed and add it accordingly to the output."""
        if element['type'] == 'co' and element['label'].startswith('switch_'):
            self._add_switch(element)
        elif element['type'] == 'hr' and element['label'].startswith('sensor_'):
            self._add_sensor(element)
        elif element['type'] == 'hr' and element['label'].startswith('tap-transformer_'):
            self._add_transformer(element)
        elif element['type'] == 'hr' and element['label'].startswith('max-'):
            self._add_max_value(element)
        else:
            self.logger.warning(f"Unknown grid element for entry {element}!")

    def _add_switch(self, element):
        """Create a new dictionary entry from the given switch coil and add it to the output."""
        label = element['label'].split('-')
        index = int(label[0].split('_')[1])
        new_switch = {
            'index': index,
            'address': element['index'],
            'name': label[0],
            'branch': label[1]
        }
        self.switches.append(new_switch)

    def _add_transformer(self, element):
        """Create a new dictionary from the given transformer register and add it to the output."""
        index = int(element['label'].split('_')[1])
        new_transformer = {
            'index': index,
            'address': element['index'],
            'name': element['label'],
        }

        # Get the transformer taps list from the transformer taps dictionary and add it to the new entry.
        # However if the transformer taps are missing for this transformer, return a warning.
        trafo_name = new_transformer['name'].split('-')[1]
        trafo_taps = self.transformer_taps.get(trafo_name)
        if trafo_taps:
            new_transformer['taps'] = trafo_taps
        else:
            self.logger.warning(f"No transformer taps found for {new_transformer['name']}! "
                                f"(Please make sure that every transformer has a defined transformer type "
                                f"in the grid file!)")

        self.transformers.append(new_transformer)

    def _add_sensor(self, element):
        """Create a new dictionary from the given (voltage or current) sensor register and add it to the output."""
        label = element['label'].split('-')
        index = int(label[0].split('_')[1])
        location = label[1]
        location_type = location.split('_')[0]
        new_sensor = {
            'index': index,
            'address': element['index'],
            'name': label[0],
        }

        # Differentiate between voltage and current sensors.
        if location_type == 'node':
            new_sensor['node'] = label[1]
            new_sensor['max_voltage'] = {}
            self.voltage_sensors.append(new_sensor)
        elif location_type == 'branch':
            new_sensor['branch'] = label[1]
            new_sensor['max_current'] = {}
            self.current_sensors.append(new_sensor)
        else:
            self.logger.warning(f"Unknown sensor location type for entry {element}! "
                                f"(found '{location_type}' but expected either 'node' or 'branch')")

    def _add_max_value(self, element):
        """Add the given max voltage/current register to its respective sensor.
        Note that a max value must be defined after its particular sensor
        in the RTU config file for the parser to connect both correctly."""

        # Get the index, label, location (e.g. branch_35) and
        # location type (branch or node) from the max value register.
        index = element['index']
        label = element['label']
        location = label.split('-')[1]
        location_type = location.split('_')[0]

        # Set the max value type and sensor list according to
        # whether the register is a max voltage or max current register.
        if location_type == 'node':
            max_value_type = 'max_voltage'
            sensor_list = self.voltage_sensors
        elif location_type == 'branch':
            max_value_type = 'max_current'
            sensor_list = self.current_sensors
        else:
            self.logger.warning(f"Unknown sensor location type for entry {element}! "
                                f"(found '{location_type}' but expected either 'node' or 'branch')")
            return

        # Iterate over the sensor list to find the matching sensor.
        # If there are multiple sensors with the same location,
        # pick the first one that doesn't have a max value register yet.
        matching_sensor = None
        for sensor in sensor_list:
            if sensor[location_type] == location and not sensor[max_value_type]:
                matching_sensor = sensor
                break

        # Create a new dictionary from the given max value register and add it to its matching sensor if there is any.
        if matching_sensor:
            new_max_value = {'address': index}
            matching_sensor[max_value_type] = new_max_value
        else:
            self.logger.warning(f"No matching sensor found for max value entry {element}! "
                                f"(Please make sure that a max value entry is always defined "
                                f"after its respective sensor entry!)")


def main():
    """Main method for testing the RTU config parser if activated."""
    if TEST_PARSER:
        test_parser = RTUConfigParser("seccomm/Testbed/data/config_files/new_rtu_1.xml")
        print("IP = " + test_parser.ip)
        print("Port = " + str(test_parser.port))
        print("\nSwitches:")
        print(*test_parser.switches, sep="\n")
        print("\nTransformers:")
        print(*test_parser.transformers, sep="\n")
        print("\nVoltage sensors:")
        print(*test_parser.voltage_sensors, sep="\n")
        print("\nCurrent sensors:")
        print(*test_parser.current_sensors, sep="\n")


if __name__ == '__main__':
    main()
