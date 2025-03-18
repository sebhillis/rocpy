from abc import ABC
from pydantic import BaseModel, field_serializer, SerializationInfo
import struct
from typing import Generic, TypeVar
from .opcodes import DeviceData, RequestData, ResponseData, MessageModel, MessageModels


class CRC(BaseModel):
    """
    Cyclic Redundancy Check (CRC) model.

    Calculates CRC from input bytes and makes MSB and LSB available.
    """

    data: bytes
    """Input data for which CRC needs to be generated."""

    @property
    def crc_value(self) -> int:
        """Raw value of CRC."""
        crc = 0xFFFF
        for byte in self.data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc
    
    @property
    def lsb(self) -> int:
        """Least significant byte (LSB) of CRC."""
        return self.crc_value & 0xFF
    
    @property
    def msb(self) -> int:
        """Most significant byte (MSB) of CRC."""
        return (self.crc_value >> 8) & 0xFF       


class Request(BaseModel, ABC):
    """
    Base request for all Opcodes.
    """
    
    device_data: DeviceData

    request_data: RequestData


    @property
    def _packet_without_crc(self) -> bytes:
        """Packet formed from header and request-specific data."""
        packet_without_crc: bytes = self.device_data.to_binary_request() + self.request_data.to_binary()
        return packet_without_crc

    @property
    def crc(self) -> CRC:
        """CRC for request."""
        return CRC(data=self._packet_without_crc)

    def to_binary(self) -> bytes:
        """Full request packet with header, request data, and CRC."""
        full_packet = self._packet_without_crc + struct.pack('BB', self.crc.lsb, self.crc.msb)
        return full_packet

T = TypeVar('T', bound=ResponseData)

class Response(BaseModel, Generic[T]):

    device_data: DeviceData

    response_data: T

    @classmethod
    def from_binary(cls, raw_response: bytes, request_data: RequestData) -> 'Response':
        device_data: DeviceData = DeviceData.response_from_binary(raw_response=raw_response)
        opcode: int = int(raw_response[4])
        opcode_model: MessageModel = MessageModels.get_model_by_opcode(opcode=opcode)
        response_data: ResponseData = opcode_model.response_data.from_binary(raw_response=raw_response, request_data=request_data)
        return Response(device_data=device_data, response_data=response_data)
    
    @field_serializer('response_data', when_used='always')
    def serialize_response_data(self, response_data: ResponseData, info: SerializationInfo):
        opcode_model: MessageModel = MessageModels.get_model_by_opcode(opcode=response_data.opcode)
        response_data_model = opcode_model.response_data
        response_data = response_data_model.model_validate(response_data)
        return response_data.model_dump()