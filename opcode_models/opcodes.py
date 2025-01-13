from typing import Type, List, Optional, Dict, Any, TypeVar, Generic
import struct
from datetime import datetime
from pydantic import BaseModel, PlainSerializer
from enum import Enum
from typing_extensions import Annotated
from abc import ABC, abstractmethod
from opcode_models.error_codes import OpcodeErrorCodes, OpcodeErrorCode
from tlp_models.tlp import TLPInstance, TLPValue
from tlp_models.point_type import PointType
from tlp_models.point_types import PointTypes
from tlp_models.parameter import Parameter

class DeviceData(BaseModel):

    roc_address: int
    """ROC address for the target device."""
    
    roc_group: int
    """ROC group for the target device."""
    
    host_address: int = 1
    """Address of requesting device. Defaults to 1."""
    
    host_group: int = 0
    """Group of requesting device. Defaults to 0."""

    def to_binary_request(self) -> bytes:
        return struct.pack(
            'BBBB',
            self.roc_address,
            self.roc_group,
            self.host_address,
            self.host_group
        )

    @classmethod
    def response_from_binary(cls, raw_response: bytes) -> 'DeviceData':
        device_bytes: bytes = raw_response[0:4]
        host_address, host_group, roc_address, roc_group = struct.unpack('BBBB', device_bytes)
        return DeviceData(
            roc_address=roc_address,
            roc_group=roc_group,
            host_address=host_address,
            host_group=host_group
        )

class RequestData(BaseModel, ABC):

    opcode: int

    @property
    def opcode_binary(self) -> bytes:
        return struct.pack('B', self.opcode)

    @property
    @abstractmethod
    def data_binary(self) -> bytes:
        return b''

    @property
    def data_length(self) -> int:
        return len(self.data_binary)

    def to_binary(self) -> bytes:
        data_binary: bytes = self.data_binary
        data_length_binary: bytes = struct.pack('B', self.data_length)
        return (self.opcode_binary + data_length_binary + data_binary)
    


class EmptyResponseData(BaseModel):
    pass


T = TypeVar('T', bound=BaseModel)


class ResponseData(BaseModel, ABC, Generic[T]):

    opcode: int

    data_length: int

    data: Optional[T] = None

    @classmethod
    def opcode_from_binary(cls, raw_response: bytes) -> int:
        return int(raw_response[4])

    @classmethod
    def data_length_from_binary(cls, raw_response: bytes) -> int:
        return int(raw_response[5])

    @classmethod
    @abstractmethod
    def data_from_binary(cls, raw_response: bytes) -> T:
        pass

    @classmethod
    def from_binary(cls, raw_response: bytes) -> 'ResponseData':
        opcode: int = cls.opcode_from_binary(raw_response=raw_response)
        data_length: int = cls.data_length_from_binary(raw_response=raw_response)
        data: Optional[T] = None
        if data_length > 0:
            data = cls.data_from_binary(raw_response=raw_response)
        return cls(
            opcode=opcode,
            data_length=data_length,
            data=data
        )


class MessageModel(BaseModel):
    """
    Model for a specific Opcode.
    
    Describes the contents of request and response data.
    """

    opcode_desc: str
    """Description of Opcode."""

    request_data: Type[RequestData]
    """Model for opcode-specific request data."""

    response_data: Type[ResponseData]
    """Model for opcode-specific response data."""


"""Opcode 6: System Configuration"""

class SystemConfigRequestData(RequestData):
    
    opcode: int = 6

    @property
    def data_binary(self) -> bytes:
        return b''


class ROCOperatingMode(Enum):
    FIRMWARE_UPDATE_MODE = 0
    RUN_MODE = 1

class LogicalCompatibilityStatus(Enum):
    _16_POINTS_PER_SLOT_9_SLOTS_MAX = 0
    _16_POINTS_PER_SLOT_14_SLOTS_MAX = 1
    _8_POINTS_PER_SLOT_27_SLOTS_MAX = 2

class OpcodeRevision(Enum):
    ORIGINAL = 0
    EXTENDED_FOR_ADDITIONAL_POINT_TYPES = 1

