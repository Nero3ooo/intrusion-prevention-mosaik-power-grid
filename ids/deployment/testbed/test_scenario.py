# test_scenario.py
# by Verena
# version 0.1
"""""
test scenario
This file consists of a simulation using the mosaik framework of a small neighboorhood and two attached RTUs. 
"""

import mosaik
from mosaik.util import connect_randomly, connect_many_to_one
from topology_loader.topology_loader import topology_loader
import random
import os
from distutils.util import strtobool
import time
import logging
import sys

def main(in_val = False):
    
    logging.getLogger("PyPower").setLevel(logging.CRITICAL)
    logger = logging.getLogger(__name__)
    
    # Simulator Configuration
    # specifies for Mosaik which simulators will be used
    global sim_config
    sim_config = {
        # CSV
        'CSV': {
            'python': 'mosaik_csv:CSV',
        },
        # DB
        'DB': {
            'cmd': 'mosaik-hdf5 %(addr)s',
        },
        # Household
        'HouseholdSim': {
            'python': 'householdsim.mosaik:HouseholdSim',
        },
        # PyPower (to solve PowerFlow Equations?)
        'PyPower': {
            'python': 'mosaik_pypower.mosaik:PyPower',
        },
        # WebVis
        # to make it locally viable at localhost:8000
        'WebVis': {
            'cmd': 'mosaik-web -s 0.0.0.0:8000 %(addr)s',
        },
        # RTU Simulation
        'RTUSim': {
            'python': 'mosaikrtu.rtu:MonitoringRTU',
        },
    }




    # main function of the simulation

    # needed to load configurations
    topoloader = topology_loader()
    if in_val:
        topoloader.rootdir = os.path.join(topoloader.rootdir, "/app")
    #     topoloader.flag = 0
    #     conf = topoloader.load_config("")
    #     
    # else:
    conf = topoloader.get_config()
    logger.debug(f"configfile:  {conf}")

    # configuration
    global START
    START = conf['start']

    global END
    END = int(conf['end'])

    global RT_FACTOR
    RT_FACTOR = float(conf['rt_factor'])
    
    global PV_DATA
    PV_DATA = os.path.join("data", conf['pv_data'])

    global GEN_DATA
    GEN_DATA = os.path.join("data",
                            conf['gen_data']) if 'gen_data' in conf else None

    global DEFAULT_VOLTAGE
    DEFAULT_VOLTAGE = float(conf['default_voltage'])

    global PROFILE_FILE
    PROFILE_FILE = os.path.join("data", conf['profile_file'])

    global GRID_NAME
    GRID_NAME = conf['grid_name']

    global GRID_FILE
    GRID_FILE = os.path.join("data", conf['grid_file'])

    global RTU_FILE_1
    RTU_FILE_1 = os.path.join("data", conf['rtu_file_1'])

    global RTU_FILE_2
    RTU_FILE_2 = os.path.join("data", conf['rtu_file_2'])

    global RTU_STATS_OUTPUT
    RTU_STATS_OUTPUT = bool(strtobool(conf['rtu_stats_output'].lower()))

    global PV_COUNT
    PV_COUNT = int(conf['pv_count'])

    global RECORD_TIMES
    RECORD_TIMES = bool(strtobool(conf['recordtimes'].lower()))

    global IN_VALIDATION
    IN_VALIDATION = in_val

    if RECORD_TIMES:
        try:
            os.remove('./outputs/times.csv')
        except OSError:
            pass
    # End of configuration
    
    while True:
        random.seed(23)
        # Will be used later to calculate to complete simulation times
        start_time = time.time()

        # Creation of the world
        world = mosaik.World(sim_config)
        logger.info("Created the simulation world.")
        logger.info("________________________________")
        logger.info("\n")

        # Creation of the scenario
        logger.info("Started simulation scenario creation.")
        create_scenario(world)
        logger.info("Created the simulation scenario.")
        logger.info("________________________________")
        logger.info("\n")

        # Run the simualtion world
        logger.info("Started simulation run.")
        #Since the simulation is partly running very slowly, we let it take all the time it needs,
        #otherwise the loggs are not readable due to the real-time factor warnings

        def ignore_rt_check(rt_factor, rt_start, rt_strict, sim):
            pass
        if not in_val:
            mosaik.scheduler.rt_check = ignore_rt_check

        if in_val:
            world.run(until=END, print_progress=False)
        else:
            world.run(until=END, rt_factor=RT_FACTOR, print_progress=False)
        
        # if RT_FACTOR == 0:
        #     world.run(until=END)  # As fast as possible
        # else:
        #     world.run(until=END, rt_factor=RT_FACTOR)  # slowed down by RT_FACTOR


        logger.info("Finished simulation run.")
        logger.info("________________________________")
        logger.info("\n")

        elapsed_time = time.time() - start_time
        logger.info("Elapsed time: {}".format(elapsed_time))
        logger.info("\n")
        logger.info("End of the simulation.")
        if in_val:
            break
        logger.info("Running simulation again because it was so fun!")
        


