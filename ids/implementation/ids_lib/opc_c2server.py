import asyncio
from datetime import datetime
import json
import uuid
from enum import Enum
import itertools
import logging
import datetime
from termcolor import colored
import websockets

from asyncua import ua, Server, Client
from asyncua.common.methods import uamethod
from asyncua.common.structures104 import new_struct, new_struct_field
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256
from asyncua.server.user_managers import CertificateUserManager

from .util.generate_border_regions import calculateFromJSON
from .config.config_c2 import C2Config


class C2Status(Enum):
    ERROR = 0
    RUNNING = 1
    WAITING_FOR_NM = 2
    WAITING_FOR_LM = 3
    SHOULD_RECONFIGURE = 4


class ColoredLogger(logging.Handler):
    def emit(self, record):
        now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')
        text = f"[C2] [{record.levelname}]: {now} - {record.getMessage()}"
        print(colored(text, "white", attrs=['reverse']))


class LogEventListener:
    """ Listens to log-events from monitors"""

    def __init__(self):
        self.colorMapping = {}
        self.colors = ['red',
                       'green',
                       'yellow',
                       'blue',
                       'magenta',
                       'cyan',
                       'white']

    async def event_notification(self, event):
        text = f"[{event.type} {event.uuid}] [{event.severity}]: {event.Time} - {event.message}"
        color = self.colorMapping.get(event.uuid)
        if color is None:
            color = self.colors[len(self.colorMapping) % len(self.colors)]
            self.colorMapping[event.uuid] = color

        out = colored(text, color, attrs=['reverse'])
        print(out)


class ReqViolationEventListener:
    """ Listens to request-violation-events from monitors"""

    async def event_notification(self, event):
        report = {"type": "report",
                  "timestamp": int(event.Time.timestamp()),
                  "requirement": event.requirement,
                  "component_id": event.component_id
                  }
        c2.reports.append(report)
        c2.reports = c2.reports[-256:]
        pass


class HeartbeatEventListener:
    """
        Listens to all heartbeat events to ensure all registered monitors are running at all times.
         If a monitor hasn't sent a heartbeat during the last 5 seconds, an error will be logged.
    """

    def __init__(self):
        print("Heartbeat init")
        self.nodes = dict()
        self.time_span = datetime.timedelta(hours=0, minutes=0, seconds=10)

    async def event_notification(self, event):
        event_node_id = event.sender

        # if node is nonexistent in dictionary, add it to it with the timestamp
        if not self.nodes.get(event_node_id):
            self.nodes[event_node_id] = event.Time
            logger.info("Node with identifier " + str(event_node_id) + " has sent it's first heartbeat!")

        # if node is existent in dictionary, update the timestamp
        elif self.nodes.get(event_node_id) != event.Time:
            self.nodes[event_node_id] = event.Time
            # if event_node_id == "demo_nm_1": # testing purposes

        # check the timestamps. If a monitor hasn't sent a heartbeat for the past 3 seconds, log an error message
        # and trigger a reconfiguration of border region
        # print("##############################")
        # for node, time in self.nodes.items():
        #    print(node)
        #    print(time)
        #    print("+++++++++++++++++++++++++++")
        # print("##############################")

        for key in list(self.nodes.keys()):
            # print(datetime.datetime.now(tz=datetime.timezone.utc) - self.nodes[key].replace(tzinfo=datetime.timezone.utc))
            if datetime.datetime.now(tz=datetime.timezone.utc) - self.nodes[key].replace(tzinfo=datetime.timezone.utc) \
                    > self.time_span:
                logger.error(f"There was no heartbeat for %s seconds from: %s", str(self.time_span.seconds), str(key))
                await c2.delete_monitor(key)
                del self.nodes[key]


