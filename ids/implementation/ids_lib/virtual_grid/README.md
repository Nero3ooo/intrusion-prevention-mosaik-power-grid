# Virtual Grid

This directory contains the virtual representation of the electrical grid which is supervised by the monitoring system. <br>
Each region evaluates the requirements from its matching scope on the available components. 

``virtual_grid_region.py``: 
Base class of a region within the grid. 

``subgrid.py``:
Represents the subgrid (i.e. the local scope) within the virtual grid. Can contain power lines, buses, meters and switches. 

``border_region.py``;
Represents the border region between two subgrids (i.e. the neighbourhood scope) within the virtual grid.  Can contain power lines, meters and switches. 

*virtual_components directory*
Contains the python files for the virtual components used within the virtual grid. 