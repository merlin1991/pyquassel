'''The qtdatastream mopdule provides wrapper classes around the struct
module to work with binary data according to DataStream version 8 (Qt_4_2)

All helper classes implement a static decode function that decodes a
python type out of a bytes object.

In order to facilitate custom user types in QVariant all custom types must
be registered via the register_user_type module function'''

import datetime
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
QDATE = 14
QTIME = 15
QDATETIME = 16

QUSERTYPE = 127

#found via debugging quassel
QUINT16 = 133

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
        if isinstance(data, io.BytesIO):
            data = data.read(1)
        return struct.unpack('b', data)[0]

class Quint8(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        return struct.pack('B', self.data)

    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            data = data.read(1)
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
        
class Quint16(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        return struct.pack('!H', self.data)

    @staticmethod
    def decode(data):
        if isinstance(data, io.BytesIO):
            data = data.read(2)
        return struct.unpack('!H', data)[0]

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
    def __init__(self, data):
        self.data = data

    def encode(self):
        if self.data == None:
            return struct.pack('!I', 0xFFFFFFFF)

        data = bytearray()
        data.extend(Quint32(len(self.data)).encode())
        data.extend(self.data)
        return data

    @staticmethod
    def decode(data):
        length = Quint32.decode(data)
        if length == 0xFFFFFFFF:
            return None

        return data.read(length)

class QString(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        if self.data == None:
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
            return None

        string = data.read(length).decode('utf-16-be')
        return string

class QStringList(QtType):
    def __init__(self, data):
        self.data = data

    @staticmethod
    def decode(data):
        count = Quint32.decode(data)
        list = []
        for i in range(count):
            list.append(QString.decode(data))

        return list

class QDate(QtType):
    '''
    Math from The Calendar FAQ at http://www.tondering.dk/claus/cal/julperiod.php
    The formulas are correct for all julian days, when using mathematical integer
    division (round to negative infinity), not c++11 integer division (round to zero)
    '''
    def __init__(self, data):
        self.data = data

    def encode(self):
        a = (14 - self.data.month) // 12
        y = self.data.year + 4800 - a
        m = self.data.month + 12 * a - 3

        julian_day = self.data.day + (153 * m +2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
        return Quint32(julian_day).encode()

    @staticmethod
    def decode(data):
        julian_day = Quint32.decode(data)
        a = julian_day + 32044
        b = (4 * a + 3) // 146097
        c = a - (146097 * b) // 4
        d = (4 * c + 3) // 1461
        e = c - (1461 * d) // 4
        m = (5 * e + 1) // 153

        day = e - (153 * m +2) // 5 + 1
        month = m + 3 - 12 * (m // 10)
        year = 100 * b + d - 4800 + m // 10

        #python can only handle years >= 1
        if year < 1:
            return datetime.date(1,1,1)

        return datetime.date(year, month, day)

class QTime(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        milliseconds = self.data.hour * 60 * 60 * 1000 + \
                        self.data.minute * 60 * 1000 + \
                        self.data.second * 1000 + \
                        self.data.microsecond // 1000

        return Quint32(milliseconds).encode()

    @staticmethod
    def decode(data):
        milliseconds = Quint32.decode(data)
        if milliseconds == 0xFFFFFFFF:
            return datetime.time(0, 0, 0, 0)

        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        return datetime.time(hours, minutes, seconds, milliseconds * 1000)

class QDateTime(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        data = bytearray()
        data.extend(QDate(self.data.date()).encode())
        data.extend(QTime(self.data.time()).encode())
        data.append(1)
        return data

    @staticmethod
    def decode(data):
        date = QDate.decode(data)
        time = QTime.decode(data)

        is_utc = Quint8.decode(data.read(1))
        if is_utc != 1:
            print('non utc date!') #Exception

        return datetime.datetime.combine(date, time)

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
        elif isinstance(self.data, Qint16):
            data.extend(Quint32(QINT).encode())  #QVariant type
            data.extend(Qint8(0).encode())         #null flag
            data.extend(Qint32(self.data.data).encode())
        elif isinstance(self.data, QDateTime):
            data.extend(Quint32(QDATETIME).encode())    #QVariant type
            data.extend(Qint8(0).encode())              #null flag
            data.extend(self.data.encode())
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
            return QByteArray.decode(data)
        elif type == QDATE:
            return QDate.decode(data)
        elif type == QTIME:
            return QTime.decode(data)
        elif type == QDATETIME:
            return QDateTime.decode(data)
        elif type == QUSERTYPE:
            name_length = Quint32.decode(data)
            name = data.read(name_length)[:-1].decode('utf-8')
            if name in _user_types:
                return _user_types[name].decode(data)

            print('unknown user type {0}'.format(name))
        elif type == QUINT16:
            return Quint16.decode(data)
            
        else:
            print('invalid data type {0} at position {1}'.format(type, data.tell() - 5)) #EXCEPTIONS

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