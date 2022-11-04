from rtu_attack_engine import read_commands, write_commands, RTUAttackEngine

import json
import os
import logging

# Set to True to test the attack scenario manager.
TEST_ATTACK_SCENARIO_MANAGER = True


def load_scenario(file_path):
    """Load and return a scenario from a JSON file at the passed location."""
    # Make sure that the passed file path points to a JSON file.
    if not file_path.endswith('.json'):
        raise RuntimeError(f"Invalid type for file path {file_path}! (must be a .json file)")

    # Try to load the scenario dictionary from its respective JSON file.
    try:
        with open(file_path) as f:
            data = json.load(f)
    except IOError:
        raise RuntimeError(f"File {file_path} doesn't exist or can't be accessed!")

    # Save the attributes from the loaded dictionary in this scenario.
    loaded_scenario = AttackScenario(data['name'], data['commands'], data['rtus'])
    return loaded_scenario


class AttackScenario:
    """An attack scenario consisting of a name and a list of commands."""

    def __init__(self, name="New Scenario", commands=None, rtus=None):
        """Initialize a new scenario and optionally pass a name, a list of commands and a list of RTUs."""
        self.name = name
        if commands is not None and rtus is not None:
            self.commands = commands
            self.rtus = rtus
        else:
            self.commands = []
            self.rtus = []

        # Initialize a logger for errors of the attack engine.
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.ERROR)

    def add_command(self, rtu_info, command_type, element_number, new_value=None, delay=0):
        """Create and add a new command to the commands list if its parameters are valid."""
        # Check the passed command parameters.
        if self._valid_command_parameters(rtu_info, command_type, element_number, new_value, delay):
            # Check if the passed RTU is already in the RTU list of this scenario.
            # If this is the case, get and use its index in the RTU list.
            # Otherwise, append it to the list.
            try:
                rtu_index = self.rtus.index(rtu_info)
            except ValueError:
                rtu_index = len(self.rtus)
                self.rtus.append(rtu_info)

            # Create a command dictionary from the passed parameters and add it to the commands list.
            new_command = {
                'rtu': rtu_index,
                'type': command_type,
                'element_id': element_number,
                'delay': delay
            }
            if command_type in write_commands:
                new_command['value'] = new_value
            self.commands.append(new_command)

    def delete_command_by_index(self, index):
        """Delete a command from the commands list by its index, if the index is valid."""
        if index < 0 or index >= len(self.commands):
            self.logger.error(f"Invalid index for attack commands! (must be between 0 and {len(self.commands)})")
        else:
            del self.commands[index]

    def delete_command(self, rtu_info, command_type, element_number, new_value, delay):
        """Delete a command from the commands list, if it can be found."""
        rtu_index = self.rtus.index(rtu_info)
        found = False
        for command in self.commands:
            if command['rtu'] == rtu_index and command['type'] == command_type \
                    and command['element_id'] == element_number and command['value'] == new_value \
                    and command['delay'] == delay:
                self.commands.remove(command)
                found = True
                break
        if not found:
            self.logger.error("Command not found")

    def save(self, file_path):
        """Save this scenario in a JSON file at the passed location."""
        # Make sure that the passed file path points to a JSON file.
        if not file_path.endswith('.json'):
            raise RuntimeError(f"Invalid type for file path {file_path}! (must be a .json file)")

        # Create a dictionary with all important parameters from the scenario.
        scenario_dict = {
            'name': self.name,
            'commands': self.commands,
            'rtus': self.rtus
        }

        # Try to save the scenario dictionary in the respective JSON file.
        # Plus if there are still folders missing in the file path, create them beforehands.
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            with open(file_path, 'w') as f:
                json.dump(scenario_dict, f, indent=4)
        except IOError:
            raise RuntimeError(f"File {file_path} can't be created!")

    def execute(self, attack_engines):
        """Execute this scenario by using the passed attack engine(s)."""
        # Map all RTUs in the scenario to the passed attack engines.
        mapped_engines = self._map_rtus_to_engines(attack_engines)

        # Execute each command by using the respective attack engine.
        for command in self.commands:
            engine = mapped_engines[command['rtu']]
            if command['type'] in write_commands:
                engine.execute_command(command['type'], command['element_id'], command['value'], command['delay'])
            else:
                engine.execute_command(command['type'], command['element_id'])

    def _valid_command_parameters(self, rtu_info, command_type, element_number, new_value, delay):
        """Check if the passed parameters for a new command are valid."""
        # Check rtu info parameter
        if 'ip' not in rtu_info or 'port' not in rtu_info:
            self.logger.error(f"Invalid dictionary format for RTU info parameter!")
            return False
        if not isinstance(rtu_info['ip'], str):
            self.logger.error(f"Invalid type of RTU IP in the RTU info dictionary! (must be a string)")
            return False
        try:
            int(rtu_info['port'])
        except ValueError:
            self.logger.error(f"Invalid type of RTU port in the RTU info dictionary! (must be an integer)")
            return False

        # Check command type parameter
        if command_type not in read_commands and command_type not in write_commands:
            self.logger.error(f"Command {command_type} is invalid!")
            return False

        # Check element number parameter
        try:
            int(element_number)
        except ValueError:
            self.logger.error(f"Invalid type of element number parameter for {command_type}! (must be an integer)")
            return False
        if element_number < 0:
            self.logger.error(f"Invalid element number for {command_type}!")
            return False

        # Check new value parameter
        if command_type in write_commands:
            if new_value is None:
                self.logger.error(f"Missing new value parameter for {command_type}!")
                return False
            try:
                float(new_value)
            except ValueError:
                self.logger.error(f"Invalid type of new value parameter for {command_type}! (must be a float)")
                return False

        # Check delay parameter
        try:
            int(delay)
        except ValueError:
            self.logger.error(f"Invalid type of delay parameter! (must be an integer)")
            return False
        if delay < 0:
            self.logger.error(f"Invalid value for delay parameter! (must be >= 0)")
            return False

        return True

    def _map_rtus_to_engines(self, attack_engines):
        """Try to map the required RTUs for the scenario onto the passed attack engines.
        If there's an attack engine missing for a RTU, raise an exception.
        However if this mapping finished without any exceptions, the RTU index of a command equals
        the index of the matching attack engine in the mapped engines list."""
        mapped_engines = []
        for rtu in self.rtus:
            found = False
            for engine in attack_engines:
                if rtu['ip'] == engine.get_ip() and int(rtu['port']) == int(engine.get_port()):
                    found = True
                    mapped_engines.append(engine)
                    break
            if not found:
                raise RuntimeError(f"No matching attack engine passed for RTU {rtu['ip']}:{rtu['port']}!")
        return mapped_engines


