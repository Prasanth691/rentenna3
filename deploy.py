import base64
import getpass
import os
import subprocess
import sys
import uuid
import yaml

version = sys.argv[1]

with open('config.yaml.%s' % version) as f:
    config = yaml.safe_load(f.read())

config['tag']['hash'] = str(uuid.uuid4())

with open('config.yaml.%s' % version, 'w') as f:
    print >> f, yaml.safe_dump(config, default_flow_style=False)

credentials = subprocess.check_output([
    'openssl',
    'aes-256-cbc',
    '-d',
    '-in',
    'credentials.%s' % version,
])

env = os.environ.copy()
env['CREDENTIALS'] = credentials
env['CONFIG'] = 'config.yaml.%s' % version
env['ENVIRONMENT'] = version

subprocess.check_call(['grunt', 'web:compile'], env=env)

subprocess.call([
    'appcfg.py',
    'update',
    '-V',
    version,
    '-E',
    'CREDENTIALS:%s' % credentials,
    '-E',
    'CONFIG:config.yaml.%s' % version,
    '-M',
    'default',
    './app.yaml'
])

subprocess.call([
    'appcfg.py',
    'update',
    '-V',
    version,
    '-E',
    'CREDENTIALS:%s' % credentials,
    '-E',
    'CONFIG:config.yaml.%s' % version,
    '-M',
    'reporting',
    './reporting.yaml'
])
