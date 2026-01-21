# OpenStreamControl

**A simple Python Programm to Control the Aquastream XT Pump from Aquacomputer (Linux + Windows)**


### LINUX:

I compiled the python source into an executable file with all the needed libraries included.

download package, unpack it and
just execute "./openstreamcontrol" in the programs directory

#########################

If you get the message the pump isnt found make sure your user account has access to the /dev/hidraw devices (udev rules)

How to do this depends on your distribution. 
Google is your friend.

########################

If you want to run the python script directly:

you need:

"python3"

and following python modules:

"Python hidapi bindings in ctypes (aka pyhidapi)"
"pyside6" and
"pyqtgraph"
"colorama"

start with "python3 ./openstreamcontrol.py"


#####################

### WINDOWS:

you need python v3

download https://github.com/libusb/hidapi and copy "hidapi.dll" to (windir)/system32 folder

use "pip" from python to load  modules "hid", "pyside6" and "pyqtgraph"

start it with "python3 ./openstreamcontrol.py" in the programs directory
