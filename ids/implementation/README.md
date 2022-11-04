# Implementation

uses opc and stuff

## Directory Overview

- **util**: assortment of functions to read the config files that setup the powergrid\
- **virtual_grid**: power grids (borde region, subgrid)
  - **virtual_components**: virtual powergrid components for monitoring
    - component.py — all virtual components inherit from this class
    - bus.py — virtual bus
    - meter.py — virtual meter
    - power_line.py — virtual power line
    - switch.py — virtual switch
  - _virtual_grid_region.py_ — base class for all virtual representation of an electrical grid region within the monitoring system. 
  - _border_region.py_ — virtual neighbourhood in the monitoring system,   inherits from _virtual_grid_region.py_
  - subgrid.py — virtual (local) subgrid region in the monitoring system, inherits from _virtual_grid_region.py_
- _opc_c2server.py_ — Command & Control Server for the distributed IDS network
- _opc_local_monitor.py_ — OPC-networked Local Monitor
- _opc_neighborhood_monitor.py_ — OPC-networked Neighborhood Monitor