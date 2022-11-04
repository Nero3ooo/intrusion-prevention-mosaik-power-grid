import uuid


class NMConfig:
    """Config class for NM"""

    uuid = None  # Unique ID of this LM
    c2_address = None  # OPC Server Url of c&c server
    opc_domain = None  # Domain used inside OPC to uniquely identify the ids

    nm_opc_address = None  # Address of the local OPC Server of this Config

    c2_cert = None  # Certificate of the c2 Server
    lm_cert = None  # Certificate of the LM

    cert = None  # Own Certificate
    private_key = None  # Encrypted Private Key
    private_key_password = None  # Private Key Password

    def __init__(self):
        pass

    def default_config(self):
        self.nm_opc_address = f"opc.tcp://localhost:10808/freeopcua/server/"  # local OPC server url
        self.uuid = uuid.uuid4()

        self.c2_address = "opc.tcp://127.0.0.1:4840/freeopcua/server/"
        self.opc_domain = "http://itsis-blackout.ids/"

        self.c2_cert = "../config/certificates/cert_c2.der"
        self.lm_cert = "../config/certificates/cert_lm.der"
        self.cert = "../config/certificates/cert_nm.der"
        self.private_key = "../config/certificates/key_nm.pem"
        self.private_key_password = "password"
        return self
