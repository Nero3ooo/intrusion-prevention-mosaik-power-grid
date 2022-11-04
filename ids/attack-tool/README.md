Here is the Trello Board, which we use to organize our Project: 
https://trello.com/invite/b/Gs1b9ffs/ae7f35ff2999f32f09a8c636a65af880/main

Base running project, which is our base that we want to attack:
https://zivgitlab.uni-muenster.de/ag-lammers/itsis-blackout/seccomm/-/tree/2ba790f66f4fee819e27ff706d5e6a4c27c49c02

## Dependencies
For the GUI you need to install *tkinter 8.6*.
(https://docs.python.org/3/library/tkinter.html)

## Basic Usage

To start the GUI, execute *python gui.py*.

To start the attack engine as commandline-tool, execute *python3 rtu_attack_engine.py*.
(We recommend using the GUI, some features are not in the commandline-tool)

## The Code

The main functionallity is in the *rtu_attack_engine.py*. There you find the whole functionallity to manipulate one value via modbus client.

The code of the GUI is in the *App.py*. In the GUI you can create **Scenarios** to manipulate multiple values at the same time. The code which connects the GUI and the attack engine is in the *attack_scenario.py*.

For more Information you can read the **final document** of the seminar.
