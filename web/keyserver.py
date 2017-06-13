import os
import logging
import traceback
import yaml

from web.base import AppSubcomponent

class KeyserverSubcomponent(AppSubcomponent):

    def augmentApp(self, app, appInfo):
        try:
            credentials = get()
            if 'secret_key' in credentials:
                app.secret_key = credentials['secret_key']
        except Exception as e:
            logging.error("-- failed to load credentials --")
            logging.error(traceback.format_exc())

def get():
    return yaml.safe_load(os.environ.get('CREDENTIALS'))