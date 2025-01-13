from pydantic import BaseModel, field_validator, ValidationInfo, field_serializer, SerializationInfo, model_validator
from datetime import datetime
from typing import Type, Any, Optional, List, Dict, overload
from roc_data_types import ParameterDataTypes, ROCDataType
from tlp_models.parameter import Parameter
from tlp_models.point_type import PointType
from tlp_models.point_types import PointTypeNotFoundError, PointTypes

class TLPInstance(BaseModel):

    parameter: Parameter
    """Parameter definition for the TLP."""

    point_type: Type[PointType] = PointTypes.ANALOG_INPUTS
    """Point Type definition for the TLP."""

    logical_number: int
    """Logical number of the TLP."""

    tag_name: Optional[str] = None
    """Name of tag within ROC as derived from the I/O Configuration."""

    @overload
    def __init__(self, *, parameter: Parameter, point_type: Type[PointType], logical_number: int) -> None:
        ...

    @overload
    def __init__(self, *, parameter: Parameter, logical_number: int) -> None:
        ...

    def __init__(self, **data) -> None:
        super().__init__(**data)

    @field_validator('point_type', mode='before')
    @classmethod
    def validate_point_type(cls, v, info: ValidationInfo) -> Type[PointType]:
        if isinstance(v, type):
            if issubclass(v, PointType):
                return v
            else:
                raise ValueError('Value is not a subclass of PointType.')
        else:
            raise ValueError('Value is not a Type.')

    @field_validator('logical_number', mode='before')
    @classmethod
    def validate_logical_number(cls, v, info: ValidationInfo) -> int:
        if isinstance(v, int):
            if v >= 0 and v <= 255:
                return v
            else:
                raise ValueError('Invalid logical number value. Please provide a value between 0 and 255.')
        else:
            raise ValueError('Invalid logical number type. Please provide an integer between 0 and 255.')

    @field_serializer('point_type', when_used='always')
    def serialize_point_type(self, point_type: Type['PointType']) -> Dict:
        return {
            'point_type_name': point_type.point_type_desc,
            'point_type_number': point_type.point_type_number
        }
    
    @model_validator(mode='before')
    def extract_point_type(cls, values) -> Dict:
        if isinstance(values, dict):
            if 'point_type' not in values:
                parameter: Parameter = values['parameter']
                point_type_name: str = parameter.__class__.__qualname__.split('.')[0]
                point_type: PointType = getattr(PointTypes, point_type_name)
                values['point_type'] = point_type
            return values
        else:
            raise ValueError('Invalid input data.')

    @classmethod
    def from_integers(cls, point_type: int, logical_number: int, parameter: int) -> 'TLPInstance':
        try:
            point_type_obj: Type[PointType] = PointTypes.get_point_type_by_number(point_type)
            parameter_obj: Parameter = point_type_obj.get_parameter_by_number(parameter)
            return TLPInstance(
                parameter=parameter_obj,
                point_type=point_type_obj,
                logical_number=logical_number
            )
        except PointTypeNotFoundError:
            return TLPInstance.get_unknown_tlp(
                point_type=point_type, 
                logical_number=logical_number, 
                parameter=parameter
            )

    @classmethod
    def get_unknown_tlp(cls, point_type: int, logical_number: int, parameter: int) -> 'TLPInstance':
        
        class UNKNOWN_POINT_TYPE(PointType):
                point_type_number: int = point_type
                point_type_desc: str = 'Unknown Point Type'
            
        UNKNOWN_PARAMETER = Parameter(
            parameter_name='Unknown Parameter',
            parameter_desc='Unknown Parameter',
            parameter_number=parameter,
            access='Unknown',
            data_type=ParameterDataTypes.UNKNOWN,
            value_range=('')
        )

        return TLPInstance(
            parameter=UNKNOWN_PARAMETER, 
            point_type=UNKNOWN_POINT_TYPE, 
            logical_number=logical_number
        )

class TLPValue(TLPInstance):

    value: Any
    """Value of this TLP."""

    timestamp: datetime = datetime.now()
    """Timestamp of the current value."""

    bit_values: List[bool] = []
    """If data type is BIN, values for each bit within the binary value indexed by bit number."""

    @field_validator('value', mode='before')
    @classmethod
    def validate_value(cls, v, info: ValidationInfo) -> Any:
        param_def: Optional[Parameter] = info.data.get('parameter')
        if isinstance(param_def, Parameter):
            data_type: Type[Any] = param_def.data_type.py_type
            if data_type == str:
                if isinstance(v, bytes):
                    try:
                        v_str: str = v.decode('utf-8')
                        return v_str.strip()
                    except:
                        raise ValueError(f'Unable to parse value {v} to string.')
            elif isinstance(v, data_type):
                return v
            else:
                raise ValueError(f'Value was not of expected type {data_type}.')
        else:
            raise ValueError(f'Parameter definition of unexpected type: {type(param_def)}.')


    @model_validator(mode='before')
    def set_bit_values(cls, values) -> Dict:
        if isinstance(values, dict):
            parameter_def: Parameter | None = values.get('parameter')
            if parameter_def is None:
                raise ValueError('Parameter definition not provided.')
            elif isinstance(parameter_def, Parameter):
                data_type: ROCDataType = parameter_def.data_type
                if data_type == ParameterDataTypes.BIN:
                    raw_value: Any | None = values.get('value')
                    if isinstance(raw_value, int) and 0 <= raw_value <= 255:
                        bit_values: List[bool] = [(raw_value >> i) & 1 == 1 for i in range(8)] # Go from LSB to MSB so it matches the parameter spec
                        values['value'] = raw_value
                        values['bit_values'] = bit_values
                        return values
                    else:
                        return values
                else:
                    return values
            else:
                raise ValueError('Invalid Parameter definition provided.')
        else:
            raise ValueError('Input data must be valid dictionary.')
        

class TLPValues(BaseModel):
    """
    Collection of TLPValue objects for ease of serialization.
    """

    values: List[TLPValue]
    """List of TLP Values."""

    timestamp: datetime = datetime.now()
    """Timestamp of object creation. For streaming messages, indicates when all tag reads completed."""