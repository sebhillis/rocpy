from abc import ABC, abstractmethod
from typing_extensions import Unpack
from pydantic import BaseModel, ConfigDict, Field, field_serializer, SerializationInfo, model_serializer, PlainSerializer
import struct
from typing import Annotated, Generic, TypeVar, Self, Dict
# from .opcodes import DeviceData, OpcodeData, RequestData, ResponseData, MessageModel, MessageModels
from loguru import logger
from base_model import AliasModel
from enums import *


class DeviceData(BaseModel):

    roc_address: Annotated[int, Field(serialization_alias='ROC Unit Address')]
    """ROC address for the target device."""
    
    roc_group: Annotated[int, Field(serialization_alias='ROC Group')]
    """ROC group for the target device."""
    
    host_address: Annotated[int, Field(serialization_alias='Host Address', default=1)]
    """Address of requesting device. Defaults to 1."""
    
    host_group: Annotated[int, Field(serialization_alias='Host Group', default=0)]
    """Group of requesting device. Defaults to 0."""

    def encode(self) -> bytes:
        return struct.pack(
            'BBBB',
            self.roc_address,
            self.roc_group,
            self.host_address,
            self.host_group
        )

    @classmethod
    def decode(cls, raw_response: bytes) -> 'DeviceData':
        device_bytes: bytes = raw_response[0:4]
        host_address, host_group, roc_address, roc_group = struct.unpack('BBBB', device_bytes)
        return DeviceData(
            roc_address=roc_address,
            roc_group=roc_group,
            host_address=host_address,
            host_group=host_group
        )

class CRC(AliasModel):
    """
    Cyclic Redundancy Check (CRC) model.

    Calculates CRC from input bytes and makes MSB and LSB available.
    """

    value: Annotated[int, Field(serialization_alias='Integer Value')]
    """Integer representation of CRC value."""

    @classmethod
    def decode(cls, crc_bytes: bytes) -> 'CRC':
        return CRC(value=int.from_bytes(crc_bytes, byteorder='little'))
    
    @classmethod
    def calculate(cls, source_data: bytes) -> 'CRC':
        crc = 0xFFFF
        for byte in source_data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc: int = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return CRC(value=crc)

    @property
    def lsb(self) -> int:
        """Least significant byte (LSB) of CRC."""
        return self.value & 0xFF
    
    @property
    def msb(self) -> int:
        """Most significant byte (MSB) of CRC."""
        return (self.value >> 8) & 0xFF   

    def encode(self) -> bytes:
        return struct.pack('BB', self.lsb, self.msb)   


class OpcodeModel(BaseModel, ABC):
    """Model defining a single specific Opcode."""

    model_config = ConfigDict(ignored_types=(TypeVar,))

    opcode: int = -1
    """Opcode integer identifier."""

    description: str = ''
    """Opcode description."""

    class OpcodeRequestData(BaseModel, ABC):
        """Opcode-specific request data."""

        @property
        @abstractmethod
        def opcode(self) -> int:
            pass

        @property
        @abstractmethod
        def description(self) -> str:
            pass

        @property
        def _opcode_encoded(self) -> bytes:
            """Opcode integer encoded to bytes."""
            return struct.pack('B', self.opcode)

        @property
        @abstractmethod
        def _data_encoded(self) -> bytes:
            """Opcode-specific data encoded to bytes. Must specify implementation based on unique Opcode-specific data."""
            return b''

        @property
        def _data_length(self) -> int:
            """Length of the encoded opcode-specific data, in bytes."""
            return len(self._data_encoded)

        @property
        def _data_length_encoded(self) -> bytes:
            """Length of the encoded opcode-specific data encoded to bytes."""
            return struct.pack('B', self._data_length)

        def encode(self) -> bytes:
            """Encode entire request to bytes."""
            return (self._opcode_encoded + self._data_length_encoded + self._data_encoded)


    T_Request = TypeVar('T_Request', bound='OpcodeModel.OpcodeRequestData')

    class OpcodeResponseData(BaseModel, ABC):
        """Opcode-specific response data."""

        @property
        @abstractmethod
        def opcode(self) -> int:
            pass

        @property
        @abstractmethod
        def description(self) -> str:
            pass

        @classmethod
        @abstractmethod
        def parse(cls, raw_response: bytes, request_data: 'OpcodeModel.T_Request') -> Self:
            """
            Parse a raw binary message into an OpcodeData object instance.

            Args:
                raw_response (bytes): The raw binary response message to parse.
                request_data (RequestData): The request data associated with the response.

            Returns:
                OpcodeData: OpcodeData object instance
            """
            pass



