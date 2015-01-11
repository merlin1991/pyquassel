'''The qtdatastream mopdule provides wrapper classes around the struct
module to work with binary data according to DataStream version 8 (Qt_4_2)

All helper classes implement a static decode function that decodes a
python type out of a bytes object.

In order to facilitate custom user types in QVariant all custom types must
be registered via the register_user_type module function'''

import io
import struct

QBOOL = 1
QINT = 2
QUINT = 3
QVARIANTMAP = 8
QVARIANTLIST = 9
QSTRING = 10
QSTRINGLIST = 11
QBYTEARRAY = 12

QUSERTYPE = 127

_user_types = {}

def register_user_type(name, type):
    global _user_types
    _user_types[name] = type

class QtType:
    pass
    
class Qint8(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        return struct.pack('b', self.data)
        
    @staticmethod
    def decode(data):
        return struct.unpack('b', data)[0]
        
class Quint8(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        return struct.pack('B', self.data)
        
    @staticmethod
    def decode(data):
        return struct.unpack('B', data)[0]
    
class Qint16(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        return struct.pack('!h', self.data)
        
    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            data = data.read(2)
        return struct.unpack('!h', data)[0]
    
class Qint32(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        return struct.pack('!i', self.data)
        
    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            data = data.read(4)
        return struct.unpack('!i', data)[0]
    
class Quint32(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        return struct.pack('!I', self.data)
        
    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            data = data.read(4)
        return struct.unpack('!I', data)[0]
        
class QByteArray(QtType):
    @staticmethod
    def decode(data):
        length = Quint32.decode(data)
        if length == 0xFFFFFFFF:
            return b''

        return data.read(length)
            
class QString(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        if len(self.data) == 0:
            return struct.pack('!I', 0xFFFFFFFF)
            
        data = bytearray()
        array_data = self.data.encode('utf-16-be')
        data.extend(Quint32(len(array_data)).encode())  #QString length
        data.extend(array_data)                         #QString data
        return data
            
    @staticmethod
    def decode(data):
        length = Quint32.decode(data.read(4))
        if length == 0xFFFFFFFF:
            return ''
        
        string = data.read(length).decode('utf-16-be')
        return string
        
class QStringList(QtType):
    def __init__(self, data):
        self.data = data
        
    @staticmethod
    def decode(data):
        count = Quint32.decode(data.read(4))
        list = []
        for i in range(count):
            list.append(QString.decode(data))
            
        return list
            
class QVariant(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        data = bytearray()
        if isinstance(self.data, bool):
            data.extend(Quint32(QBOOL).encode())  #QVariant type
            data.extend(Qint8(0).encode())          #null flag
            if self.data:
                data.append(1)
            else:
                data.append(0)
        elif isinstance(self.data, str):
            data.extend(Quint32(QSTRING).encode())  #QVariant type
            data.extend(Qint8(0).encode())          #null flag
            data.extend(QString(self.data).encode())
        elif isinstance(self.data, bytes):
            data.extend(Quint32(QBYTEARRAY).encode())   #QVariant type
            data.extend(Qint8(0).encode())              #null flag
            data.extend(Quint32(len(self.data)).encode())   #QByteArray length
            data.extend(self.data)                          #QbyteArray data
        else:
            print('invalid data type') #EXCEPTIONS!
            
        return data
    
    @staticmethod
    def decode(data):
        global _user_types
        type = Quint32.decode(data)
        data.read(1)    #ignore null flag
        if type == QBOOL:
            return data.read(1) != 0x00
        elif type == QINT:
            return Qint32.decode(data)
        elif type == QUINT:
            return Quint32.decode(data)
        elif type == QSTRING:
            return QString.decode(data)
        elif type == QSTRINGLIST:
            return QStringList.decode(data)
        elif type == QVARIANTMAP:
            return QVariantMap.decode(data)
        elif type == QVARIANTLIST:
            return QVariantList.decode(data)
        elif type == QBYTEARRAY:
            length = Quint32.decode(data)
            return data.read(length)
        elif type == QUSERTYPE:
            name_length = Quint32.decode(data)
            name = data.read(name_length)[:-1].decode('utf-8')
            if name in _user_types:
                return _user_types[name].decode(data)
            
            print('unkown user type {0}'.format(name))
            
        else:
            print('invalid data type {0}'.format(type)) #EXCEPTIONS
        
class QVariantMap(QtType):
    def __init__(self, data):
        self.data = data
        
    @staticmethod
    def decode(data):
        entries = Quint32.decode(data)
        dict = {}
        for i in range(entries):
            key = QString.decode(data)
            dict[key] = QVariant.decode(data)
            
        return dict
        
class QVariantList(QtType):
    def __init__(self, data):
        self.data = data
        
    def encode(self):
        data = bytearray()
        data.extend(Quint32(len(self.data)).encode())   #QList length
        for value in self.data:
            if isinstance(value, QtType):
                data.extend(value.encode())
            else:
                print('not a qt type') #EXCEPTIONS!
        return data
        
    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            buffer = data
        else:
            buffer = io.BytesIO()
            buffer.write(data)
            buffer.seek(0)
        length = Quint32.decode(buffer)
        
        list_data = []
        
        for x in range(length):
            list_data.append(QVariant.decode(buffer))
        
        return list_data