def create_scenario(world):
    # Creates the simulation scenario, e.g. creating simulators and connecting them

    # Start all simulators (PyPower, Household, PV, RTU)
    pypower = world.start('PyPower', step_size=60)

    # Household simulators have by default the step size of 15 minutes.
    householdsim = world.start('HouseholdSim')

    pvsim = world.start('CSV', sim_start=START, datafile=PV_DATA)
    if not GEN_DATA == None:
        gensim = world.start('HouseholdSim')

    # Start two RTU simulators
    rtusim_1 = world.start('RTUSim')
    rtusim_2 = world.start('RTUSim')

    # Instantiate models
    grid_inf = pypower.Grid(gridfile=GRID_FILE)
    grid = grid_inf.children

    houses = householdsim.ResidentialLoads(sim_start=START,
                                           profile_file=PROFILE_FILE,
                                           grid_name=GRID_NAME).children

    pvs = pvsim.PV.create(PV_COUNT)

    if not GEN_DATA == None:
        gens = gensim.ResidentialLoads(
            sim_start=START,
            profile_file=GEN_DATA,  # file with generators profiles
            grid_name=GRID_NAME).children

    rtu_sim_1 = rtusim_1.RTU(rtu_ref=RTU_FILE_1)
    rtu_1 = rtu_sim_1.children
    rtu_sim_2 = rtusim_2.RTU(rtu_ref=RTU_FILE_2)
    rtu_2 = rtu_sim_2.children

    # Start the database
    db = world.start('DB', step_size=60, duration=END)
    hdf5 = db.Database(filename='data/config_files/demo.hdf5')

    # Connect all entities
    # Connecting houses, pvs and gens to the grid
    connect_buildings_to_grid(world, houses, grid)
    connect_randomly(world, pvs, [e for e in grid if 'node' in e.eid], 'P')
    if not GEN_DATA == None:
        connect_buildings_to_grid(world, gens, grid)
    '''ADDED'''
    logger.info("Connected all entities")
    # Connecting houses, gens and PVs to the DB
    connect_many_to_one(world, houses, hdf5, 'P_out')
    connect_many_to_one(world, pvs, hdf5, 'P')
    if not GEN_DATA == None:
        connect_many_to_one(world, gens, hdf5, 'P_out')
    '''ADDED'''
    logger.info("Connected houses, gens and PV to DB")
    # Connecting RTUs to the grid
    connect_sensors_to_grid(world, rtu_1, grid)
    world.connect(grid_inf, rtu_sim_1, 'switchstates', async_requests=True)
    connect_sensors_to_grid(world, rtu_2, grid)
    world.connect(grid_inf, rtu_sim_2, 'switchstates', async_requests=True)
    '''ADDED'''
    logger.info("Connected RTUs to grid")
    nodes = [e for e in grid if e.type in ('RefBus, PQBus')]
    connect_many_to_one(world, nodes, hdf5, 'P', 'Q', 'Vl', 'Vm', 'Va')
    branches = [e for e in grid if e.type in ('Transformer', 'Branch')]
    connect_many_to_one(world, branches, hdf5, 'P_from', 'Q_from', 'P_to',
                        'P_from')
    '''ADDED'''
    logger.info("Done stuff before webvis start")
    # Web visualization
    if not IN_VALIDATION:
        webvis = world.start('WebVis', start_date=START, step_size=60)
        webvis.set_config(ignore_types=[
            'Topology', 'ResidentialLoads', 'Grid', 'Database', 'TopologyModel',
            'RTU', 'sensor', 'switch'
        ])

        vis_topo = webvis.Topology()

        connect_many_to_one(world, nodes, vis_topo, 'P', 'Vm')
        webvis.set_etypes({
            'RefBus': {
                'cls': 'refbus',
                'attr': 'P',
                'unit': 'P [W]',
                'default': 0,
                'min': 0,
                'max': 30000,
            },
            'PQBus': {
                'cls': 'pqbus',
                'attr': 'Vm',
                'unit': 'U [V]',
                'default': 230,
                'min': 0.99 * 230,
                'max': 1.01 * 230,
            },
        })

        connect_many_to_one(world, houses, vis_topo, 'P_out')
        webvis.set_etypes({
            'House': {
                'cls': 'load',
                'attr': 'P_out',
                'unit': 'P [W]',
                'default': 0,
                'min': 0,
                'max': 3000,
            },
        })

        connect_many_to_one(world, pvs, vis_topo, 'P')
        webvis.set_etypes({
            'PV': {
                'cls': 'gen',
                'attr': 'P',
                'unit': 'P [W]',
                'default': 0,
                'min': -10000,
                'max': 0,
            },
        })

        if not GEN_DATA == None:
            connect_many_to_one(world, gens, vis_topo, 'P_out')
        webvis.set_etypes({
            'GEN': {
                'cls': 'gen',
                'attr': 'P',
                'unit': 'P [W]',
                'default': 0,
                'min': -10000,
                'max': 0,
            },
        })


def connect_buildings_to_grid(world, houses, grid):
    # function to connect the simulated houses to the grid
    buses = filter(lambda e: e.type == 'PQBus', grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    house_data = world.get_data(houses, 'node_id')
    for house in houses:
        node_id = house_data[house]['node_id']
        world.connect(house,
                      buses[node_id], ('P_out', 'P'),
                      async_requests=True)


def connect_sensors_to_grid(world, rtu, grid):
    # function to connect the RTU sensors to the grid
    buses = filter(lambda e: e.type in ('PQBus', 'None'), grid)
    buses = {b.eid.split('-')[1]: b for b in buses}
    branches = filter(lambda e: e.type == 'Branch', grid)
    branches = {b.eid.split('-')[1]: b for b in branches}
    sensors = filter(lambda e: e.type == 'sensor', rtu)

    voltage_data = world.get_data(rtu, 'node')
    current_data = world.get_data(rtu, 'branch')

    for sensor in sensors:
        node_id = voltage_data[sensor]['node']
        world.connect(buses[node_id], sensor, 'Vm', async_requests=True)
        branch_id = current_data[sensor]['branch']
        world.connect(branches[branch_id],
                      sensor,
                      'I_imag',
                      'I_real',
                      async_requests=True)


# Needed to execute file as main
if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    main()
