from pydantic import BaseModel

class OpcodeErrorCode(BaseModel):
    """
    Opcode 255 Error Code definition.
    """

    error_code: int
    """Numeric error code."""

    error_description: str
    """Error description."""

    cause_byte_description: str
    """Description of the byte that cause the error."""



class OpcodeErrorCodes:
    _1 = OpcodeErrorCode(error_code=1, error_description='Invalid Opcode request.', cause_byte_description='Opcode')
    _2 = OpcodeErrorCode(error_code=2, error_description='Invalid parameter number.', cause_byte_description='Parameter number')
    _3 = OpcodeErrorCode(error_code=3, error_description='Invalid logical number.', cause_byte_description='Logical number')
    _4 = OpcodeErrorCode(error_code=4, error_description='Invalid point type.', cause_byte_description='Point type')
    _5 = OpcodeErrorCode(error_code=5, error_description='Received too many data bytes.', cause_byte_description='Length')
    _6 = OpcodeErrorCode(error_code=6, error_description='Received too few data bytes.', cause_byte_description='Length')
    _12 = OpcodeErrorCode(error_code=12, error_description='Obsolete (Reserved, but not used)', cause_byte_description='None')
    _13 = OpcodeErrorCode(error_code=13, error_description='Outside valid address range.', cause_byte_description='Address')
    _14 = OpcodeErrorCode(error_code=14, error_description='Invalid history request.', cause_byte_description='History point number')
    _15 = OpcodeErrorCode(error_code=15, error_description='Invalid FST request', cause_byte_description='FST command number')
    _16 = OpcodeErrorCode(error_code=16, error_description='Invalid event entry.', cause_byte_description='Event code')
    _17 = OpcodeErrorCode(error_code=17, error_description='Requested too many alarms.', cause_byte_description='Number of alarms requested')
    _18 = OpcodeErrorCode(error_code=18, error_description='Requested too many events.', cause_byte_description='Number of events requested')
    _19 = OpcodeErrorCode(error_code=19, error_description='Write to read only parameter.', cause_byte_description='Parameter number')
    _20 = OpcodeErrorCode(error_code=20, error_description='Security error.', cause_byte_description='Opcode')
    _21 = OpcodeErrorCode(error_code=21, error_description='Invalid security logon.', cause_byte_description='Login ID or Password')
    _22 = OpcodeErrorCode(error_code=22, error_description='Invalid store and forward path.', cause_byte_description='Any address or group')
    _24 = OpcodeErrorCode(error_code=24, error_description='History configuration in progress.', cause_byte_description='Opcode')
    _25 = OpcodeErrorCode(error_code=25, error_description='Invalid parameter range', cause_byte_description='Parameter')
    _29 = OpcodeErrorCode(error_code=29, error_description='Invalid 1 day history index request.', cause_byte_description='History Segment, point, day or month')
    _30 = OpcodeErrorCode(error_code=30, error_description='Invalid history point.', cause_byte_description='History Point')
    _31 = OpcodeErrorCode(error_code=31, error_description='Invalid Min/Max request.', cause_byte_description='History segment or point number')
    _32 = OpcodeErrorCode(error_code=32, error_description='Invalid TLP.', cause_byte_description='Point type, parameter, or logical number')
    _33 = OpcodeErrorCode(error_code=33, error_description='Invalid time.', cause_byte_description='Seconds, minutes, hours, days, months, or years')
    _34 = OpcodeErrorCode(error_code=34, error_description='Illegal Modbus range', cause_byte_description='Point/Logical number')
    _50 = OpcodeErrorCode(error_code=50, error_description='General Error', cause_byte_description='Any')
    _51 = OpcodeErrorCode(error_code=51, error_description='Invalid State for Write', cause_byte_description='Point type')
    _52 = OpcodeErrorCode(error_code=52, error_description='Invalid Configurable Opcode Request', cause_byte_description='Starting Table Location')
    _61 = OpcodeErrorCode(error_code=61, error_description='HART Passthrough Comm Scanner', cause_byte_description='See Opcode 200 or passthrough disabled on this channel')
    _62 = OpcodeErrorCode(error_code=62, error_description='HART passthrough not licensed', cause_byte_description='See Opcode 200')
    _63 = OpcodeErrorCode(error_code=63, error_description='Requested Access Level Too High', cause_byte_description='Access Level')
    _77 = OpcodeErrorCode(error_code=77, error_description='Invalid logoff string', cause_byte_description='Ignored')

    @staticmethod
    def get_error_code(error_code: int) -> OpcodeErrorCode:
        error_code_key: str = f'_{error_code}'
        if hasattr(OpcodeErrorCodes, error_code_key):
            return getattr(OpcodeErrorCodes, error_code_key)
        else:
            raise KeyError(f'No error code found for provided code: {error_code}')