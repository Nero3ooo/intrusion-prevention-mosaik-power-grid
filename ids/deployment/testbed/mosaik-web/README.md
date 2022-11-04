# Mosaik-web

A simple mosaik simulation visualization for web browsers.
Used in version 0.2.2 as from [gitlab](https://gitlab.com/mosaik/mosaik-web), developed by Stefan Scherfke and Gunnar Jeddeloh.

I (Verena Menzel) only adapted the visualization a little bit in this repository. To use "my" version of the visualization the repository **cannot** be installed via 

    $ pip install mosaik-web

since this would use the original repository but must be installed (with terminal directory in this folder) via: 

    $ python setup.py install

If you already installed mosaik-web automatically via the first command you can remove it again via: 
    
    $ pip uninstall mosaik-web 

The main testbed simulation scenario launches the web visualization currently at http://localhost:8000 . The port is set in the scenario, in this case the ``test_scenario.py``, LOC 40.