import base64
import uuid

from Crypto.Cipher import AES

from web import config

def getAes(iv=None, key=None):
    return AES.new(
        key or config.CONFIG['CRYPTO']['KEY'], 
        AES.MODE_CBC, 
        iv or config.CONFIG['CRYPTO']['DEFAULT_IV'],
    )

def getIv():
    return str(uuid.uuid4()).replace("-", '')[0:16]

def encrypt(text, iv=None, key=None):
    text += "|"
    paddingNeeded = 16 - (len(text) % 16)
    padded = text + ("=" * paddingNeeded)
    aes = getAes(iv, key)
    encrypted = aes.encrypt(padded)
    return base64.b64encode(encrypted)

def decrypt(text, iv=None, key=None):
    if text is None:
        return None
    try:
        encrypted = base64.b64decode(text)
        aes = getAes(iv, key)
        decrypted = aes.decrypt(encrypted)
        unpadded = decrypted.rstrip("=")[:-1]
        return unpadded
    except:
        return None