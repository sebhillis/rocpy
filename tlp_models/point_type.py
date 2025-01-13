from pydantic import model_serializer
from tlp_models.parameter import Parameter
from enum import Enum
from typing import Optional, Type, ClassVar
from abc import ABC, abstractmethod

class ParameterNotFoundError(KeyError):
    pass

class PointType(ABC):

    point_type_number: int = -1
    """Point Type identifier."""

    point_type_desc: str = 'NOT IMPLEMENTED'
    """Point Type friendly description."""

    Parameters: ClassVar[Type]

    @classmethod
    def get_all_parameters(cls) -> list[Parameter]:
        """Get all TLPParameter objects as a list."""
        return [v for v in cls.Parameters.__dict__.values() if isinstance(v, Parameter)]


    @classmethod
    def get_parameter_by_number(cls, parameter_number: int) -> Parameter:
        parameter: Optional[Parameter] = None
        for v in cls.Parameters.__dict__.values():
            if isinstance(v, Parameter):
                if v.parameter_number == parameter_number:
                    parameter = v
                    return parameter
        if parameter is None:
            raise ParameterNotFoundError(f'No parameter found for parameter number {parameter_number}.')
        

    @classmethod
    def get_parameter_by_name(cls, parameter_name: str) -> Parameter:
        parameter: Optional[Parameter] = None
        for k, v in cls.Parameters.__dict__.items():
            if isinstance(v, Parameter):
                if k.lower() == parameter_name.lower():
                    parameter = v
                    return parameter
        if parameter is None:
            raise ParameterNotFoundError(f'No parameter found for name {parameter_name}.')