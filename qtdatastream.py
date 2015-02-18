'''The qtdatastream module provides wrapper classes around the struct
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

QINT16 = 130
QINT8 = 131
QUINT16 = 133
QUINT8 = 134

_qt_types = {}
_user_types = {}
_python_types = {}

def register_mapping(qt_type, python_type = None):
    def decorator(cls):
        if python_type is not None:
            _python_types[python_type] = cls
        _qt_types[qt_type] = cls.decode
        setattr(cls, 'QT_TYPE', qt_type)
        return cls
    return decorator

def register_user_type(name):
    def decorator(cls):
        if cls not in _qt_types and not hasattr(cls, 'decode'):
            raise TypeError('class does not provide decode method')
        _user_types[name] = cls
        return cls
    return decorator

class DataStreamException(Exception):
    pass


class DecodeException(DataStreamException):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class EncodeException(DataStreamException):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class QtType:
    pass

@register_mapping(QUSERTYPE)
class UserType(QtType):
    @staticmethod
    def decode(data):
        name_length = Quint32.decode(data)
        name = data.read(name_length)[:-1].decode('utf-8')
        if name in _user_types:
            if _user_types[name] in _qt_types:
                return _qt_types[_user_types[name]](data)
            else:
                return _user_types[name].decode(data)

        raise DecodeException('unknown user type {0}'.format(name))

@register_mapping(QBOOL, bool)
class QBool(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        return Quint8(1 if self.data else 0).encode()

    @staticmethod
    def decode(data):
        data = Quint8.decode(data)
        return  data == 1

@register_mapping(QINT8)
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

@register_mapping(QUINT8)
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

@register_mapping(QINT16)
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

@register_mapping(QUINT16)
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

@register_mapping(QINT)
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

@register_mapping(QUINT)
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

@register_mapping(QBYTEARRAY, bytes)
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

@register_mapping(QSTRING, str)
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

@register_mapping(QSTRINGLIST)
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

@register_mapping(QDATE, datetime.date)
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

        if julian_day == 0: #QDate::nullJd
            return None
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

@register_mapping(QTIME, datetime.time)
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
            return None

        seconds, milliseconds = divmod(milliseconds, 1000)
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)

        return datetime.time(hours, minutes, seconds, milliseconds * 1000)

@register_mapping(QDATETIME, datetime.datetime)
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
        is_utc = Quint8.decode(data.read(1)) #TODO handle?

        if date == None or time == None:
            return None
        return datetime.datetime.combine(date, time)

class QVariant(QtType):
    def __init__(self, data):
        self.data = data

    def encode(self):
        data = bytearray()
        if hasattr(self.data.__class__, 'QT_TYPE') and hasattr(self.data, 'encode'):
            data.extend(Quint32(self.data.QT_TYPE).encode())    #QVariant type
            data.extend(Qint8(0).encode())              #null flag
            data.extend(self.data.encode())
        elif type(self.data) in _python_types:
            cls = _python_types[type(self.data)]
            data.extend(Quint32(cls.QT_TYPE).encode())
            data.extend(Qint8(0).encode())              #null flag
            data.extend(cls(self.data).encode())
        else:
            raise EncodeException('invalid data type {0}'.format(type(self.data).__name__))

        return data

    @staticmethod
    def decode(data):
        type = Quint32.decode(data)
        data.read(1)    #ignore null flag
        if type in _qt_types:
            return _qt_types[type](data)
        else:
            raise DecodeException('invalid data type {0} at position {1}'.format(type, data.tell() - 5))

@register_mapping(QVARIANTMAP)
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

@register_mapping(QVARIANTLIST)
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
                raise EncodeException('{0} is not a qt type'.format(type(value).__name__))
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