def main():
    """Main method for testing the attack scenario manager if activated."""
    if TEST_ATTACK_SCENARIO_MANAGER:
        # Create RTU infos
        rtu_1 = {'ip': '127.0.0.1', 'port': 10502}
        rtu_2 = {'ip': '127.0.0.1', 'port': 10503}
        rtu_3 = {'ip': '127.0.0.1', 'port': 10504}

        # Create test scenario 1
        test_scenario_1 = AttackScenario("Test Scenario")
        test_scenario_1.add_command(rtu_2, 'read_trafo', 1)
        test_scenario_1.add_command(rtu_1, 'write_switch', 3, 1)
        test_scenario_1.add_command(rtu_2, 'write_max_current', 7, 1000000)

        # Create test scenario 2
        test_scenario_2 = AttackScenario("Test Scenario 2")
        test_scenario_2.add_command(rtu_1, 'read_volt_sensor', 9, 10)
        test_scenario_2.add_command(rtu_1, 'write_trafo', 1, -1)

        # Create test scenario 3
        test_scenario_3 = AttackScenario("Test Scenario 3")
        test_scenario_3.add_command(rtu_1, 'read_current_sensor', 4)
        test_scenario_3.add_command(rtu_2, 'write_switch', 2, 1)
        test_scenario_3.add_command(rtu_3, 'write_max_volt', 5, 9001)

        # Save all scenarios
        test_scenario_1.save('test_scenarios/Test Scenario 1.json')
        test_scenario_2.save('test_scenarios/Test Scenario 2.json')
        test_scenario_3.save('test_scenarios/Test Scenario 3.json')

        # Load all saved attack scenarios and print out their names, commands and RTUs.
        loaded_scenario_1 = load_scenario('test_scenarios/Test Scenario 1.json')
        print(loaded_scenario_1.name)
        print(loaded_scenario_1.commands)
        print(loaded_scenario_1.rtus)
        loaded_scenario_2 = load_scenario('test_scenarios/Test Scenario 2.json')
        print(loaded_scenario_2.name)
        print(loaded_scenario_2.commands)
        print(loaded_scenario_2.rtus)
        loaded_scenario_3 = load_scenario('test_scenarios/Test Scenario 3.json')
        print(loaded_scenario_3.name)
        print(loaded_scenario_3.commands)
        print(loaded_scenario_3.rtus)
        print()

        # Delete the second command of the first scenario and save it again.
        test_scenario_3.delete_command_by_index(1)
        test_scenario_3.save('test_scenarios/Test Scenario 3.json')

        # Create attack engines for the two RTUs of the testbed.
        attack_engine_1 = RTUAttackEngine("seccomm/Testbed/data/config_files/new_rtu_0.xml")
        attack_engine_2 = RTUAttackEngine("seccomm/Testbed/data/config_files/new_rtu_1.xml")
        attack_engines = [attack_engine_1, attack_engine_2]

        # Execute the test scenarios.
        loaded_scenario_1.execute(attack_engines)

        # Close the connection of the attack engines to the testbed.
        attack_engine_1.client.close()
        attack_engine_2.client.close()


if __name__ == '__main__':
    main()
