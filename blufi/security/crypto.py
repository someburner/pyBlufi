
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import dh

DH_P = "0xcf5cf5c38419a724957ff5dd323b9c45c3cdd261eb740f69aa94b8bb1a5c9640" + \
    "9153bd76b24222d03274e4725a5406092e9e82e9135c643cae98132b0d95f7d6" + \
    "5347c68afc1e677da90e51bbab5f5cf429c291b4ba39c6b2dc5e8c7231e46aa7" + \
    "728e87664532cdf547be20c9a3fa8342be6e34371a27c06f7dc0edddd2f86373"

# https://cryptography.io/en/latest/hazmat/primitives/asymmetric/dh/
class BlufiCrypto(object):
    def __init__(self):
        self.p = int(DH_P, 0)
        self.g = 2
        self.y = 0
        self.privKey = None
        self.pubKey = None

    def genKeys(self):
        pn = dh.DHParameterNumbers(self.p, self.g)
        parameters = pn.parameters()
        self.privKey = parameters.generate_private_key()
        self.pubKey = self.privKey.public_key()
        self.y = self.pubKey.public_numbers().y

    def deriveSharedKey(self, peer_pub_bytes):
        pn = dh.DHParameterNumbers(self.p, self.g)
        parameters = pn.parameters()
        y = int.from_bytes(peer_pub_bytes, "big")
        peer_public_numbers = dh.DHPublicNumbers(y, pn)
        peer_public_key = peer_public_numbers.public_key()
        shared_key = self.privKey.exchange(peer_public_key)
        # print('got shared key:')
        # dump_bytes(shared_key)
        digest = hashes.Hash(hashes.MD5())
        digest.update(shared_key)
        return digest.finalize()

    def getPBytes(self):
        return bytes.fromhex(DH_P[2:])

    def getGBytes(self):
        return bytes.fromhex('02')

    def getYBytes(self):
        pub_bytes = self.y.to_bytes(2048 // 8, 'big')
        return pub_bytes
