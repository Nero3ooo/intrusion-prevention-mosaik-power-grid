import logging
import sys
import os
sys.path.append(os.path.abspath("/app"))
import test_scenario

import xml.etree.ElementTree as ET

import asyncio
from asyncua import Server, ua
from asyncua.common.methods import uamethod
from asyncua.common.structures104 import new_struct, new_struct_field
import time

port = 10000
@uamethod
def validate(parent, rtu0Data, rtu1Data):
    global port

    print(f"Port1: {port}")
    if (len(rtu0Data.switches) + len(rtu0Data.others) > 0):
        print(rtu0Data)
        __create_xml(rtu0Data, 0, "192.168.0.19", port)
    if (len(rtu1Data.switches) + len(rtu1Data.others) > 0):
        print(rtu1Data)
        __create_xml(rtu1Data, 1, "192.168.0.19", port+1)

    port += 2
    print(f"Port2: {port}")
    
    # run simulation
    result = False
    while True:
        try:
            test_scenario.main(True)
            result = True
            break
        except OSError:
            bindport = port
            print(f"Port in bind {bindport}, wait 60 seconds")
            time.sleep(60)
        except Exception as e:
            name,number_of_zeros = e.args
            print(number_of_zeros)
            break
    
    if result:
        print(f"validation successful")

    return True
    #return False


def __create_xml(rtuData, rtuNumber, ip, port):
    ####TODO: get ports and identification from RTU, extend rtuData-Model
    dvdc = ET.Element("DVDC", label="Local substation " + str(rtuNumber+1))
    ET.SubElement(dvdc, "ip").text = ip
    ET.SubElement(dvdc, "port").text = str(port)
    identity = ET.SubElement(dvdc, "identity")
    ET.SubElement(identity, "vendor", name="UTwente 0", url="https://www.utwente.nl")
    ET.SubElement(identity, "product", name="PoorSecuritySubstation", code="PSS", model="PSS 1.0")
    ET.SubElement(identity, "version", major="0", minor="5")

    # Write Switches to XML-File
    for switch in rtuData.switches:
        ET.SubElement(dvdc, "reg",type=switch.reg_type, index=str(switch.index), label=switch.dev+"-"+switch.place, dt=switch.datatype).text = str(switch.value)

    # Write all other stuff to XML-File
    for other in rtuData.others:
        ET.SubElement(dvdc, "reg",type=other.reg_type, index=str(other.index), label=other.dev+"-"+other.place, dt=other.datatype).text = str(other.value)

    ET.SubElement(dvdc, "code").text = "mosaikrtu/conf/rtu_logic_good.py"
    
    tree = ET.ElementTree(dvdc)
    ET.indent(tree, '  ')
    tree.write("data/config_files/new_rtu_" + str(rtuNumber) + ".xml", xml_declaration=True,encoding='utf-8',method="xml")

async def main():
     # Setup Logging for this package
    logging.getLogger('pymodbus3').setLevel(logging.CRITICAL)

    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    #handler = OPCNetworkLogger()
    #logger.addHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)

    # setup our server
    server = Server()
    await server.init()
    server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")

    # setup our own namespace, not really necessary but should as spec
    uri = "http://itsis-blackout.ids/"
    idx = await server.register_namespace(uri)

    # Create data structure for switches
    switch_data, _ = await new_struct(server, idx, "SwitchData", [
        new_struct_field("dev", ua.VariantType.String),
        new_struct_field("place", ua.VariantType.String),
        new_struct_field("reg_type", ua.VariantType.String),
        new_struct_field("index", ua.VariantType.Int32),
        new_struct_field("datatype", ua.VariantType.String),
        new_struct_field("value", ua.VariantType.Boolean)
    ])
    # Create data structure for meters & transformer
    other_data, _ = await new_struct(server, idx, "OtherData", [
        new_struct_field("dev", ua.VariantType.String),
        new_struct_field("place", ua.VariantType.String),
        new_struct_field("reg_type", ua.VariantType.String),
        new_struct_field("index", ua.VariantType.Int32),
        new_struct_field("datatype", ua.VariantType.String),
        new_struct_field("value", ua.VariantType.Float)
    ])

    # Create nested data structure that includes switch and meter data
    _, _ = await new_struct(server, idx, "RTUData", [
        new_struct_field("ts", ua.VariantType.Float),
        new_struct_field("switches", switch_data, array=True),
        new_struct_field("others", other_data, array=True),
    ])

    await server.load_data_type_definitions()







    # populating our address space
    # server.nodes, contains links to very common nodes like objects and root
    # Set method to be used by clients
    await server.nodes.objects.add_method(
        ua.NodeId("validate", idx),
        ua.QualifiedName("validate", idx),
        validate,
        [ua.RTUData()],
        [ua.VariantType.Boolean],
    )

    logger.info("Starting server!")
    async with server:
        while True:
            await asyncio.sleep(1)
            logger.debug("Server is still running.")
