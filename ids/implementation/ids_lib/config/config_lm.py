import uuid


class LMConfig:
    """Config class for LM"""

    uuid = None  # Unique ID of this LM
    c2_address = None  # OPC Server Url of c&c server
    opc_domain = None  # Domain used inside OPC to uniquely identify the ids

    lm_opc_address = None  # Adress of the local OPC Server of this Config

    c2_cert = None  # Certificate of the c2 Server
    nm_cert = None  # Certificate of the NM certificates

    cert = None  # Own Certificate
    private_key = None  # Encrypted Private Key
    private_key_password = None  # Private Key Password

    rtu_config = None  # RTU json config as string

    rtu_modbus_host = None  # Modbus hostname of the RTU to monitor
    rtu_modbus_port = None  # Modbus port of the RTU to monitor

    def __init__(self):
        pass

    def default_config(self, rtu_conf_file, rtu_modbus_port, lm_opc_port):
        self.lm_opc_address = f"opc.tcp://localhost:{lm_opc_port}/freeopcua/server/"  # local OPC server url
        self.uuid = str(uuid.uuid4())

        self.opc_domain = "http://itsis-blackout.ids/"

        self.c2_cert = "../config/certificates/cert_c2.der"
        self.nm_cert = "../config/certificates/cert_nm.der"
        self.cert = "../config/certificates/cert_lm.der"
        self.private_key = "../config/certificates/key_lm.pem"
        self.private_key_password = "password"

        self.c2_address = "opc.tcp://127.0.0.1:4840/freeopcua/server/"

        self.rtu_modbus_host = "localhost"
        self.rtu_modbus_port = rtu_modbus_port

        # TODO: Maybe validate the config here?
        with open(rtu_conf_file, 'r') as file:
            self.rtu_config = file.read()

        return self
