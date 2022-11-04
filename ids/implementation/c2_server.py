import asyncio
import uuid
import os

from ids_lib import opc_c2server
from ids_lib.config.config_c2 import C2Config

def run_c2():
    # Setup config based on command line parameters
    try:
        config = C2Config()
        config.uuid = "c200" + str(uuid.uuid4())[4:]
        config.c2_address = os.getenv('IDS_C2_ADDRESS')
        config.opc_domain = os.getenv('IDS_OPC_DOMAIN')
        config.nm_cert = os.getenv('IDS_NM_CERT')  # TODO: refactor this to accept individual certificates
        config.lm_cert = os.getenv('IDS_LM_CERT')  # TODO: refactor this to accept individual certificates
        config.cert = os.getenv('IDS_CERT')
        config.private_key = os.getenv('IDS_PRIVATE_KEY')
        config.private_key_password = os.getenv('IDS_PRIVATE_KEY_PASSWORD')

        # Run c2 forever
        asyncio.run(opc_c2server.main(config))
    except KeyError as ke:
        print(ke)
        exit(78)


if __name__ == '__main__':
    run_c2()
