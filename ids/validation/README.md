# Validation for IDS

Validates incomming commands of the RTU.
## Installation

Starts with [ids/deployment/docker-compose](deployment/docker-compose.yml).

## Directory Structure

    config:
      - config_val.py (Config file for server configurations, not used yet)
    data:
      - relevant data for the simulation (houses, grid-structure and pv have to be changed manually when changing on testbed, xm-files will be changed by validating)
    ids-lib:
      - current validation server 
      - location to add more validation 
    
    validation-setup.py configurates server, entrypoint for docker
    
## Notes:
Some folders will be provided from testbed by docker (See volumes in [ids/deployment/docker-compose](deployment/docker-compose.yml))
