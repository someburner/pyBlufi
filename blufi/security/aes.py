from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.algorithms.AES
class BlufiAES(object):
    """ AES/CFB/NoPadding """
    def __init__(self, key, iv):
        self.key = key
        self.iv = iv
        self.cipher = Cipher(algorithms.AES128(self.key), modes.CFB(self.iv))
        self.encryptor = self.cipher.encryptor()
        self.decryptor = self.cipher.decryptor()

    def encrypt(self, data):
        ct = self.encryptor.update(data) + self.encryptor.finalize()
        return ct

    def decrypt(self, data):
        pt = self.decryptor.update(data) + self.decryptor.finalize()
        return pt
