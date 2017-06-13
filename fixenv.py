import json

startupArgs = config.python_config.startup_args
try:
    environment = json.loads(startupArgs)
except:
    print "No environment available..."
    exit()

import sys

sys.OS_OVERRIDES = environment