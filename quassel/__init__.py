PROTOCOL_VERSION = 10
MAGIC = 0x42b33f00

FEATURE_ENCRYPTION = 0x01
FEATURE_COMPRESSION = 0x02
FEATURES = { FEATURE_ENCRYPTION : 'encryption', FEATURE_COMPRESSION : 'compression' }

DATASTREAMPROTOCOL = 0x02
DATASTREAMFEATURES = 0

PROTOCOLS = { DATASTREAMPROTOCOL : 'datastream' }

LIST_END = 0x80000000

#network message types
SYNC = 0x1
RPC = 0x2
INIT_REQUEST = 0x3
INIT_DATA = 0x4
HEART_BEAT = 0x5
HEART_BEAT_REPLY = 0x6

from .protocol import QuasselClientProtocol