class ROCSubType(Enum):
    SERIES_2 = 0
    SERIES_1 = 1

class ROCType(Enum):
    ROCPAC_ROC300_SERIES = 1
    FLO_BOSS_407 = 2
    FLASHPAC_ROC300_SERIES = 3
    FLO_BOSS_503 = 4
    FLO_BOSS_504 = 5
    ROC_800 = 6
    DL_800 = 11


class SystemConfigData(BaseModel):
    """
    System Configuration data.
    """

    operating_mode: Annotated[ROCOperatingMode, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """The system mode the unit is currently operating in."""

    comm_port: int
    """Comm Port or Port Number that this request arrived on."""

    security_access_mode: int
    """Security Access Mode for the port the request was received on."""

    compatibility_status: Annotated[LogicalCompatibilityStatus, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """Logical Compatibility Status (see Point Type 91, Logical 0, Parameter 50)."""

    opcode_revision: Annotated[OpcodeRevision, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """Opcode 6 Revision."""

    roc_subtype: Annotated[ROCSubType, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """ROC Subtype."""

    roc_type: Annotated[ROCType, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """Type of ROC."""

    point_type_counts: Dict[int, int]
    """Number of logical points for each point type, indexed by point type ID."""


class SystemConfigResponseData(ResponseData[SystemConfigData]):
    """
    Response data model for System Configuration request.
    """

    data: Optional[SystemConfigData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> SystemConfigData:
        operating_mode: int = int(raw_response[6])
        comm_port: int = struct.unpack('h', raw_response[7:9])[0]
        security_access_mode: int = int(raw_response[9])
        compatibility_status: int = int(raw_response[10])
        opcode_revision: int = int(raw_response[11])
        roc_subtype: int = int(raw_response[12])
        roc_type: int = int(raw_response[24])
        point_type_counts: Dict[int, int] = {}
        for i in range(25, 221):
            point_type: int = i + 35
            point_type_counts[point_type] = int(raw_response[i])
        return SystemConfigData(
            operating_mode=ROCOperatingMode(operating_mode),
            comm_port=comm_port,
            security_access_mode=security_access_mode,
            compatibility_status=LogicalCompatibilityStatus(compatibility_status),
            opcode_revision=OpcodeRevision(opcode_revision),
            roc_subtype=ROCSubType(roc_subtype),
            roc_type=ROCType(roc_type),
            point_type_counts=point_type_counts
        )




"""Opcode 7: Read Real-time Clock"""

class ReadClockRequestData(RequestData):

    opcode: int = 7

    @property
    def data_binary(self) -> bytes:
        return b''



class ReadClockData(BaseModel):

    current_second: int

    current_minute: int

    current_hour: int

    current_day: int

    current_month: int

    current_year: int

    current_day_of_week: int

    @property
    def as_datetime(self) -> datetime:
        return datetime(
            year=self.current_year,
            month=self.current_month,
            day=self.current_day,
            hour=self.current_hour,
            minute=self.current_minute,
            second=self.current_second
        )


class ReadClockResponseData(ResponseData[ReadClockData]):

    data: Optional[ReadClockData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> ReadClockData:
        current_second, current_minute, current_hour, current_day, current_month, current_year, current_day_of_week = struct.unpack('<BBBBBHB', raw_response[6:14])
        return ReadClockData(
            current_second=current_second,
            current_minute=current_minute,
            current_hour=current_hour,
            current_day=current_day,
            current_month=current_month,
            current_year=current_year,
            current_day_of_week=current_day_of_week
        )
    


"""Opcode 10: Read Configurable Opcode Point Data"""

class OpcodeTableRequestData(RequestData):

    opcode: int = 10

    table_number: int

    starting_location: int

    number_of_locations: int

    @property
    def data_binary(self) -> bytes:
        return struct.pack(
            'BBB',
            self.table_number,
            self.starting_location,
            self.number_of_locations 
        )


class OpcodeTableData(BaseModel):

        table_number: int

        starting_location: int

        number_of_locations: int

        table_version_number: float

        data: Any


class OpcodeTableResponseData(ResponseData[OpcodeTableData]):
    
    data: Optional[OpcodeTableData] = None

    @classmethod
    def data_from_binary(cls, raw_response):
        return super().data_from_binary(raw_response)



"""Opcode 50: Request I/O Point Position"""

class IOLocationRequestType(Enum):

    IO_POINT_TYPE = 0

    LOGICAL_NUMBER = 1

class IOLocationRequestData(RequestData):

    opcode: int = 50

    request_type: IOLocationRequestType
    """0 = I/O Point Type, 1 = I/O Logical Number"""

    @property
    def data_binary(self) -> bytes:
        return struct.pack('B', self.request_type.value)
    

class IOLocationData(BaseModel):

        location_data: Dict[int, int]
        """Location data indexed by physical I/O location."""


class IOLocationResponseData(ResponseData[IOLocationData]):
    
    data: Optional[IOLocationData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> IOLocationData:
        data_length: int = int(raw_response[5])
        location_data: Dict[int, int] = {}
        data_bytes: bytes = raw_response[6:6 + data_length]
        for location, data in enumerate(data_bytes):
            location_data[location] = data
        return IOLocationData(location_data=location_data)




"""Opcode 167: Request Single Point Parameters"""

class SinglePointParameterRequestData(RequestData):

    opcode: int = 167

    point_type: int

    logical_number: int

    number_of_parameters: int

    starting_parameter_number: int

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BBBB',
            self.point_type,
            self.logical_number,
            self.number_of_parameters,
            self.starting_parameter_number
        )
        return data


class SinglePointParameterData(BaseModel):
        """
        Parameter request response data model.
        """

        point_type: int
        
        logical_number: int

        number_of_parameters: int

        starting_parameter_number: int

        values: List[TLPValue]
        """Parameter value objects."""



class SinglePointParameterResponseData(ResponseData[SinglePointParameterData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[SinglePointParameterData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> SinglePointParameterData:
        # Set timestamp of response receipt
        response_timestamp: datetime = datetime.now()
        
        # Parse response for TL, parameter count, and starting parameter
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        point_type: int = response_data[0]
        logical_number: int = response_data[1]
        number_of_parameters: int = response_data[2]
        starting_parameter_number: int = response_data[3]
        
        # Remaining data is parameter data
        data_bytes: bytes = response_data[4:]
        
        # Grab PointType class for getting parameter definitions
        point_type_def: Type[PointType] = PointTypes.get_point_type_by_number(point_type=point_type)

        # Unpack each parameter value according to its data type
        start_idx = 0
        values: List[TLPValue] = []
        for i in range(number_of_parameters):
            parameter_number: int = starting_parameter_number + i
            parameter_def: Parameter = point_type_def.get_parameter_by_number(parameter_number=parameter_number)
            end_idx: int = start_idx + parameter_def.data_type.structure.size
            value_tuple: tuple[Any] = struct.unpack(
                parameter_def.data_type.structure.format, 
                data_bytes[start_idx:end_idx]
            )
            if len(value_tuple) == 1:
                value: Any = value_tuple[0]
            else:
                value: Any = [val for val in value_tuple]
            values.append(
                TLPValue(
                    parameter=parameter_def,
                    point_type=point_type_def,
                    logical_number=logical_number,
                    value=value,
                    timestamp=response_timestamp
                )
            )
            start_idx: int = end_idx
        return SinglePointParameterData(
            point_type=point_type,
            logical_number=logical_number,
            number_of_parameters=number_of_parameters,
            starting_parameter_number=starting_parameter_number,
            values=values
        )




"""Opcode 180: Request Parameters"""

class ParameterRequestData(RequestData):

    opcode: int = 180

    tlps: List[TLPInstance]

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack('B', len(self.tlps))
        for tlp in self.tlps:
            data += struct.pack(
                'BBB',
                tlp.point_type.point_type_number,
                tlp.logical_number,
                tlp.parameter.parameter_number
            )
        return data



class ParameterData(BaseModel):
        """
        Parameter request response data model.
        """

        value_count: int
        """The number of parameters requested."""

        values: List[TLPValue]
        """Parameter value objects."""


class ParameterResponseData(ResponseData[ParameterData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[ParameterData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> ParameterData:
        # Set timestamp of response receipt
        response_timestamp: datetime = datetime.now()
        
        # Parse response for parameter count and value data
        data_length: int = int(raw_response[5])
        response_data = raw_response[6:6 + data_length]
        value_count: int = response_data[0]
        parameter_bytes: bytes = response_data[1:]
        
        # Unpack each parameter value according to its data type
        start_idx = 0
        values: List[TLPValue] = []
        for _ in range(value_count):
            # Grab TLP data from first 3 bytes
            tlp_data: bytes = parameter_bytes[start_idx:start_idx + 3]
            point_type, point_number, param_number = struct.unpack('BBB', tlp_data)
            point_type_def: Type[PointType] = PointTypes.get_point_type_by_number(point_type=point_type)
            parameter_def: Parameter = point_type_def.get_parameter_by_number(parameter_number=param_number)
            
            # Grab value data from remaining bytes, determined by data type
            param_data_start_idx: int = start_idx + 3
            end_idx: int = param_data_start_idx + parameter_def.data_type.structure.size
            value_tuple: tuple[Any] = struct.unpack(
                parameter_def.data_type.structure.format, 
                parameter_bytes[param_data_start_idx:end_idx]
            )
            if len(value_tuple) == 1:
                value: Any = value_tuple[0]
            else:
                value: Any = [val for val in value_tuple]
            values.append(
                TLPValue(
                    parameter=parameter_def,
                    point_type=point_type_def,
                    logical_number=point_number,
                    value=value,
                    timestamp=response_timestamp
                )
            )
            start_idx: int = end_idx
        return ParameterData(
            values=values,
            value_count=value_count
        )


"""Opcode 255: Error Indicator"""

class OpcodeError(BaseModel):
    """
    Opcode 255 Error Instance.
    """

    error_code: OpcodeErrorCode

    cause_byte_offset: int


class OpcodeErrorData(BaseModel):

        errors: List[OpcodeError]


class OpcodeErrorResponseData(ResponseData[OpcodeErrorData]):

    data: Optional[OpcodeErrorData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes) -> OpcodeErrorData:
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        errors: List[OpcodeError] = []
        for error_code, cause_byte_offset in zip(response_data[::2], response_data[1::2]):
            error_code_obj: OpcodeErrorCode = OpcodeErrorCodes.get_error_code(error_code)
            errors.append(OpcodeError(
                error_code=error_code_obj,
                cause_byte_offset=cause_byte_offset
            ))
        return OpcodeErrorData(errors=errors)

class MessageModels:

    _6 = MessageModel(request_data=SystemConfigRequestData, response_data=SystemConfigResponseData, opcode_desc='System Configuration')
    _7 = MessageModel(request_data=ReadClockRequestData, response_data=ReadClockResponseData, opcode_desc='Read Real-time Clock')
    _50 = MessageModel(request_data=IOLocationRequestData, response_data=IOLocationResponseData, opcode_desc='Request I/O Point Position')
    _167 = MessageModel(
        request_data=SinglePointParameterRequestData, 
        response_data=SinglePointParameterResponseData, 
        opcode_desc='Request Single Point Parameter(s)'
    )
    _180 = MessageModel(request_data=ParameterRequestData, response_data=ParameterResponseData, opcode_desc='Request Parameter(s)')
    _255 = MessageModel(request_data=RequestData, response_data=OpcodeErrorResponseData, opcode_desc='Error Indicator')

    @classmethod
    def get_model_by_opcode(cls, opcode: int) -> MessageModel:
        model: Optional[MessageModel] = None
        query_string = '_' + str(opcode)
        for k, v in cls.__dict__.items():
            if k == query_string:
                model = v
        if model is None:
            raise KeyError(f'No Opcode model found for opcode {opcode}.')
        else:
            return model