import xmltodict
import json

# The function adds the indices used by modbus to the config file used by the LM
# To use the function please specify the path of the two config files manually
# IMPORTANT: switches are added manually as they are not properly identifiable in the config files
# Unfortunately switches don't have a consequent naming scheme.
def addModbusRegistersToRTUs():
    # Read config files
    path = 'Implementation/test_input_files/rtu_0.json'

    with open(path) as jsonFile:
        with open('Testbed/data/config_files/new_rtu_0.xml') as xmlFile:
            xml = xmltodict.parse(xmlFile.read())
            rtu = json.load(jsonFile)
            #print(xml['DVCD']['reg'])

            # Modify meters
            for r in rtu['meters']:
                for e in xml['DVCD']['reg']:
                    if e['@label'] == str(r['id']) + '-node_' + str(r['bus_id']):
                        print(e)
                        r['hr_index_voltage'] = e['@index']
                    elif e['@label'] == r['id'] + '-' + r['power_line_id']:
                        print(e)
                        r['hr_index_current'] = e['@index']

            # Write back to file
            f = open(path, "w")
            f.write(json.dumps(rtu, indent=4))
            f.close()

if __name__ == "__main__":
    addModbusRegistersToRTUs()
