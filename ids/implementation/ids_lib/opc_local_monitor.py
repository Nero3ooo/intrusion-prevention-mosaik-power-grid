import asyncio
import json
import logging
import queue
import sys
import time
import psutil

from asyncua import Client, Server, ua
from asyncua.common.methods import uamethod

from asyncua.common.structures104 import new_struct, new_struct_field
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.server.user_managers import CertificateUserManager
from asyncua.ua.uaerrors import BadUnexpectedError
from pymodbus3.constants import Endian
from pymodbus3.payload import BinaryPayloadDecoder
from pymodbus3.client.sync import ModbusTcpClient as ModbusClient

from .config.config_lm import LMConfig
from .req_checker_local import ReqCheckerLocal


class OPCNetworkLogger(logging.Handler):
    """ Hooks normal logging functions and queues messages to also be emitted via OPC"""

    def emit(self, record):
        lm.log.put_nowait({
            "message": record.getMessage(),
            "severity": record.levelname}
        )


class C2EventListener:
    """ Listens to events from c&c server"""

    async def event_notification(self, event):
        msg = event.Message.Text
        if msg == "reconfigure":
            pass
        elif msg == "isRegistered":
            lm.isRegistered = True
            logger.propagate = False
        elif msg.startswith('lmRemoved_'):
            pass
        else:
            logger.error("Received unhandled event from server '%r'" % event)