class Request(BaseModel):
    """
    Base request for all Opcodes.
    """
    
    device_data: DeviceData
    """Device data header information."""

    request_data: OpcodeModel.OpcodeRequestData
    """Opcode-specific request data."""

    @property
    def _data_encoded(self) -> bytes:
        """Packet formed from header and request-specific data."""
        packet_without_crc: bytes = self.device_data.encode() + self.request_data.encode()
        return packet_without_crc

    @property
    def _crc(self) -> CRC:
        """CRC for request, calculated from header and request-specific data."""
        return CRC.calculate(source_data=self._data_encoded)

    @property
    def _crc_encoded(self) -> bytes:
        """CRC for request encoded to bytes."""
        return self._crc.encode()

    def encode(self) -> bytes:
        """Full request packet with header, request data, and CRC."""
        return (self._data_encoded + self._crc_encoded)


class Response(AliasModel):

    raw_response: bytes = Field(exclude=True)
    """The raw binary response received from the ROC."""

    device_data: DeviceData = Field(serialization_alias='ROC Device Data')
    """The device data header of the response. Extracted from bytes 0 (0-index) through 3 per ROC Plus specification."""

    opcode: int = Field(serialization_alias='Opcode ID')
    """The Opcode identifier found in the response. Extracted from byte 4 (0-index) per ROC Plus specification."""

    data_length: Annotated[int, Field(serialization_alias='Opcode Data Length')]
    """The length of the opcode-specific data in bytes. Extracted from byte 5 (0-index) per ROC Plus specification."""

    opcode_data: Annotated[OpcodeModel.OpcodeResponseData, Field(serialization_alias='Opcode Data Payload')]
    """The opcode-specific data in the response. Extracted from bytes 6 (0-index) through (6 + data_length) per ROC Plus specification."""

    crc: Annotated[CRC, Field(serialization_alias='Cyclic Redundancy Check (CRC)')]
    """The CRC footer of the response. Extracted from the final (2) bytes of the response per ROC Plus specification."""

    @property
    def total_length(self) -> int:
        return len(self.raw_response)

    @classmethod
    def decode(cls, raw_response: bytes, request_data: OpcodeModel.OpcodeRequestData) -> 'Response':
        logger.debug('Decoding response message.')
        logger.debug('Decoding device data header.')
        device_data: DeviceData = DeviceData.decode(raw_response=raw_response)
        logger.debug('Device data header decoded successfully. Decoding opcode and data length header.')
        opcode: int = raw_response[4]
        data_length: int = raw_response[5]
        logger.debug('Header decoded successfully. Decoding Opcode data.')
        opcode_model: type[OpcodeModel] = opcode_models[opcode]
        opcode_data: OpcodeModel.OpcodeResponseData = opcode_model.OpcodeResponseData.parse(raw_response=raw_response, request_data=request_data)
        logger.debug('Opcode data decoded successfully. Decoding CRC.')
        crc: CRC = CRC.decode(crc_bytes=raw_response[-2:])
        logger.debug('Entire response decoded successfully. Constructing model instance.')
        response_obj = Response(
            raw_response=raw_response,
            device_data=device_data,
            opcode=opcode,
            data_length=data_length,
            opcode_data=opcode_data,
            crc=crc
        )
        logger.debug('Model instance created successfully. Returning instance.')
        return response_obj

    @field_serializer('opcode_data', when_used='always')
    def serialize_response_data(self, opcode_data: OpcodeModel.OpcodeResponseData, info: SerializationInfo):
        opcode_model: type[OpcodeModel] = opcode_models[self.opcode]
        response_data_model: type[OpcodeModel.OpcodeResponseData] = opcode_model.OpcodeResponseData
        response_data: OpcodeModel.OpcodeResponseData = response_data_model.model_validate(opcode_data)
        return response_data.model_dump(by_alias=True)
    

