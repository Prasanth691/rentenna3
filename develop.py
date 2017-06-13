import base64
import getpass
import os
import subprocess
import sys

credentials = subprocess.check_output([
    'openssl',
    'aes-256-cbc',
    '-d',
    '-in',
    'credentials.development'
])

env = os.environ.copy()
env['CREDENTIALS'] = credentials
env['CONFIG'] = 'config.yaml.development'
env['ENVIRONMENT'] = 'development'

subprocess.check_call(['grunt', 'web:develop'], env=env)
