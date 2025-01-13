from typing import Optional, List
from roc_data_types import ROCDataType
from pydantic import BaseModel, field_validator, ValidationInfo

class Parameter(BaseModel):

    parameter_number: int
    """Parameter # for parameter within the point type."""

    parameter_name: str
    """Simple name of parameter."""

    parameter_desc: str
    """Parameter description."""

    data_type: ROCDataType
    """ROC Data Type. Defines byte length, unpacking format string, and py type."""

    access: Optional[str] = None
    """Read/write access for the parameter."""

    value_range: tuple[str | int | float] | str
    """Valid range of values for parameter."""

    @field_validator('data_type')
    def validate_data_type(cls, v, info: ValidationInfo) -> ROCDataType:
        if not isinstance(v, ROCDataType):
            raise TypeError(f'Invalid input type {type(v)}.')
        else:
            return v
        
    def to_json(self, **kwargs) -> str:
        kwargs['indent'] = 4
        return self.model_dump_json(**kwargs)
        

        
class BitDescriptor(BaseModel):
    """
    Description of bit constituent of BIN TLP.

    The TLP spec document lists "6.0", "6.1", etc. as separate parameters, but only "6" can actually
        be requested. Therefore, the parameter name/description is extracted/documented here in the
        BitDescriptor object for introspection. This can be used along with the "bit_values" field of
        the TLP object to correlate the response value (an 8-bit integer) with the bit-level significance.
    """

    bit_number: int
    """The bit number within the binary value. 0=LSB, 7=MSB."""

    bit_name: str
    """The name of the bit-level parameter."""

    bit_desc: str
    """The description of the bit-level parameter."""


class ParameterBinary(Parameter):
    """
    Special Parameter type for BIN values that includes bit-level descriptor objects.
    """

    bits: List[BitDescriptor]
    """BitDescriptor object for each bit, indexed by bit number (bits[0] is the BitDescriptor for bit 0 (LSB))."""