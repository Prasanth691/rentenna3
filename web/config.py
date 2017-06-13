import os
import os.path
import yaml

CONFIG = {}

def augmentOs():
    import os
    import sys
    if hasattr(sys, 'OS_OVERRIDES'):
        os.environ.update(sys.OS_OVERRIDES)
    if 'OS_OVERRIDES' in CONFIG:
        os.environ.update(CONFIG['OS_OVERRIDES'])

augmentOs()

if os.environ.get('WEB_ROOT'):
    WEB_ROOT = os.environ.get('WEB_ROOT')
else:
    WEB_ROOT = '.'

siteConfigPath = "%s/site-config.yaml" % WEB_ROOT
envConfigPath = "%s/%s" % (WEB_ROOT, os.environ['CONFIG'])

if os.path.isfile(siteConfigPath):
    with open(siteConfigPath) as f:
        siteConfig = yaml.safe_load(f)
else:
    siteConfig = {}

if os.path.isfile(envConfigPath):
    with open(envConfigPath) as f:
        deployConfig = yaml.safe_load(f)
else:
    deployConfig = {}

CONFIG.update(siteConfig)

for key, value in deployConfig.items():
    if isinstance(value, dict):
        subConfig = CONFIG.setdefault(key, {})
        for subkey, subvalue in value.items():
            subConfig[subkey] = subvalue
    else:
        CONFIG[key] = value

CONFIG['WEB_ROOT'] = WEB_ROOT

augmentOs()