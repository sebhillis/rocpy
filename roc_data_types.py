from pydantic import BaseModel, field_serializer, SerializationInfo, ConfigDict, Field
from typing import Type, Dict
import struct


class ROCDataType(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True)

    data_type_name: str
    """Name of the data type from the ROC Plus specification."""

    format_string: str = Field(exclude=True)
    """Format string used to de-serialize parameters of this type."""

    py_type: Type
    """Corresponding Python base type for the ROC Data Type."""


    @property
    def structure(self) -> struct.Struct:
        return struct.Struct(f'<{self.format_string}')

    @field_serializer('py_type', when_used='always')
    def serialize_py_type(self, py_type: Type, info: SerializationInfo) -> str:
        return str(py_type.__name__)
    
    def to_json(self, **kwargs) -> str:
        kwargs['indent'] = 4
        return self.model_dump_json(**kwargs)

class ParameterDataTypes:
    BIN = ROCDataType(data_type_name='BIN', format_string='B', py_type=int)
    AC = ROCDataType(data_type_name='AC', format_string='10s', py_type=str)
    AC3 = ROCDataType(data_type_name='AC3', format_string='3s', py_type=str)
    AC7 = ROCDataType(data_type_name='AC7', format_string='7s', py_type=str)
    AC10 = ROCDataType(data_type_name='AC10', format_string='10s', py_type=str)
    AC12 = ROCDataType(data_type_name='AC12', format_string='12s', py_type=str)
    AC20 = ROCDataType(data_type_name='AC20', format_string='20s', py_type=str)
    AC30 = ROCDataType(data_type_name='AC30', format_string='30s', py_type=str)
    AC40 = ROCDataType(data_type_name='AC40', format_string='40s', py_type=str)
    INT8 = ROCDataType(data_type_name='INT8', format_string='b', py_type=int)
    INT16 = ROCDataType(data_type_name='INT16', format_string='h', py_type=int)
    INT32 = ROCDataType(data_type_name='INT32', format_string='i', py_type=int)
    UINT8 = ROCDataType(data_type_name='UINT8', format_string='B', py_type=int)
    UINT16 = ROCDataType(data_type_name='UINT16', format_string='H', py_type=int)
    UINT32 = ROCDataType(data_type_name='UINT32', format_string='I', py_type=int)
    FL = ROCDataType(data_type_name='FLOAT', format_string='f', py_type=float)
    FLOAT: ROCDataType = FL
    DBL = ROCDataType(data_type_name='DOUBLE', format_string='d', py_type=float)
    TLP = ROCDataType(data_type_name='TLP', format_string='BBB', py_type=list)
    TIME = ROCDataType(data_type_name='TIME', format_string='I', py_type=int)
    HOURMINUTE = ROCDataType(data_type_name='HOURMINUTE', format_string='H', py_type=int)
    UNKNOWN = ROCDataType(data_type_name='UNKNOWN', format_string='', py_type=bytes)