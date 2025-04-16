from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict, Field, field_serializer, SerializationInfo, model_serializer
import struct
from typing import Annotated, Generic, TypeVar
# from .opcodes import DeviceData, OpcodeData, RequestData, ResponseData, MessageModel, MessageModels
from loguru import logger
from base_model import AliasModel


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


class OpcodeRequestData(BaseModel, ABC):
    """
    Opcode-specific request data.
    """

    opcode: int
    """Opcode integer identifier."""

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



class Request(BaseModel):
    """
    Base request for all Opcodes.
    """
    
    device_data: DeviceData
    """Device data header information."""

    request_data: OpcodeRequestData
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





T = TypeVar('T', bound=OpcodeRequestData)

class OpcodeResponseData(BaseModel, ABC):

    @classmethod
    @abstractmethod
    def parse(cls, raw_response: bytes, request_data: OpcodeRequestData) -> 'OpcodeResponseData':
        """
        Parse a raw binary message into an OpcodeData object instance.

        Args:
            raw_response (bytes): The raw binary response message to parse.
            request_data (RequestData): The request data associated with the response.

        Returns:
            OpcodeData: OpcodeData object instance
        """
        pass

class Response(AliasModel, Generic[T]):

    raw_response: bytes = Field(exclude=True)
    """The raw binary response received from the ROC."""

    device_data: DeviceData = Field(serialization_alias='ROC Device Data')
    """The device data header of the response. Extracted from bytes 0 (0-index) through 3 per ROC Plus specification."""

    opcode: int = Field(serialization_alias='Opcode ID')
    """The Opcode identifier found in the response. Extracted from byte 4 (0-index) per ROC Plus specification."""

    data_length: Annotated[int, Field(serialization_alias='Opcode Data Length')]
    """The length of the opcode-specific data in bytes. Extracted from byte 5 (0-index) per ROC Plus specification."""

    opcode_data: Annotated[T, Field(serialization_alias='Opcode Data Payload')]
    """The opcode-specific data in the response. Extracted from bytes 6 (0-index) through (6 + data_length) per ROC Plus specification."""

    crc: Annotated[CRC, Field(serialization_alias='Cyclic Redundancy Check (CRC)')]
    """The CRC footer of the response. Extracted from the final (2) bytes of the response per ROC Plus specification."""

    @property
    def total_length(self) -> int:
        return len(self.raw_response)

    @classmethod
    def decode(cls, raw_response: bytes, request_data: OpcodeRequestData) -> 'Response':
        logger.debug('Decoding response message.')
        logger.debug('Decoding device data header.')
        device_data: DeviceData = DeviceData.decode(raw_response=raw_response)
        logger.debug('Device data header decoded successfully. Decoding opcode and data length header.')
        opcode: int = raw_response[4]
        data_length: int = raw_response[5]
        logger.debug('Header decoded successfully. Decoding Opcode data.')
        opcode_model: MessageModel = MessageModels.get_model_by_opcode(opcode=opcode)
        opcode_data: OpcodeResponseData = opcode_model.response_data.parse(raw_response=raw_response, request_data=request_data)
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
    def serialize_response_data(self, opcode_data: OpcodeResponseData, info: SerializationInfo):
        opcode_model: MessageModel = MessageModels.get_model_by_opcode(opcode=self.opcode)
        response_data_model = opcode_model.response_data
        response_data = response_data_model.model_validate(opcode_data)
        return response_data.model_dump(by_alias=True)
    

class OpcodeModel(BaseModel):
    """Model defining a single specific Opcode."""

    opcode: int
    """Opcode integer identifier."""

    description: str
    """Opcode description."""

    class OpcodeRequestData(BaseModel, ABC):
        """Opcode-specific request data."""

        opcode: int
        """Opcode integer identifier."""

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


    class OpcodeResponseData(BaseModel, ABC):
        """Opcode-specific response data."""

        @classmethod
        @abstractmethod
        def parse(cls, raw_response: bytes, request_data: OpcodeRequestData) -> 'OpcodeResponseData':
            """
            Parse a raw binary message into an OpcodeData object instance.

            Args:
                raw_response (bytes): The raw binary response message to parse.
                request_data (RequestData): The request data associated with the response.

            Returns:
                OpcodeData: OpcodeData object instance
            """
            pass