class LM:
    """Implements a OPC-networked Local Monitor"""

    def __init__(self, config: LMConfig):
        self.config = config
        self.__rtu_conf = json.loads(self.config.rtu_config)
        self.__neighborhood_monitors = []  # Each LM has 2 NMs
        self.log = queue.SimpleQueue()  # Queue for buffering log messages until they can be sent via OPC
        self.violation_queue = queue.SimpleQueue()  # Queue for buffering violation messages until they are sent by the LM
        self.isRegistered = False  # True if this LM has registered with the c2
        self.__modbus_client = None  # Client connected to Modbus RTU

    async def __init(self) -> None:
        """Initialize LM. Register with c&c server and connect to RTU"""
        await self.__register_to_c2()
        logger.info("finished initialization")

    async def __start_opc_server(self) -> None:
        cert_user_manager = CertificateUserManager()
        self.__server = Server(user_manager=cert_user_manager)
        server = self.__server

        # security settings
        self.__server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])

        await cert_user_manager.add_user(self.config.c2_cert, name="c2")
        await cert_user_manager.add_user(self.config.nm_cert, name="nm")

        await server.load_certificate(self.config.cert)
        await server.load_private_key(self.config.private_key, self.config.private_key_password)

        await server.init()
        server.set_endpoint(self.config.lm_opc_address)
        logger.info(f"LM serving OPC Server on: {self.config.lm_opc_address}")

        idx = await server.register_namespace(self.config.opc_domain)
        # Define custom type: LocalMonitor
        opcLMType = await server.nodes.base_object_type.add_object_type(idx, "LocalMonitor")
        self.__idx = idx

        # Create data structure for switches
        switch_data, _ = await new_struct(server, idx, "SwitchData", [
            new_struct_field("id", ua.VariantType.String),
            new_struct_field("value", ua.VariantType.Boolean)
        ])
        # Create data structure for meters
        meter_data, _ = await new_struct(server, idx, "MeterData", [
            new_struct_field("id", ua.VariantType.String),
            new_struct_field("current", ua.VariantType.Float),
            new_struct_field("voltage", ua.VariantType.Float)
        ])
        # Create nested data structure that includes switch and meter data
        _, _ = await new_struct(server, idx, "RTUData", [
            new_struct_field("ts", ua.VariantType.Float),
            new_struct_field("switches", switch_data, array=True),
            new_struct_field("meters", meter_data, array=True),
        ])

        # System related statistics
        _, _ = await new_struct(server, idx, "UsageData", [
            new_struct_field("cpu_load", ua.VariantType.Float),
            new_struct_field("memory_load", ua.VariantType.Float),
        ])

        # Load all new data structures to server
        await server.load_data_type_definitions()

        # Add data node with rtu data to lm server
        data_object = ua.RTUData()
        data_object.switches = []
        data_object.values = []
        data_var = await opcLMType.add_variable(idx, "data", ua.Variant(data_object, ua.VariantType.ExtensionObject))
        await data_var.set_modelling_rule(True)

        # Add uuid data node to lm server
        uuid_var = await opcLMType.add_property(idx, "uuid", self.config.uuid)
        await uuid_var.set_modelling_rule(True)

        usage_object = ua.UsageData()
        usage_var = await opcLMType.add_variable(idx, "usage", ua.Variant(usage_object, ua.VariantType.ExtensionObject))
        await usage_var.set_modelling_rule(True)

        # Actually create the LM Object
        self.opc_lm_ref = await server.nodes.objects.add_object(self.__idx, "LM", opcLMType)

        # Get a reference to the data object once here
        # this is the object we write our rtu measurements to
        self.opc_lm_data_ref = await self.opc_lm_ref.get_child([f"{self.__idx}:data"])

        # this is the object we write our usage to
        self.opc_lm_usage_ref = await self.opc_lm_ref.get_child([f"{self.__idx}:usage"])

        # Add method to register neighborhood monitors
        await self.opc_lm_ref.add_method(self.__idx,
                                         "registerNM",
                                         self.register_nm,
                                         [ua.VariantType.Guid, ua.VariantType.String],
                                         [ua.VariantType.StatusCode])

        await self.opc_lm_ref.add_method(self.__idx,
                                         "unregisterNM",
                                         self.unregister_nm,
                                         [ua.VariantType.Guid, ua.VariantType.String],
                                         [ua.VariantType.StatusCode])

        # Create custom event that is used for Requirement violations
        req_violation_event = await server.create_custom_event_type(idx, 'ReqViolationEvent',
                                                                    ua.ObjectIds.BaseEventType,
                                                                    [
                                                                        ('requirement', ua.VariantType.Int32),
                                                                        ('component_id', ua.VariantType.String),
                                                                    ])
        self.__violation_event_generator = await self.__server.get_event_generator(req_violation_event)

        # Create custom event that is used for General Logging purposes
        log_event = await server.create_custom_event_type(idx, 'LogEvent',
                                                          ua.ObjectIds.BaseEventType,
                                                          [
                                                              ('uuid', ua.VariantType.String),
                                                              ('type', ua.VariantType.String),
                                                              ('severity', ua.VariantType.String),
                                                              ('message', ua.VariantType.String),
                                                          ])
        self.__log_event_generator = await self.__server.get_event_generator(log_event)

        # Create custom event that stores url
        self.event_type = await self.__server.create_custom_event_type(self.__idx, 'LMEvent',
                                                                       ua.ObjectIds.BaseEventType,
                                                                       [('address', ua.VariantType.String)])
        self.__data_event_generator = await self.__server.get_event_generator(self.event_type, self.opc_lm_ref)

        # Set up requirement checker
        global req_checker
        req_checker = ReqCheckerLocal(self.__rtu_conf, self.opc_lm_data_ref, self.violation_queue)

        # heartbeat event to check if component is still alive and connected to c2 server
        # should not print anything in the console, only if not available (error message)
        self.heartbeat_event = await server.create_custom_event_type(idx, 'Heartbeat',
                                                                     ua.ObjectIds.BaseEventType,
                                                                     [('Message', ua.VariantType.String),
                                                                      ('sender', ua.VariantType.String)])
        self.__heartbeat_event_generator = await self.__server.get_event_generator(self.heartbeat_event)
        self.__heartbeat_event_generator.event.Message = 'Still alive'
        self.__heartbeat_event_generator.event.sender = self.config.uuid

    async def __register_to_c2(self) -> None:
        """Register as new LM to c&c server"""

        # We use a temporary client as we do not need it later on
        client = Client(url=self.config.c2_address)
        self.client = client

        await client.set_security(
            SecurityPolicyBasic256Sha256,
            certificate=self.config.cert,
            private_key=self.config.private_key,
            private_key_password=self.config.private_key_password,
            server_certificate=self.config.c2_cert
        )

        # async with Client(url=self.config.c2_address) as client:
        logger.info(f"registering to c2 with id: {self.config.uuid}")

        while True:
            try:
                await client.connect()
                logger.info("Connected to c&c Server")
                break
            except BaseException as e:
                logger.error("Connection error while connecting to c&c Server. Retrying in 5 seconds")
                await asyncio.sleep(5)

        await client.load_data_type_definitions()
        idx = await client.get_namespace_index(self.config.opc_domain)
        root = client.get_root_node()

        # Register ourselves as a LM looking for work
        c2 = await root.get_child(["0:Objects", "{}:C2".format(idx)])
        await c2.call_method("{}:registerLM".format(idx),
                             str(self.config.uuid),
                             self.config.lm_opc_address,
                             self.config.rtu_config)

        # Create EventListener to listen to configurationChanged Events
        handler = C2EventListener()
        subscription = await self.client.create_subscription(100, handler)
        while True:
            try:
                await subscription.subscribe_events()
                break
            except asyncio.exceptions.TimeoutError:
                logger.error(
                    "Connection timeout while subscribing to C&C events. Retrying in 5 seconds")
                await asyncio.sleep(5)

    @uamethod
    async def register_nm(self, parent, id: str) -> ua.StatusCode:
        """Registers an NM with this LM. Adds the NM to the pool of connected NMs and sends new sensor information"""

        # Create OPC Object
        try:
            # This NM is already registered.
            await self.__server.nodes.objects.get_child(f"{self.__idx}:{id}")
            pass
        except Exception as err:
            # Register this NM
            # Save neighborhood monitor references for internal use
            if len(self.__neighborhood_monitors) < 2:
                opc_ref = await self.__server.nodes.objects.add_object(self.__idx, id)
                self.__neighborhood_monitors.append({
                    "id": id,
                    "opc_ref": opc_ref
                })
                logger.debug("Registered NM " + str(id) + " to LM " + str(self.config.uuid))
            else:
                raise Exception("This LM already has two NMs")

        return ua.StatusCodes.Good

    @uamethod
    async def unregister_nm(self, parent, nm_id) -> ua.StatusCode:
        """ Unregisters an NM from an LM (when it has shut down or stopped responding) in order for the LM to register a new one"""

        # Check if NM is actually in the list
        for nm in self.__neighborhood_monitors:
            if nm['id'] == nm_id:
                # Remove NM from registered list
                self.__neighborhood_monitors.remove(nm)
                logger.debug("Unregistered NM " + str(nm_id) + " from " + str(self.config.uuid))
                # TODO: Change status code
                return ua.StatusCodes.Good
        return ua.StatusCodes.BadUnexpectedError

    async def __connect_to_rtu(self) -> None:
        """Connects to a RTU via modbus"""
        mc = ModbusClient(self.config.rtu_modbus_host, port=self.config.rtu_modbus_port)
        try:
            if not mc.connect() and mc.read_coils(0, 1, unit=1):
                logger.error(f"Error connecting to Modbus Server"
                             f"'{self.config.rtu_modbus_host}:{self.config.rtu_modbus_port}'")
            else:
                self.__modbus_client = mc
                logger.info(f"Connected to Modbus Server "
                            f"'{self.config.rtu_modbus_host}:{self.config.rtu_modbus_port}'")
        except Exception as e:
            logger.error(e)

        await self._log_to_opc()

    async def _read_modbus(self) -> bool:
        """Reads current sensor values via modbus and saves readings to data node."""

        # Connect to Modbus if not already connected
        if not self.__modbus_client:
            await self.__connect_to_rtu()
            return False

        # Create new data object for this reading
        opc_data = ua.RTUData()
        opc_data.ts = time.time()  # Note that this is ingestion time into our system and not measurement time
        opc_data.switches = []
        opc_data.meters = []

        # Get switch and meter info from config files
        switches = self.__rtu_conf["switches"]
        meters = self.__rtu_conf["meters"]

        try:
            for s in switches:
                # Get coil index from config file
                co_index = int(s["co_index"])
                # Read value at coil index from modbus
                # Note: the length of a coil register is 1 byte
                coil_data = self.__modbus_client.read_coils(co_index, 1, unit=1)
                # Create new data object to store switch data
                switch_data = ua.SwitchData()
                switch_data.id = s["id"]
                switch_data.value = coil_data.bits[:1]
                opc_data.switches.append(switch_data)

            for m in meters:
                # Get holding registers indices from config file
                hr_index_current = int(m["hr_index_current"])
                hr_index_voltage = int(m["hr_index_voltage"])
                # Read and decode hr values from modbus
                # Note: the length of a holding register is 8 bytes
                hr_data_current = self.__modbus_client.read_holding_registers(hr_index_current, 8, unit=1)
                hr_data_voltage = self.__modbus_client.read_holding_registers(hr_index_voltage, 8, unit=1)
                decoder_current = BinaryPayloadDecoder.from_registers(hr_data_current.registers, endian=Endian.Big)
                decoder_voltage = BinaryPayloadDecoder.from_registers(hr_data_voltage.registers, endian=Endian.Big)
                # Create new data object to store meter data
                meter_data = ua.MeterData()
                meter_data.id = m["id"]
                meter_data.current = decoder_current.decode_64bit_float()
                meter_data.voltage = decoder_voltage.decode_64bit_float()
                opc_data.meters.append(meter_data)

            # Write new reading into data node
            await self.opc_lm_data_ref.write_value(opc_data)
            # Notify NM of data change
            await self._notify_nm()

        except Exception as e:
            logger.error(e)
            self.__modbus_client = None
            return False
        return True

    async def _notify_nm(self):
        """Notify subscribed NMs about data changes """
        self.__data_event_generator.event.address = self.config.lm_opc_address
        await self.__data_event_generator.trigger()

    async def _log_to_opc(self):
        # Wait until we have registered with the c2 and before sending log messages
        if not self.isRegistered:
            return
        # Emit all queued log messages as events
        while not self.log.empty():
            try:
                event = self.log.get_nowait()
                self.__log_event_generator.event.uuid = self.config.uuid
                self.__log_event_generator.event.severity = event["severity"]
                self.__log_event_generator.event.message = event["message"]
                self.__log_event_generator.event.type = "LM"
                await self.__log_event_generator.trigger()
            except queue.Empty:
                return

    async def _report_violation_via_opc(self, vio_queue):
        """Report each violation in the queue to the c2 server."""
        # Loop over the whole queue
        while not vio_queue.empty():
            violation = vio_queue.get_nowait()
            self.__violation_event_generator.event.requirement = violation["req_id"]
            self.__violation_event_generator.event.component_id = violation["component_id"]
            await self.__violation_event_generator.trigger()

    async def _monitor_usage(self):
        usage_data = ua.UsageData()
        usage_data.cpu_load = psutil.cpu_percent(interval=0)
        usage_data.memory_load = psutil.virtual_memory().percent
        await self.opc_lm_usage_ref.write_value(usage_data)

    async def run(self) -> None:
        """Run LM"""
        # Start OPC Server
        await self.__start_opc_server()
        async with self.__server:
            # Initialize
            await self.__init()

            # Run forever
            while True:
                try:
                    await self.__heartbeat_event_generator.trigger()
                    if await self._read_modbus():
                        await req_checker.check_requirements()
                        await self._report_violation_via_opc(self.violation_queue)
                except Exception as err:
                    logger.error("Exception in local monitor: %s", err)
                # Send new logging messages to opc
                await self._log_to_opc()
                await self._monitor_usage()
                await asyncio.sleep(1)


async def main(config: LMConfig):
    # Setup Logging for this package
    logging.getLogger('pymodbus3').setLevel(logging.CRITICAL)

    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = OPCNetworkLogger()
    logger.addHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)

    # Create and run LM
    global lm
    lm = LM(config)
    await lm.run()
