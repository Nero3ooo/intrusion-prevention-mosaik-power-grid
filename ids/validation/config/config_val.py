import uuid


class ValConfig:
    """Config class for Val"""

    uuid = None  # Unique ID of this Val
    rtu_address = None  # OPC Server Url of rtu server
    opc_domain = None  # Domain used inside OPC to uniquely identify the ids

    val_opc_address = None  # Adress of the local OPC Server of this Config

    rtu_cert = None  # Certificate of the RTU

    cert = None  # Own Certificate
    private_key = None  # Encrypted Private Key
    private_key_password = None  # Private Key Password

    def __init__(self):
        pass

    def default_config(self, val_opc_port):
        self.val_opc_address = f"opc.tcp://localhost:{val_opc_port}/freeopcua/server/"  # local OPC server url
        self.uuid = str(uuid.uuid4())

        self.opc_domain = "http://itsis-blackout.ids/"

        self.rtu_cert = "../config/certificates/cert_rtu.der"
        self.cert = "../config/certificates/cert_val.der"
        self.private_key = "../config/certificates/key_val.pem"
        self.private_key_password = "password"

        self.rtu_address = "opc.tcp://127.0.0.1:4840/freeopcua/server/"

        return self
