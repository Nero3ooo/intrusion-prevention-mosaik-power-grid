import asyncio
import os
import uuid

from ids_lib import opc_validation
from config.config_val import ValConfig


def run_val():
    # Setup config based on environment
    config = ValConfig()
    config.uuid = "val00" + str(uuid.uuid4())[4:]
    config.opc_domain = os.getenv('IDS_OPC_DOMAIN')
    config.lm_opc_address = os.getenv('IDS_LM_OPC_ADDRESS')
    config.cert = os.getenv('IDS_CERT')
    config.private_key = os.getenv('IDS_PRIVATE_KEY')
    config.private_key_password = os.getenv('IDS_PRIVATE_KEY_PASSWORD')

    # Run validation forever
    asyncio.run(opc_validation.main())


if __name__ == '__main__':
    run_val()
