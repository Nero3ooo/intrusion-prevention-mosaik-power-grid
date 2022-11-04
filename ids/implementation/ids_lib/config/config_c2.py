import uuid


class C2Config:
    """Config class for c&c server"""

    uuid = None  # Unique ID
    c2_address = None  # OPC Server Url of c&c server
    opc_domain = None  # Domain used inside OPC

    nm_cert = None  # Certificate used by NMs
    lm_cert = None  # Certificate used by LMs
    cert = None  # Certificate used by this c2
    private_key = None  # Private key for certificate
    private_key_password = None  # Private key password

    def __str__(self):
        return f'''
            Running c&c server with config:
            
                uuid: {self.uuid}
                c2_address: {self.c2_address}
                opc_domain: {self.opc_domain}
                nm_cert: {self.nm_cert}
                lm_cert: {self.lm_cert}
                cert: {self.cert}
                private_key: {self.private_key}
                private_key_password: ****
        '''

    def default_config(self):
        self.uuid = uuid.uuid4()

        self.c2_address = "opc.tcp://127.0.0.1:4840/freeopcua/server/"
        self.opc_domain = "http://itsis-blackout.ids/"

        self.nm_cert = "../config/certificates/cert_nm.der"
        self.lm_cert = "../config/certificates/cert_lm.der"

        self.cert = "../config/certificates/cert_c2.der"
        self.private_key = "../config/certificates/key_c2.pem"
        self.private_key_password = "password"
        return self