class OpcodeExchange(BaseModel):

    request: Request

    response: Response



class SystemConfigOpcode(OpcodeModel):

    opcode: int = 6

    description: str = 'Retrieve system configuration'


    class OpcodeRequestData(OpcodeModel.OpcodeRequestData):

        @property
        def opcode(self) -> int:
            return SystemConfigOpcode().opcode
        
        @property
        def description(self) -> str:
            return SystemConfigOpcode().description
        
        @property
        def _data_encoded(self) -> bytes:
            return b''
        
    
    class OpcodeResponseData(OpcodeModel.OpcodeResponseData):

        operating_mode: Annotated[
            ROCOperatingMode, 
            PlainSerializer(lambda x: x.serialized, return_type=dict, when_used='always'), 
            Field(serialization_alias='Operating Mode')
        ]
        """The system mode the unit is currently operating in."""

        comm_port: Annotated[int, Field(serialization_alias='Comm Port')]
        """Comm Port or Port Number that this request arrived on."""

        security_access_mode: Annotated[int, Field(serialization_alias='Security Access Mode')]
        """Security Access Mode for the port the request was received on."""

        compatibility_status: Annotated[
            LogicalCompatibilityStatus, 
            PlainSerializer(lambda x: x.serialized, return_type=dict, when_used='always'),
            Field(serialization_alias='Logical Compatibility Status')
        ]
        """Logical Compatibility Status (see Point Type 91, Logical 0, Parameter 50)."""

        opcode_revision: Annotated[
            OpcodeRevision, 
            PlainSerializer(lambda x: x.serialized, return_type=dict, when_used='always'),
            Field(serialization_alias='Opcode 6 Revision (Version 2.02)')
        ]
        """Opcode 6 Revision."""

        roc_subtype: Annotated[
            ROCSubType, 
            PlainSerializer(lambda x: x.serialized, return_type=dict, when_used='always'),
            Field(serialization_alias='ROC Subtype')
        ]
        """ROC Subtype."""

        roc_type: Annotated[
            ROCType, 
            PlainSerializer(lambda x: x.serialized, return_type=dict, when_used='always'),
            Field(serialization_alias='ROC Type')
        ]
        """Type of ROC."""

        point_type_counts: Annotated[Dict[int, int], Field(serialization_alias='Configured Point Types')]
        """Number of logical points for each point type, indexed by point type ID."""

        @property
        def opcode(self) -> int:
            return SystemConfigOpcode().opcode
        
        @property
        def description(self) -> str:
            return SystemConfigOpcode().description
        
        @classmethod
        def parse(
            cls, 
            raw_response: bytes, 
            request_data: 'SystemConfigOpcode.OpcodeRequestData'
        ) -> Self:
            (
                operating_mode, 
                comm_port, 
                security_access_mode, 
                compatibility_status, 
                opcode_revision, 
                roc_subtype 
            ) = struct.unpack(
                '<BhBBBB',
                raw_response[6:13]
            )
            roc_type: int = raw_response[24]
            point_type_counts: Dict[int, int] = {}
            point_type_bytes = raw_response[25:221]
            starting_point_type = 60
            for i, byte in enumerate(point_type_bytes):
                point_type: int = i + starting_point_type
                point_type_counts[point_type] = int(byte)
            return cls(
                operating_mode=ROCOperatingMode(operating_mode),
                comm_port=comm_port,
                security_access_mode=security_access_mode,
                compatibility_status=LogicalCompatibilityStatus(compatibility_status),
                opcode_revision=OpcodeRevision(opcode_revision),
                roc_subtype=ROCSubType(roc_subtype),
                roc_type=ROCType(roc_type),
                point_type_counts=point_type_counts
            )
        
opcode_models: Dict[int, type[OpcodeModel]] = {
    6: SystemConfigOpcode
}