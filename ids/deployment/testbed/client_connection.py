# client_connections.py
# by Verena
# version 0.1
'''
Client Connection
Connects to Modbus TCP Clients to the running Simulation and both Modbus Servers each representing one subgrid/RTU.
Additionaly output files are generated for the data measured by each subgrid.
'''

from pymodbus3.constants import Endian
from pymodbus3.payload import BinaryPayloadDecoder
from pymodbus3.payload import BinaryPayloadBuilder
from pymodbus3.client.sync import ModbusTcpClient as ModbusClient

from time import sleep
import os

global PRINT_READINGS_TO_CONSOLE
PRINT_READINGS_TO_CONSOLE = False  # false = only general output will sent to the terminal and the detailed results will be saved to the output files, # true = the detailed sensory readings will be sent to the terminal, too


def main():
    # main function to start the readings
    print("\n")
    print(
        "Starting the client connection via Modbus to both subgrids.\nThe generated data will be saved to the outputs folder."
    )

    # Connecting to the subgrid/RTU 0
    print("Trying to connect to subgrid/RTU 0.")
    client_0 = ModbusClient('127.0.0.1', port=10502)
    client_0.connect()

    # Output file for subgrid 0
    FILENAME_0 = 'outputs/subgrid_0_output.csv'
    try:
        os.remove(FILENAME_0)
    except OSError:
        pass
    fd_0 = open(FILENAME_0, 'w+')
    introrow = "s3;sensor_13_v;sensor_14_v;sensor_16_v;sensor_17_v;sensor_18_v;sensor_15_v;sensor_19_v;sensor_20_v;sensor_21_v;sensor_22_v;sensor_23_v;sensor_24_v;sensor_13_c;sensor_14_c;sensor_16_c;sensor_17_c;sensor_18_c;sensor_15_c;sensor_19_c;sensor_20_c;sensor_21_c;sensor_22_c;sensor_23_c;sensor_24_c;\n"
    # This is highly specific with respect to the used grid topology.
    fd_0.write(introrow)

    # Connecting to the subgrid/RTU 1
    print("Trying to connect to subgrid/RTU 1.")
    client_1 = ModbusClient('127.0.0.1', port=10503)
    client_1.connect()

    # Output file for subgrid 1
    FILENAME_1 = 'outputs/subgrid_1_output.csv'
    try:
        os.remove(FILENAME_1)
    except OSError:
        pass
    fd_1 = open(FILENAME_1, 'w+')
    introrow = "s1;s2;sensor_1_v;sensor_2_v;sensor_3_v;sensor_4_v;sensor_5_v;sensor_6_v;sensor_7_v;sensor_8_v;sensor_9_v;sensor_10_v;sensor_11_v;sensor_12_v;sensor_1_c;sensor_2_c;sensor_3_c;sensor_4_c;sensor_5_c;sensor_6_c;sensor_7_c;sensor_8_c;sensor_9_c;sensor_10_c;sensor_11_c;sensor_12_c;\n"
    # This is highly specific with respect to the used grid topology.
    fd_1.write(introrow)

    # Listening to data sets
    print("\nStarting to listen to data sets:\n")
    if not PRINT_READINGS_TO_CONSOLE:
        print("...")
    i = 0
    while i < 20:
        if PRINT_READINGS_TO_CONSOLE:
            print("________________")
            print("Read data set " + str(i) + " from both RTUs:")

        read_data_from_client_new(client_0, fd_0, 1, 12)

        if PRINT_READINGS_TO_CONSOLE:
            print("_ _ _ _ _ _ _ _ _")

        read_data_from_client_new(client_1, fd_1, 2, 12)

        i = i + 1
    print("\nFinished listening to data:\n")

    # Closing the output files
    fd_0.close()
    fd_1.close()

    # Closing the client/subgrid connection
    client_0.close()
    client_1.close()


def read_data_from_client_new(client, file, switch_count, sensor_count):
    # reads the one row of data generated in one simulation step

    # switch reading
    switches_result = client.read_coils(0, switch_count, unit=1)

    switches = []
    for x in range(switch_count):
        switches.append(switches_result.bits[x])

    if PRINT_READINGS_TO_CONSOLE:
        print("." * 10 + " SWITCHES " + "." * 10)
        for x in range(switch_count):
            print("Nr. " + str(x) + " Wert: " + str(switches[x]))
        print("." * 25)

    # voltage and current reading
    result = client.read_holding_registers(0, sensor_count * 8, unit=1)
    decoder = BinaryPayloadDecoder.from_registers(result.registers,
                                                  endian=Endian.Big)

    values = []
    for x in range(sensor_count * 2):
        values.append(decoder.decode_64bit_float())

    if PRINT_READINGS_TO_CONSOLE:
        print("*" * 10 + " VALUES " + "*" * 10)
        for x in range(sensor_count * 2):
            if x < sensor_count:
                print("Value Nr. " + str(x) + " Voltage: " + str(values[x]))
            else:
                print("Value Nr. " + str(x - sensor_count) + " Current: " +
                      str(values[x]))
        print("." * 25)

    # creation of csv row for data storage
    csvrow = ""
    for x in range(len(switches)):
        csvrow = csvrow + str(switches[x]) + ";"

    for x in range(len(values)):
        csvrow = csvrow + str(values[x]) + ";"

    file.write(csvrow)
    file.write("\n")
    sleep(1)


# Needed to execute file as main
if __name__ == '__main__':
    main()
