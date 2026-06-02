import os, sys
path = '/home/inmove/inmove'
if path not in sys.path:
    sys.path.append(path)
os.chdir(path)
from inmove import app as application
