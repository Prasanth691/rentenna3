import base64
import getpass
import os
import subprocess
import uuid
import sys

version = sys.argv[1]

credentials = subprocess.check_output([
    'openssl', 
    'aes-256-cbc',
    '-d', 
    '-in', 
    'credentials.%s' % version,
])

tmpFile = '/tmp/%s' % (str(uuid.uuid4()))

with open(tmpFile, 'w') as f:
    f.write(credentials)

subprocess.check_call(['vim', tmpFile])

credentials = subprocess.check_output([
    'openssl', 
    'aes-256-cbc',
    '-in', 
    tmpFile,
    '-out',
    'credentials.%s' % version,
])

subprocess.check_call(['rm', tmpFile])