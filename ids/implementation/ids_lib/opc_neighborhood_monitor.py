import asyncio
import logging
import queue
import sys

import psutil
from asyncua import Client, Server, ua
from asyncua.common.structures104 import new_struct, new_struct_field
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.server.user_managers import CertificateUserManager

from .config.config_nm import NMConfig
from .req_checker_neighborhood import ReqCheckerNeighborhood

class OPCNetworkLogger(logging.Handler):
    """ Hooks normal logging functions and queues messages to also be emitted via OPC"""

    def emit(self, record):
        nm.log_queue.put_nowait({
            "message": record.getMessage(),
            "severity": record.levelname}
        )


class C2EventListener:
    """ Listens to events from c&c server"""

    async def event_notification(self, event):
        msg = event.Message.Text
        if msg == "reconfigure":
            await nm.refresh_config()
        elif msg == "isRegistered":
            nm.isRegistered = True
            logger.propagate = False
        elif msg.startswith('nmRemoved_'):
            pass
        elif msg.startswith('lmRemoved_'):
            pass
            #logger.debug(msg[10:])
            #nm.unregister_lm(msg[10:])
        else:
            logger.error("Received unhandled event from server '%r'" % event)


class RTUDataEventListener:
    """ Listens to events from local monitor"""

    async def event_notification(self, event):
        # Data has changed so reevaluate requirements
        nm.lm_to_check.append(event.address)


