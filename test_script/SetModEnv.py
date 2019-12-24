import os, string

if not os.environ.has_key('MODULE_VERSION'):
        os.environ['MODULE_VERSION_STACK'] = '3.1.6'
        os.environ['MODULE_VERSION'] = '3.1.6'
else:
        os.environ['MODULE_VERSION_STACK'] = os.environ['MODULE_VERSION']

os.environ['MODULESHOME'] = '/usr/share/modules'

if not os.environ.has_key('MODULEPATH'):
        os.environ['MODULEPATH'] = os.popen("""sed 's/#.*$//' ${MODULESHOME}/init/.modulespath | awk 'NF==1{printf("%s:",$1)}'""").readline()

if not os.environ.has_key('LOADEDMODULES'):
        os.environ['LOADEDMODULES'] = '';

def module(command, *arguments):
	commands = os.popen('/usr/bin/modulecmd python %s %s' % (command, string.join(arguments))).read()
        exec commands
