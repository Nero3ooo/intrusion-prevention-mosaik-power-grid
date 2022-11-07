# Mosaik PyPower

This is the Mosaik PyPower adapter from [gitlab](https://gitlab.com/mosaik/mosaik-pypower). <br> This offers mosaik support for the power flow solver PYPOWER, which is not activly maintained anymore. The Mosaik PyPower adapter is used in an older version here, there may be newer versions available. To avoid any incompatibilities, the old version was kept.  

There were some changes done by Chromik to make the PyPower compatible to the RTU simulation, therefore the adapter needs to be installed via this repository: 

    $ pip install -r requirements.txt

and not via 

    $ pip install mosaik-pypower 

If the repository was acidentially installed via pip, it can be removed with 

    $ pip uninstall mosaik-pypower

**Currently there are no additional changes done by me(Verena Menzel).**