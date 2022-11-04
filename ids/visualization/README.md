# Visualization for IDS
Visualizes current `virtual_grid` used by IDS system. 

### Installation
Start the Server on port 8000 with `python3 server.py`

## Directory Structure

- **data**: custom json config files for the powergrid components, used by webvis to generate the map
    - _rtu_0.json_ — components connected to RTU 0
    - _rtu_1.json_ — components connected to RTU 1
- **www**: content served by the webserver (_webserver.py_)
  - **assets**: contains itsis logo
  - **css**: stylesheets for the website
  - **js**: javascripts
    - _com.js_ — connects to C2 and gets newest violations, highlights them on the graph
    - _visualize.js_ — generates the powergrid visualization graph
  - _index.html_ — index page of the visualization
  - _graph.json_ — output of the processed config files, used by _visualize.js_ to generate the graph
- _webserver.py_ — Webserver including functions for processing **data** files and dumping them into _www/graph.json_


### Notes:
- Currently requires custom formatted `rtu_<id>.json` files
    - added power_line->segments key

## Future Work
- Maybe boxes to show Subgrids? Not sure if this is really needed
    - https://ialab.it.monash.edu/webcola/examples/sucrosebreakdown.html
