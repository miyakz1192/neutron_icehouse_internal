import socket
import time

host = '127.0.0.1'
port = 1192
#bufsize = 4096
bufsize = 5

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((host, port))
sfile = sock.makefile()

"""
<socket._fileobject object at 0x7f0f2523e1d0>
(Pdb) fg
*** NameError: name 'fg' is not defined
(Pdb) import inspect
(Pdb) inspect.getsourcefile(sflile)
*** NameError: name 'sflile' is not defined
(Pdb) inspect.getsourcefile(sfile)
*** TypeError: <socket.AF_APPLETALK_fileobject object at 0x7f0f2523e1d0> is not a module, class, method, function, traceback, frame, or code object
(Pdb) inspect.getfile(sfile)
*** TypeError: <socket.AF_APPLETALK_fileobject object at 0x7f0f2523e1d0> is not a module, class, method, function, traceback, frame, or code object
(Pdb) 

"""

for c in range(1, 10):
  print c
#  import pdb
#  pdb.set_trace()
  data = sfile.read(bufsize)
  print "size=", len(data)
  time.sleep(1)
  print data

sfile.close()

