import asyncio
import io
import logging

import quassel
import qtdatastream
from qtdatastream import register_user_type, Quint8, Qint16, Qint32, Quint32, QByteArray, QDateTime, QVariant, QVariantMap, QVariantList

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

class Message(qtdatastream.QtType):
    def __init__(self, data):
        self.data = data

    @staticmethod
    def decode(data):
        return {
            'msgId' : Qint32.decode(data),
            'timeStamp' : Quint32.decode(data),
            'type' : Quint32.decode(data),
            'flags': Quint8.decode(data),
            'bufferInfo' : BufferInfo.decode(data),
            'sender' : QByteArray.decode(data).decode('utf-8'),
            'contents' : QByteArray.decode(data).decode('utf-8')
        }


class QuasselClientProtocol(asyncio.Protocol):
    def __init__(self, loop, user, password):
        self.loop = loop
        self.user = user
        self.password = password
        self._probing = True
        self._handshake = False
        self._buffer = io.BytesIO()

        register_user_type('NetworkId', Qint32)
        register_user_type('Identity', QVariantMap)
        register_user_type('IdentityId', Qint32)
        register_user_type('BufferInfo', BufferInfo)
        register_user_type('BufferId', Qint32)
        register_user_type('Message', Message)

    def connection_made(self, transport):
        log = logging.getLogger(__name__)
        log.info('Connection made')
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
            self._buffer.write(data)
            self.handle_data()

    def handle_data(self):
            buffer_end = self._buffer.tell()

            if buffer_end >= 4:         #can we read message size?
                self._buffer.seek(0)
                message_length = Quint32.decode(self._buffer)

                if message_length > buffer_end + 4:
                    self._buffer.seek(buffer_end)
                else:                   #enough data for one message
                    self.handle_message(self._buffer)
                    buffer_position = self._buffer.tell()

                    while buffer_end - buffer_position >= 4: #any trailing messages in the data?
                        message_length = Quint32.decode(self._buffer)

                        if message_length <= buffer_end - (buffer_position + 4):
                            self.handle_message(self._buffer)

                        else:
                            break

                        buffer_position = self._buffer.tell()

                    available_bytes = buffer_end - buffer_position

                    if available_bytes > 0:
                        self._buffer.seek(buffer_position)
                        partial_message = self._buffer.read()
                        self._buffer.seek(0)
                        self._buffer.write(partial_message)
                    elif available_bytes == 0:
                        self._buffer.seek(0)

    def connection_lost(self, exc):
        log = logging.getLogger(__name__)
        log.warning('Connection lost')
        self.loop.stop()

    def handle_probe_response(self, data):
        log = logging.getLogger(__name__)
        probe_response = Quint32.decode(data)
        self.proto_type = probe_response & 0xFF
        log.info('protocol type: {0}'.format(quassel.PROTOCOLS[self.proto_type]))
        self.proto_features = probe_response >> 8 & 0xFFFF
        log.info('protocol features: {0}'.format(repr(self.proto_features)))
        self.connection_features = probe_response >> 24
        log.info('connection features: {0}'.format(', '.join([quassel.FEATURES[i] for i in quassel.FEATURES if self.connection_features & i])))
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
        data = QVariantList([QVariant(x) for x in message]).encode()
        self.transport.write(Quint32(len(data)).encode())   #Message length
        self.transport.write(data)                          #Message data

    def send_legacy_message(self, message):
        data = self.data_streamify(message)
        self.transport.write(Quint32(len(data)).encode())   #Message length
        self.transport.write(data)                          #Message data

    def register_client(self):
        message = { 'MsgType' : 'ClientInit', 'ClientVersion': 'v0.11.0 (unknown revision)', 'ClientDate': 'Jan 11 2015 15:41:00' }
        self.send_legacy_message(message)

    def handle_message(self, raw_message_stream):
        log = logging.getLogger(__name__)
        list_data = QVariantList.decode(raw_message_stream)

        if not self._handshake:
            message_data = self.data_destreamify(list_data)
            log.debug(repr(message_data))

            msg_type = message_data['MsgType']
            if msg_type == 'ClientInitAck':
                self.handle_client_init_ack(message_data)
            elif msg_type == 'ClientLoginAck':
                log.info('Password accepted')
            elif msg_type == 'ClientLoginReject':
                pass
            elif msg_type == 'SessionInit':
                self.handle_session_init(message_data)
            else:
                log.warning('Unknown message type {0}'.format(msg_type))
        else:
            self.handle_regular_message(list_data)

    def handle_client_init_ack(self, data):
        log = logging.getLogger(__name__)
        if not data['Configured']:
            log.error('Core is not configured!')
        else:
            log.info('Sending login data')
            message = { 'MsgType' : 'ClientLogin', 'User' : self.user, 'Password' : self.password }
            self.send_legacy_message(message)

    def handle_session_init(self, data):
        self._handshake = True

    def handle_regular_message(self, message):
        log = logging.getLogger(__name__)
        log.debug('message: {0}'.format(repr(message)))

        if len(message) == 0:
            log.error('invalid message')
            return

        message_type = message[0]

        if message_type == 1:
            log.debug('sync')
            if len(message) < 4:
                log.error('invalid sync call')
                return

            class_name = message[1]
            object_name = message[2]
            if object_name != None:
                object_name = object_name.decode('utf-8')
            function_name = message[3]
            params = message[4:]

            #call object!

        elif message_type == 2:
            log.debug('rpc call')
            if len(message) == 1:
                log.error('empty rpc call')
                return

            #handle rpc call

        elif message_type == 3:
            log.debug('init request')
            if len(message) != 3:
                log.error('invalid init request')
                return

            #handle init request

        elif message_type == 4:
            log.debug('init data')
            if len(message) < 3:
                log.error('invalid init data')
                return

            #handle init data

        elif message_type == 5:
            log.debug('heart beat')

            if len(message) != 2:
                log.error('invalid heart beat')

            self.send_message([Qint16(6), QDateTime(message[1])])

        elif message_type == 6:
            log.debug('heart beat reply')

            if len(message) != 2:
                log.error('invalid heart beat reply')

            #handle heart beat reply!

        else:
            log.error('invalid message type {0}'.format(message_type))