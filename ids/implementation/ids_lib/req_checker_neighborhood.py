import asyncio
import json


def get_meter_data(data1, data2, m):
    """Checks if the meter m is contained in either one of the MeterData lists and returns the corresponding MeterData
    object. """
    for d in data1.meters:
        if d.id == m["id"]:
            return d

    for d in data2.meters:
        if d.id == m["id"]:
            return d

    return None


def get_switch_data(data1, data2, s):
    """Checks if the switch is contained in either one of the SwitchData lists and returns the corresponding SwitchData
        object. """
    for d in data1.switches:
        if d.id == s["id"]:
            return d

    for d in data2.switches:
        if d.id == s["id"]:
            return d

    return None


class ReqCheckerNeighborhood:

    def __init__(self, border_regions, client_lms, vio_queue, logger):
        # TODO: get border regions and client_lms as input parameters
        self.__br = border_regions
        self.__client_lms = client_lms
        self.__vio_queue = vio_queue
        self.__logger = logger

    async def check_requirements(self, lm_address):
        """Check all requirements of the neighborhood scope"""
        try:
            await asyncio.gather(
                self._check_req_3(lm_address),
                self._check_req_4(lm_address)
            )
        except Exception as e:
            self.__logger.error(e)

    async def _check_req_3(self, lm_address):
        """Checks requirement 3: There is no current on a power line with an open switch."""
        # Get border regions of the lm that sent the data
        br_to_be_checked = []
        for br in self.__br:
            if br.lm_1_address == lm_address or br.lm_2_address == lm_address:
                br_to_be_checked.append(br)

        for br in br_to_be_checked:
            # Get data values from all lm in this border region
            data_lm1 = await self.get_data_from_lm(br.lm_1_address)
            data_lm2 = await self.get_data_from_lm(br.lm_2_address)

            # Could not retrieve data from LM
            if data_lm1 is None or data_lm2 is None:
                return

            # Extract border region json
            tmp = json.loads(br.region_definition)
            region_id = list(tmp)[0]
            br_json = tmp[region_id]

            # Get all lines from border region with open switch
            open_switch_lines = []
            for s in br_json["switches"]:
                d = get_switch_data(data_lm1, data_lm2, s)
                if d is None:
                    self.__logger.error("Could not find switch data.")
                # Note: switch is open <=> switch.value = False
                if not d.value:
                    # Note: power lines from s are always in the border region
                    power_line_id = s["power_line_id"]
                    open_switch_lines.append(power_line_id)

            # Check values of all meters on border region power line with open switch
            for m in br_json["meters"]:
                if m["power_line_id"] in open_switch_lines:
                    d = get_meter_data(data_lm1, data_lm2, m)
                    if d is None:
                        self.__logger.error("Could not find meter data.")
                    # If current != 0
                    if d.current:
                        # Add violation to queue
                        self.__vio_queue.put_nowait({
                            "req_id": 3,
                            "component_id": m["power_line_id"]}
                        )

                        # self.__logger.error("Requirement 3 (neighborhood) violated! There is current on line %s with "
                        #              "an open switch", m["power_line_id"])

    async def _check_req_4(self, lm_address):
        """Checks requirement 4: Measured voltage and current remain the same over the length of a power line."""
        # Get border regions of the lm that sent the data
        br_to_be_checked = []
        for br in self.__br:
            if br.lm_1_address == lm_address or br.lm_2_address == lm_address:
                br_to_be_checked.append(br)

        for br in br_to_be_checked:
            data_lm1 = await self.get_data_from_lm(br.lm_1_address)
            data_lm2 = await self.get_data_from_lm(br.lm_2_address)

            # Could not retrieve data from LM
            if data_lm1 is None or data_lm2 is None:
                return

            # Extract border region json
            tmp = json.loads(br.region_definition)
            region_id = list(tmp)[0]
            br_json = tmp[region_id]
            # Get all power lines in border region
            for power_line in br_json['power_lines']:
                # Get all meter ids on this power line
                pl_meters = []
                for m in br_json["meters"]:
                    if m["power_line_id"] == power_line["id"]:
                        d = get_meter_data(data_lm1, data_lm2, m)
                        if d is None:
                            self.__logger.error("Could not find meter data.")
                        pl_meters.append(d)

                # Compare the values with one another
                ref_current = round(pl_meters[0].current, 2)
                ref_voltage = round(pl_meters[0].voltage, 2)
                for d in pl_meters:
                    # Check if all values are within toleration range
                    if not (ref_current - 0.05 <= round(d.current, 2) <= ref_current + 0.05):
                        # Add violation to queue
                        self.__vio_queue.put_nowait({
                            "req_id": 4,
                            "component_id": power_line["id"]}
                        )

                        # self.__logger.error("Requirement 4 (neighborhood) violated! Current on line %s measured by %s "
                        #                     ": %s (!= %s)",
                        #                     power_line["id"], d.id, round(d.current, 2), ref_current)
                    if not (ref_voltage - 0.05 <= round(d.voltage, 2) <= ref_voltage + 0.05):
                        # Add violation to queue
                        self.__vio_queue.put_nowait({
                            "req_id": 4,
                            "component_id": power_line["id"]}
                        )

                        # self.__logger.error("Requirement 4 (neighborhood) violated! Voltage on line %s measured by %s "
                        #                     ": %s (!= %s)",
                        #                     power_line["id"], d.id, round(d.voltage, 2), ref_voltage)

    async def get_data_from_lm(self, lm_address):
        """Get the latest data values from the specified local monitor."""
        data_node = None
        for lm in self.__client_lms:
            if lm["url"] == lm_address:
                data_node = lm["data_node"]
        try:
            lm_data = await data_node.read_value()
        except Exception:
            lm_data = None
        return lm_data