class C2:
    """ Command & Control Server for the distributed IDS network """

    def __init__(self, config: C2Config) -> None:
        """Setup the OPC Server"""

        self.config = config

        # Current status. May be changed by remote procedure calls from monitors or internal processes
        self.status = C2Status.WAITING_FOR_LM

        # Lists of LM and NM for internal management
        self.__local_monitors = []
        self.__neighborhood_monitors = []

        # TODO: Refactor this
        self.reports = []

        self.__log_event_listener = LogEventListener()

        self.__heartbeat_event_listener = HeartbeatEventListener()

    async def _init(self) -> None:
        """Initializes the OPC Server"""

        logger.info(self.config)
        # initialize user-manager for managing lms and nms and their certificates
        cert_user_manager = CertificateUserManager()
        self.__server = Server(user_manager=cert_user_manager)
        server = self.__server

        # security settings
        self.__server.set_security_policy([ua.SecurityPolicyType.Basic256Sha256_SignAndEncrypt])
        await cert_user_manager.add_user(self.config.lm_cert, name="lm")
        await cert_user_manager.add_user(self.config.nm_cert, name="nm")

        await server.init()
        server.set_endpoint(self.config.c2_address)

        idx = await server.register_namespace(self.config.opc_domain)
        self.__idx = idx

        # security settings
        await server.load_certificate(self.config.cert)
        await server.load_private_key(self.config.private_key, self.config.private_key_password)

        # custom structs storing configuration in accessible format
        opc_border_region_node_id, _ = await new_struct(server, idx, "BorderRegion", [
            new_struct_field("uuid", ua.VariantType.Guid),
            new_struct_field("lm_1_id", ua.VariantType.String),
            new_struct_field("lm_2_id", ua.VariantType.String),
            new_struct_field("lm_1_address", ua.VariantType.String),
            new_struct_field("lm_2_address", ua.VariantType.String),
            new_struct_field("region_definition", ua.VariantType.String),
        ])

        await new_struct(server, idx, "NMConfig", [
            new_struct_field("uuid", ua.VariantType.Guid),
            new_struct_field("regions", opc_border_region_node_id, array=True),
        ])
        # Load the just registered definitions
        await server.load_data_type_definitions()

        # Add custom type that has NMConfig as variable
        self.opcNMType = await server.nodes.base_object_type.add_object_type(idx, "NeighborhoodMonitor")

        # We need to initialize NMConfig ourselves, else we run into serializationErrors
        defaultConfig = ua.NMConfig()
        defaultConfig.regions = []
        var = await self.opcNMType.add_variable(idx, "config",
                                                ua.Variant(defaultConfig, ua.VariantType.ExtensionObject))
        await var.set_modelling_rule(True)

        # Add C2 Object and add methods for registering
        c2 = await server.nodes.objects.add_object(idx, "C2")

        await c2.add_method(self.__idx,
                            "registerLM",
                            self.registerLM,
                            [ua.VariantType.Guid, ua.VariantType.String, ua.VariantType.String],
                            [ua.VariantType.StatusCode])
        await c2.add_method(self.__idx,
                            "registerNM",
                            self.registerNM,
                            [ua.VariantType.Guid, ua.VariantType.String],
                            [ua.VariantType.StatusCode])

    @uamethod
    async def registerLM(self, parent, id: str, address: str, config: str) -> ua.StatusCode:
        """Registers an LM with this C2. Triggers reconfiguration of the network as border_regions will have changed."""

        logger.info(f"LM with id: '{id}' has registered")
        self.__local_monitors.append({
            "id": id,
            "address": address,
            "rtu_config": config,
            "client": None,
            "log_subscription": None,
            "violation_subscription": None
        })

        # schedule recalculation as new LM is available
        self.status = C2Status.SHOULD_RECONFIGURE

        return ua.StatusCodes.Good

    @uamethod
    async def registerNM(self, parent, id: str, addr: str) -> ua.StatusCode:
        """Registers an NM with this C2. Adds the NM to the pool of available NMs and can trigger reconfiguration"""

        logger.info(f"NM with id: '{id}' has registered")
        # Create OPC Object
        opc_ref = await self.__server.nodes.objects.add_object(self.__idx, id, self.opcNMType)

        # Create internal Object
        self.__neighborhood_monitors.append({
            "id": id,
            "border_regions": [],
            "address": addr,
            "opc_ref": opc_ref,
            "client": None,
            "log_subscription": None,
            "violation_subscription": None
        })

        # A new NM is available so leave waiting status
        if self.status == C2Status.WAITING_FOR_NM:
            self.status = C2Status.SHOULD_RECONFIGURE

        return ua.StatusCodes.Good

    async def connect_event_handlers(self, monitors, cert):

        for monitor in monitors:
            # Skip if we are already connected
            if monitor['client'] is not None:
                continue

            # Create listening client
            client = Client(url=monitor['address'])
            await client.set_security(
                SecurityPolicyBasic256Sha256,
                certificate=self.config.cert,
                private_key=self.config.private_key,
                private_key_password=self.config.private_key_password,
                server_certificate=cert
            )

            try:
                await client.connect()
                logger.info(f"c2 connected to monitor {monitor['id']}")
            except BaseException as e:
                logger.error(f"Connection error while connecting to monitor '{monitor['id']}' "
                             f"on '{monitor['address']}'. Retrying soon.")
                continue

            await client.load_data_type_definitions()
            monitor['client'] = client

            # Get event definition
            root = client.get_root_node()
            violation_event_type = \
                await root.get_child(["0:Types", "0:EventTypes", "0:BaseEventType", "2:ReqViolationEvent"])
            log_event_type = \
                await root.get_child(["0:Types", "0:EventTypes", "0:BaseEventType", "2:LogEvent"])
            heartbeat_event_type = \
                await root.get_child(["0:Types", "0:EventTypes", "0:BaseEventType", "2:Heartbeat"])

            # Register event handlers
            log_handler = self.__log_event_listener
            log_subscription = await client.create_subscription(1000, log_handler)
            while True:
                try:
                    await log_subscription.subscribe_events(evtypes=log_event_type)
                    break
                except asyncio.exceptions.TimeoutError:
                    # TODO: refine error message
                    logger.error(
                        "Connection timeout while subscribing to events. Retrying in 5 seconds")
                    await asyncio.sleep(5)
            monitor['log_subscription'] = log_subscription

            violation_handler = ReqViolationEventListener()
            violation_subscription = await client.create_subscription(1000, violation_handler)
            while True:
                try:
                    await violation_subscription.subscribe_events(evtypes=violation_event_type)
                    break
                except asyncio.exceptions.TimeoutError:
                    # TODO: refine error message
                    logger.error(
                        "Connection timeout while subscribing to events. Retrying in 5 seconds")
                    await asyncio.sleep(5)
            monitor['violation_subscription'] = violation_subscription

            heartbeat_handler = self.__heartbeat_event_listener
            heartbeat_subscription = await client.create_subscription(1000, heartbeat_handler)
            while True:
                try:
                    await heartbeat_subscription.subscribe_events(evtypes=heartbeat_event_type)
                    break
                except asyncio.exceptions.TimeoutError:
                    # TODO: refine error message
                    logger.error(
                        "Connection timeout while subscribing to heartbeatevents. Retrying in 5 seconds")
                    await asyncio.sleep(5)

            # Notify Monitor that they are registered and we are listening to events
            await (await self.__server.get_event_generator()).trigger(message="isRegistered")

    def check_current_configuration(self) -> bool:
        """Does a sanity check if recalculation of configuration configuration is possible"""

        # Check that we have more than 1 LM
        if len(self.__local_monitors) < 2:
            logger.error(f"skipping calculate_border_region as we do not have enough LMs registered. "
                         f"Needed: >2 but currently only have {len(self.__local_monitors)}")
            self.status = C2Status.WAITING_FOR_LM
            return False

        # Check that we have enough registered neighborhood monitors to assign an NM to each LM
        if len(self.__neighborhood_monitors) < len(self.__local_monitors):
            logger.error(f"skipping calculate_border_region as we do not have enough NMs registered. "
                         f"Needed: {len(self.__local_monitors)} but currently have {len(self.__neighborhood_monitors)}")

            # We need to wait for NM to register
            self.status = C2Status.WAITING_FOR_NM
            return False

        return True

    async def configure_network(self) -> None:
        """Configures the IDS communication network"""

        # Checks if configuring is even possible
        if not self.check_current_configuration():
            return

        # Convenience
        local_monitors = self.__local_monitors
        neighborhood_monitors = self.__neighborhood_monitors

        # Reset all neighborhood monitor configs
        for nm in neighborhood_monitors:
            nm['border_regions'] = []

        # Assign each NM to an LM
        # TODO: Add affinity to NM so NM_xyz is always connected to LM_xyz.
        #  This may be desirable, e.g. if they are physically close to each other
        #  To do this the LM/NM probably needs to tell us which LM/NM id should be used
        #  For now we just assign based on their order of registration
        nm_index = 0
        for lm in local_monitors:
            lm['assigned_nm'] = neighborhood_monitors[nm_index]
            nm_index += 1

        # For each pair of local monitors calculate the border region
        for pair in itertools.combinations(local_monitors, 2):
            lm_1 = pair[0]
            lm_2 = pair[1]
            # logger.debug(f"Calculating border region for: {lm_1['id']} <-> {lm_2['id']}")

            border_region = calculate_border_regions({'id': lm_1['id'], 'config': lm_1['rtu_config']},
                                                     {'id': lm_2['id'], 'config': lm_2['rtu_config']})

            # Generate config
            opc_border_region = ua.BorderRegion()
            opc_border_region.uuid = uuid.uuid4()
            opc_border_region.lm_1_id = lm_1['id']
            opc_border_region.lm_2_id = lm_2['id']
            opc_border_region.lm_1_address = lm_1['address']
            opc_border_region.lm_2_address = lm_2['address']
            opc_border_region.region_definition = json.dumps(border_region)

            # Assign border_region to both participating NMs
            lm_1['assigned_nm']['border_regions'].append(opc_border_region)
            lm_2['assigned_nm']['border_regions'].append(opc_border_region)

        # Assign config to each monitor via OPC:
        for nm in neighborhood_monitors:
            # Get config object node_id
            opc_nm_config = await nm['opc_ref'].get_child([f"{self.__idx}:config"])

            # create new config (thereby overriding the old one)
            config = ua.NMConfig()
            config.uuid = uuid.uuid4()
            config.regions = nm['border_regions']
            await opc_nm_config.write_value(config)

        # Notify NMs about config change so they can reload
        await (await self.__server.get_event_generator()).trigger(message="reconfigure")

        # leave status C2Status.SHOULD_RECONFIGURE
        self.status = C2Status.RUNNING

    # Intermediate between reported requirement violations and "webvis" website
    async def websocket_handle(self, ws, path):
        async for message in ws:
            message_json = json.loads(message)

            # Differentiate message types for future extensibility of communication between Visualization <-> C2
            if message_json["type"] == "query":
                last_timestamp = message_json["timestamp"]

                # Gather all reports that happened later than the last timestamp
                new_reports = []
                for i in range(len(self.reports)):
                    if int(self.reports[i]['timestamp']) > last_timestamp:
                        new_reports.append(self.reports[i])

                # If new reports exist, reply
                if len(new_reports) > 0:
                    # Package reports in json array
                    await ws.send(json.dumps(new_reports))

    async def delete_monitor(self, monitorId):
        for monitor in self.__neighborhood_monitors:
            if monitorId == monitor['id']:
                self.__neighborhood_monitors.remove(monitor)
                logger.error("An NM has been removed, because it hasn't answered. Need to reconfigure.")
                # TODO: Call unregister_nm for all LMs (the check for necessity of this action is included)
                for lm in self.__local_monitors:
                    if lm['client']:
                        await(await lm['client']
                              .get_root_node()
                              .get_child(["0:Objects", f"{self.__idx}:LM"])).call_method(f"{self.__idx}:unregisterNM",
                                                                                         monitorId)
                self.status = C2Status.SHOULD_RECONFIGURE

        for monitor in self.__local_monitors:
            if monitorId == monitor['id']:
                self.__local_monitors.remove(monitor)
                logger.error("An LM has been removed, because it hasn't answered. Need to reconfigure.")
                self.status = C2Status.SHOULD_RECONFIGURE

        await self.configure_network()

    async def run(self):
        """ Serve forever """
        await c2._init()

        async with self.__server:
            async with websockets.serve(self.websocket_handle, "0.0.0.0", 8777):
                logger.info("[WEBSOCKET] Started websocket at localhost:8777")
                while True:
                    # TODO only trigger this if new monitors have registered.
                    await self.connect_event_handlers(self.__neighborhood_monitors, self.config.nm_cert)
                    await self.connect_event_handlers(self.__local_monitors, self.config.lm_cert)
                    await asyncio.sleep(2)
                    # Check every tick if we need to recalculate
                    if self.status == C2Status.SHOULD_RECONFIGURE:
                        await self.configure_network()


def calculate_border_regions(conf1, conf2):
    ret = calculateFromJSON([conf1, conf2])
    if ret:
        logger.debug("border region calculation was successful!")
        return ret
    else:
        logger.error("border region calculation failed!")
        return "ERROR BR"


async def main(config: C2Config):
    # Setup Logging for this package
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    handler = ColoredLogger()
    logger.addHandler(handler)
    logger.propagate = False

    global c2
    c2 = C2(config)
    await c2.run()
