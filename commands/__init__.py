from .exportbomcsv import entry as exportbomcsv
from .exportgraphviz import entry as exportgraphviz
from .exportmermaid import entry as exportmermaid

# Fusion will automatically call the start() and stop() functions.
commands = [
    exportbomcsv,
    exportgraphviz,
    exportmermaid,
]


# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start():
    for command in commands:
        command.start()


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()