class NM:
    """Implements a Neighborhood Monitor"""

    def __init__(self, config: NMConfig):
        self.c2_address = config.c2_address
        self.uuid = str(config.uuid)
        self.opc_nm_ref = None
        self.opc_nm_usage_ref = None
        self.client_c2 = None
        self.client_lms = []
        self.idx = 0
        self.config = config
        self.__br = []  # border regions

        self.log_queue = queue.SimpleQueue()  # Queue for buffering log messages until they can be sent via OPC
        self.violation_queue = queue.SimpleQueue()  # Queue for buffering violation messages until they are sent vio OPC
        self.isRegistered = False  # True if this NM has registered with the c2

        self.lm_to_check = []

    async def __init(self):
        """Initialize NM by registering to c&c server"""
        # Start the opc client and connect to c2 server
        await self.__start_opc_client()
        logger.info("finished initialization")

    async def __start_opc_client(self) -> None:
        client_c2 = Client(url=self.c2_address)
        self.client_c2 = client_c2

        # security settings
        await client_c2.set_security(
            SecurityPolicyBasic256Sha256,
            certificate=self.config.cert,
            private_key=self.config.private_key,
            private_key_password=self.config.private_key_password,
            server_certificate=self.config.c2_cert
        )

        while True:
            try:
                await client_c2.connect()
                logger.info("Connected to c&c Server")
                break
            except BaseException as e:
                logger.error(f"{self.uuid} Connection error while connecting to c&c Server. Retrying in 5 seconds")
                await asyncio.sleep(5)

        await client_c2.load_data_type_definitions()
        await self.__register_to_c2()

    async def __start_opc_server(self) -> None:
        """
            Starts an opc server for the neighborhood_monitor to publish its data and events in.
            The C2 Server can subscribe to changes on this server.
        """

        cert_user_manager = CertificateUserManager()
        self.__server = Server(user_manager=cert_user_manager)
        server = self.__server

        # security settings
        self.__server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])

        await cert_user_manager.add_user(self.config.c2_cert, name="c2")

        await server.load_certificate(self.config.cert)
        await server.load_private_key(self.config.private_key, self.config.private_key_password)

        await server.init()
        server.set_endpoint(self.config.nm_opc_address)

        logger.info(f"NM serving OPC Server on: {self.config.nm_opc_address}")

        idx = await server.register_namespace(self.config.opc_domain)
        self.__idx = idx

        # Set up requirement checker
        global req_checker
        req_checker = ReqCheckerNeighborhood(self.__br, self.client_lms, self.violation_queue, logger)

        # System related statistics
        opcNMType = await server.nodes.base_object_type.add_object_type(idx, "NeighborhoodMonitor")
        
        _, _ = await new_struct(server, idx, "UsageData", [
            new_struct_field("cpu_load", ua.VariantType.Float),
            new_struct_field("memory_load", ua.VariantType.Float),
        ])

        # Load all new data structures to server
        await server.load_data_type_definitions()

        usage_object = ua.UsageData()
        usage_var = await opcNMType.add_variable(idx, "usage", ua.Variant(usage_object, ua.VariantType.ExtensionObject))
        await usage_var.set_modelling_rule(True)

        # Actually create the NM Object
        self.opc_nm_ref = await server.nodes.objects.add_object(self.__idx, "NM", opcNMType)

        # Get a reference to the data object once here
        # this is the object we write our usage measurements to
        self.opc_nm_usage_ref = await self.opc_nm_ref.get_child([f"{self.__idx}:usage"])

        # Create custom event that is used for Requirement violations
        req_violation_event = await server.create_custom_event_type(idx, 'ReqViolationEvent',
                                                                    ua.ObjectIds.BaseEventType,
                                                                    [
                                                                        # ('timestamp', ua.VariantType.String),
                                                                        ('requirement', ua.VariantType.Int32),
                                                                        ('component_id', ua.VariantType.String),
                                                                    ])
        self.__violation_event_generator = await self.__server.get_event_generator(req_violation_event)

        # Create custom event that is used for General Logging purposes
        log_event = await server.create_custom_event_type(idx, 'LogEvent',
                                                          ua.ObjectIds.BaseEventType,
                                                          [
                                                              ('uuid', ua.VariantType.String),
                                                              ('severity', ua.VariantType.String),
                                                              ('type', ua.VariantType.String),
                                                              ('message', ua.VariantType.String),
                                                          ])
        self.__log_event_generator = await self.__server.get_event_generator(log_event)

        # heartbeat event to check if component is still alive and connected to c2 server
        # should not print anything in the console, only if not available (error message)
        heartbeat_event = await server.create_custom_event_type(idx, 'Heartbeat',
                                                                ua.ObjectIds.BaseEventType,
                                                                [('Message', ua.VariantType.String),
                                                                 ('sender', ua.VariantType.String)])

        self.__heartbeat_event_generator = await self.__server.get_event_generator(heartbeat_event)
        self.__heartbeat_event_generator.event.Message = 'Still alive'
        self.__heartbeat_event_generator.event.sender = self.config.uuid


    async def __register_to_lm(self, lm_url):
        """Register this nm to the given lm. """
        client_lm = Client(url=lm_url)

        await client_lm.set_security(
            SecurityPolicyBasic256Sha256,
            certificate=self.config.cert,
            private_key=self.config.private_key,
            private_key_password=self.config.private_key_password,
            server_certificate=self.config.lm_cert
        )

        # Connect with client
        while True:
            try:
                await client_lm.connect()
                logger.info("NM connected to LM")
                break
            except BaseException as e:
                logger.error("Connection error while connecting to LM. Retrying in 5 seconds")
                await asyncio.sleep(5)

        # Load lm data type definitions
        await client_lm.load_data_type_definitions()

        idx = await client_lm.get_namespace_index(self.config.opc_domain)
        root = client_lm.get_root_node()
        lm = await root.get_child(["0:Objects", f"{idx}:LM"])

        # Get event type for events from LM server
        lm_event_type = await root.get_child(["0:Types", "0:EventTypes", "0:BaseEventType", "2:LMEvent"])

        # Get lm data node that stores modbus rtu data
        data_node = await root.get_child(["0:Objects", f"{idx}:LM", f"{idx}:data"])
        usage_node = await root.get_child(["0:Objects", f"{idx}:LM", f"{idx}:usage"])

        # Store lm references to private collection
        self.client_lms.append({"lm": lm, "url": lm_url, "data_node": data_node, "usage_node": usage_node})

        # Create EventListener to listen to new sensor data
        handler = RTUDataEventListener()
        subscription = await client_lm.create_subscription(1000, handler)
        while True:
            try:
                await subscription.subscribe_events(lm, lm_event_type)
                break
            except asyncio.exceptions.TimeoutError:
                logger.error(
                    "Connection timeout while subscribing to LM events. Retrying in 5 seconds")
                await asyncio.sleep(5)

        # Register ourselves with LM to receive data
        res = await lm.call_method(f"{idx}:registerNM", self.uuid)
        # TODO: Check status code

    # Register with GlobalMonitor
    async def __register_to_c2(self):
        """Register as new NM to c&c server"""
        logger.info(f"registering with c2 as uuid: {self.uuid}")

        self.idx = await self.client_c2.get_namespace_index(self.config.opc_domain)
        root = self.client_c2.get_root_node()

        # Create EventListener to listen to configurationChanged Events
        handler = C2EventListener()
        subscription = await self.client_c2.create_subscription(100, handler)
        while True:
            try:
                await subscription.subscribe_events()
                break
            except asyncio.exceptions.TimeoutError:
                logger.error(
                    "Connection timeout while subscribing to C&C events. Retrying in 5 seconds")
                await asyncio.sleep(5)

        # Register ourselves as a NM looking for work
        c2 = await root.get_child(["0:Objects", f"{self.idx}:C2"])
        # TODO: check if res is actually a success status code
        res = await c2.call_method(f"{self.idx}:registerNM", self.uuid, self.config.nm_opc_address)

    async def refresh_config(self):
        """Reloads the config from OPC"""
        config_node = await self.client_c2.get_root_node() \
            .get_child(["0:Objects", f"{self.idx}:{self.uuid}", f"{self.idx}:config"])
        config = await config_node.get_value()
        regions = config.regions
        for br in regions:
            self.__br.append(br)
            lm_1_address = br.lm_1_address
            lm_2_address = br.lm_2_address
            # Register to new local monitors
            await self.__register_to_lm(lm_1_address)
            await self.__register_to_lm(lm_2_address)

    async def _log_to_opc(self):
        # Wait until we have registered with the c2 and before sending log messages
        if not self.isRegistered:
            return
        # Emit all queued log messages as events
        while not self.log_queue.empty():
            try:
                event = self.log_queue.get_nowait()
                self.__log_event_generator.event.uuid = self.config.uuid
                self.__log_event_generator.event.severity = event["severity"]
                self.__log_event_generator.event.message = event["message"]
                self.__log_event_generator.event.type = "NM"
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
        await self.opc_nm_usage_ref.write_value(usage_data)

    async def run(self):
        """Run this nm and do work forever."""
        # Start OPC Server
        await self.__start_opc_server()
        async with self.__server:
            # Initialize
            await self.__init()

            while True:
                await self.__heartbeat_event_generator.trigger()

                # Iterate over all LMs that have reported to have new data
                if len(self.lm_to_check) > 0:
                    for lm in self.lm_to_check:
                        await req_checker.check_requirements(lm)
                        await self._report_violation_via_opc(self.violation_queue)
                    self.lm_to_check = []
                # Publish log messages via OPC
                await self._log_to_opc()
                await self._monitor_usage()
                await asyncio.sleep(1)


async def main(config: NMConfig):
    # Setup Logging for this package
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = OPCNetworkLogger()
    logger.addHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    logger.addHandler(handler)

    # Setup NM itself
    global nm
    nm = NM(config)
    await nm.run()