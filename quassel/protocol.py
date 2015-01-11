import asyncio
import io
import logging

import quassel
import qtdatastream
from qtdatastream import register_user_type, Qint16, Qint32, Quint32, QByteArray, QVariant, QVariantMap, QVariantList

class BufferInfo(qtdatastream.QtType):
    def __init__(self, data):
        self.data = data
        
    @staticmethod
    def decode(data):
        return {
            'bufferId' : Qint32.decode(data),
            'networkId' : Qint32.decode(data),
            'type' : Qint16.decode(data),
            'groupId' : Quint32.decode(data),
            'name' : QByteArray.decode(data).decode('utf-8')
        }

class QuasselClientProtocol(asyncio.Protocol):
    def __init__(self, loop, user, password):
        self.loop = loop
        self.user = user
        self.password = password
        self._probing = True
        self._handshake = False
        self._size = 0
        self._buffer = io.BytesIO()
        
        register_user_type('NetworkId', Qint32)
        register_user_type('Identity', QVariantMap)
        register_user_type('IdentityId', Qint32)
        register_user_type('BufferInfo', BufferInfo)
        
    def connection_made(self, transport):
        log = logging.getLogger(__name__)
        log.info('connection made')
        self.transport = transport
        
        probe_data = bytearray()
        probe_data.extend(Quint32(quassel.MAGIC).encode()) # to enable encryption and compression: | quassel.FEATURE_ENCRYPTION | quassel.FEATURE_COMPRESSION
        probe_data.extend(Quint32(quassel.DATASTREAMPROTOCOL | quassel.DATASTREAMFEATURES | quassel.LIST_END).encode())
        transport.write(probe_data)
        
    def data_received(self, data):
        log = logging.getLogger(__name__)
        log.debug('data received: {0}'.format(repr(data)))
        if self._probing:
            self.handle_probe_response(data)
        else:
            if self._size == 0:
                self._buffer.write(data)
                if len(data) >= 4:
                    bufferpos = self._buffer.tell()
                    self._buffer.seek(0)
                    self._size = Quint32.decode(self._buffer.read(4))
                    if bufferpos == self._size + 4:
                        self.handle_message(self._buffer)
                        self._buffer.seek(0)
                        self._size = 0
                    else:
                        self._buffer.seek(bufferpos)
            else:
                self._buffer.write(data)
                bufferpos = self._buffer.tell()
                if bufferpos == self._size + 4:
                    self._buffer.seek(4)
                    self.handle_message(self._buffer)
                    self._buffer.seek(0)
                    self._size = 0
    
    def connection_lost(self, exc):
        log = logging.getLogger(__name__)
        log.warning('connection lost')
        self.loop.stop()
        
    def handle_probe_response(self, data):
        log = logging.getLogger(__name__)
        probe_response = Quint32.decode(data)
        self.proto_type = probe_response & 0xFF
        log.debug('protocol type: {0}'.format(quassel.PROTOCOLS[self.proto_type]))
        self.proto_features = probe_response>>8 & 0xFFFF
        log.debug('protocol features: {0}'.format(repr(self.proto_features)))
        self.connection_features = probe_response >> 24
        log.debug('connection features: {0}'.format(', '.join([quassel.FEATURES[i] for i in quassel.FEATURES if self.connection_features & i])))
        self._probing = False
        self.register_client()
        
    def data_streamify(self, message):
        data = []
        for key in message:
            data.append(QVariant(key.encode('utf-8')))
            data.append(QVariant(message[key]))
            
        return QVariantList(data).encode()
        
    def data_destreamify(self, list):
        assert len(list) % 2 == 0
        data = {}
        
        for i in range(len(list) // 2):
            data[list[i * 2].decode('utf-8')] = list[i * 2 + 1]
        
        return data
    
    def send_message(self, message):
        data = self.data_streamify(message)
        self.transport.write(Quint32(len(data)).encode())   #Message length
        self.transport.write(data)                          #Message data
    
    def register_client(self):
        message = { 'MsgType' : 'ClientInit', 'ClientVersion': 'v0.11.0 (unknown revision)', 'ClientDate': 'Jan 11 2015 15:41:00' }
        self.send_message(message)
        
    def handle_message(self, raw_message_stream):
        log = logging.getLogger(__name__)
        list_data = QVariantList.decode(raw_message_stream)
        
        if not self._handshake:            
            message_data = self.data_destreamify(list_data)
            log.info(repr(message_data))
        
            msg_type = message_data['MsgType']
            if msg_type == 'ClientInitAck':
                self.handle_client_init_ack(message_data)
            elif msg_type == 'ClientLoginAck':
                pass
            elif msg_type == 'ClientLoginReject':
                pass
            elif msg_type == 'SessionInit':
                self.handle_session_init(message_data)
            else:
                log.warning('Unkown message type {0}'.format(msg_type))
        else:
            self.handle_regular_message(list_data)
                
    def handle_client_init_ack(self, data):
        log = logging.getLogger(__name__)
        if not data['Configured']:
            log.error('Core is not configured!')
        else:
            log.info('Sending login data')
            message = { 'MsgType' : 'ClientLogin', 'User' : self.user, 'Password' : self.password }
            self.send_message(message)
            
    def handle_session_init(self, data):
        self._handshake = True
        
    def handle_regular_message(self, message):
        pass