# Mosaik RTU

This is a RTU Simulator for the Mosaik framework. It simulates an RTU/Local substation/subgrid and presents a Modbus TCP Server which writes the currently measured values in its registers.

Most work was done by Chromik, I (Verena Menzel) edited only small adaptions/output file generation.
Addiotonaly ToDos within the source code were kept from Chromik, my annotation start with a "# V:". 
<br>
For the scope of this thesis, the most crucial part is the update of scensory readings to the Modbus Server. This is currently done in the step() function (which is a simulation step) in the ``rtu.py`` file. 