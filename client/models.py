from ipaddress import IPv4Address
from typing import Optional, List, Dict, Type, overload
from collections import defaultdict
from enum import Enum
from datetime import datetime
from typing_extensions import Annotated
from pydantic import BaseModel, IPvAnyAddress, field_validator, ValidationInfo, model_serializer, PlainSerializer
from tlp_models.point_type import PointType
from tlp_models.point_types import PointTypes
from tlp_models.parameter import Parameter
from tlp_models.tlp import TLPInstance
from client.exceptions import *
from enums import HistoryArchiveType, HistoryAveragingRateType

class ROCClientDefinition(BaseModel):
    """
    Definition data for ROC Client connection.
    """

    ip: IPvAnyAddress
    """IP Address of ROC TCP endpoint."""

    port: int
    """Port number of ROC TCP endpoint."""

    roc_address: int
    """ROC Unit Address."""

    roc_group: int
    """ROC Group."""

    host_address: int
    """Host address."""

    host_group: int
    """Host group."""

    @field_validator('ip', mode='before')
    @classmethod
    def validate_ip(cls, v, info: ValidationInfo) -> IPv4Address:
        if isinstance(v, str):
            return IPv4Address(v)
        elif isinstance(v, IPv4Address):
            return v
        else:
            raise ValueError()

    @field_validator('port', mode='before')
    @classmethod
    def validate_port(cls, v, info: ValidationInfo) -> int:
        if isinstance(v, int):
            if 0 <= v <= 65535:
                return v
            else:
                raise ValueError('Port out of range.')
        else:
            raise ValueError('Port must be integer value.')
    
    @field_validator('roc_address', 'host_address', 'roc_group', 'host_group', mode='before')
    @classmethod
    def validate_roc_address(cls, v, info: ValidationInfo) -> int:
        if isinstance(v, int):
            if 0 <= v <= 255:
                return v
            else:
                raise ValueError('Address/group out of range.')
        else:
            raise ValueError('Address/group must be integer.')


class IOPointDefinition(BaseModel):
    """
    Single I/O point definition.
    """

    physical_location: int
    """Physical location from 0 -> maximum # of I/O points in rack."""

    logical_number: Optional[int] = None
    """Logical number from 0 -> maximum # of points on I/O card."""

    point_type: Optional[int] = None
    """Point type identifier."""

    point_tag_id: Optional[str] = None
    """Point tag ID; tag name"""

    @property
    def defined(self) -> bool:
        if self.point_type is not None:
            if self.point_type > 0:
                return True
            else:
                return False
        else:
            raise ValueError('Point Type not defined, cannot determine enabled status.')

    def get_point_type_object(self) -> Type[PointType]:
        """
        Get Point Type model instance for this I/O point type.

        Returns:
            PointType: Point type object describing the point type in full.
        """
        try:
            if self.point_type:
                return PointTypes.get_point_type_by_number(self.point_type)
            else:
                raise ROCDataError('Point type not defined.')
        except KeyError as e:
            raise ROCDataError('Invalid Point Type ID.') from e

    def get_point_tag_id_param(self) -> Parameter:
        point_type_obj: Type[PointType] = self.get_point_type_object()
        try:

            return point_type_obj.get_parameter_by_name('POINT_TAG_ID')
        except KeyError as e:
            raise ROCDataError('Invalid Parameter Name.') from e

class IODefinition:
    """
    Full I/O definition for all points in device.
    """

    def __init__(self):
        self._logical_numbers_uploaded: bool = False
        """Flag to indicate if I/O Logical Numbers have been uploaded."""

        self._point_types_uploaded: bool = False
        """Flag to indicate if I/O Point Types have been uploaded."""

        self._point_tag_ids_uploaded: bool = False
        """Flag to indicate if I/O Point Tag IDs have been uploaded."""

        self._defined: bool = False
        """Flag to indicate if all parameters have been uploaded."""

        self.io_map: Dict[int, IOPointDefinition] = {}
        """Map of I/O Point Definitions indexed by physical location."""
    

    def as_dict(self) -> Dict[str, Dict[int, Dict]]:
        self_dict = {'io_definition': {}}
        for index, segment in self.io_map.items():
            self_dict['io_definition'][index] = segment.model_dump()
        return self_dict


    def add_point_definition(self, physical_location: int, point_definition: IOPointDefinition) -> None:
        """
        Add a single I/O Point Definition to the I/O Map.

        Args:
            physical_location (int): Physical I/O point location.
            point_definition (IOPointDefinition): I/O Point Definition object.
        """
        if isinstance(point_definition, IOPointDefinition):
            self.io_map[physical_location] = point_definition
            return
        else:
            raise ROCDataError('Invalid point definition argument. Please provide IOPointDefinition instance.')



    @overload
    def get_point_definition(self, tlp_instance: TLPInstance) -> IOPointDefinition:
        ...
    
    @overload
    def get_point_definition(self, physical_location: int) -> IOPointDefinition:
        ...

    def get_point_definition(self, *args, **kwargs) -> IOPointDefinition:
        """
        Get single I/O Point Definition object for the given physical location.

        Args:
            physical_location (int): Physical I/O point location.

        Returns:
            IOPointDefinition: I/O Point Definition object.
        """
        if len(args) > 0:
            if isinstance(args[0], TLPInstance):
                logical_number: int = args[0].logical_number
            elif isinstance(args[0], int):
                logical_number: int = args[0]
            else:
                raise ROCDataError('Invalid argument to retrieve I/O Point Definition.')
        else:
            if 'tlp_instance' in kwargs:
                tlp_instance: TLPInstance = kwargs['tlp_instance']
                logical_number: int = tlp_instance.logical_number
            elif 'physical_location' in kwargs:
                logical_number: int = kwargs['physical_location']
            else:
                raise ROCDataError('Invalid argument to retrieve I/O Point Definition.')
        
        try:
            return self.io_map[logical_number]
        except KeyError as e:
            raise ROCDataError(f'No I/O defined for physical location {logical_number}')



    def get_all_defined_points(self) -> Dict[int, IOPointDefinition]:
        """
        Get all I/O points with a valid definition.

        Returns:
            Dict[int, IOPointDefinition]: All fully defined I/O points, indexed by physical location.
        """
        io_point_defs: Dict[int, IOPointDefinition] = {}
        for physical_location, point_definition in self.io_map.items():
            if point_definition.defined:
                io_point_defs[physical_location] = point_definition
        return io_point_defs


    @overload
    def get_points_for_point_type(self, point_type: Type[PointType]) -> List[IOPointDefinition]:
        """
        Get all I/O Point Definitions with the given Point Type.

        Args:
            point_type (Type[PointType]): Point Type class.

        Returns:
            List[IOPointDefinition]: All I/O Point Definition objects with matching Point Type.
        """
        ...

    @overload
    def get_points_for_point_type(self, point_type_number: int) -> List[IOPointDefinition]:
        """
        Get all I/O Point Definitions with the given Point Type.

        Args:
            point_type (int): Point Type identifier.

        Returns:
            List[IOPointDefinition]: All I/O Point Definition objects with matching Point Type.
        """
        ...


    def get_points_for_point_type(self, *args, **kwargs) -> List[IOPointDefinition]:
        
        if len(args) > 0:
            if isinstance(args[0], PointType):
                point_type_number: int = args[0].point_type_number
            elif isinstance(args[0], int):
                point_type_number: int = args[0]
            else:
                raise ROCDataError('Invalid arguments to retrieve points by point type.')
        elif 'point_type_number' in kwargs:
            point_type_number: int = kwargs['point_type_number']
        elif 'point_type' in kwargs:
            point_type: PointType = kwargs['point_type']
            point_type_number: int = point_type.point_type_number
        else:
            raise ROCDataError('Invalid arguments to retrieve points by point type.')

        return self.points_by_point_type[point_type_number]

    @property
    def points_by_point_type(self) -> Dict[int, List[IOPointDefinition]]:
        points_by_point_type = defaultdict(list)
        for point_def in self.io_map.values():
            points_by_point_type[point_def.point_type].append(point_def)
        return points_by_point_type


class OpcodeTableEntryDefinition(BaseModel):

    table_index: int
    """Index of the Configurable Opcode table."""

    data_index: int
    """Index of the individual data entry."""

    tlp_definition: TLPInstance
    """TLP definition for the TLP to which the data entry is mapped."""


class ConfigurableOpcodeTableDefinition(BaseModel):

    table_index: int
    """Index of the Configurable Opcode Table."""

    data_entry_definitions: List[OpcodeTableEntryDefinition]
    """List of data entry definition objects."""


class ConfigurableOpcodeTablesDefinition:

    def __init__(self):

        self._defined: bool = False
        """Flag to indicate if all configurable opcode table definitions have been uploaded."""

        self.configurable_opcode_table_map: Dict[int, ConfigurableOpcodeTableDefinition] = {}
        """Map of Configurable Opcode Table Definitions indexed by table number."""

    def as_dict(self) -> Dict[str, Dict[int, Dict]]:
        self_dict = {'user_opcode_table_definition': {}}
        for index, segment in self.configurable_opcode_table_map.items():
            self_dict['user_opcode_table_definition'][index] = segment.model_dump()
        return self_dict
    

class HistorySegmentPointConfiguration(BaseModel):

    history_segment: int
    """The history segment this point belongs to."""

    history_point_number: int
    """ID for the history point."""

    point_tag_id: str
    """Same value as the Point Tag of the Point Type the History Log Point resides in."""

    parameter_description: str
    """User supplied text string used to identify the parameter being logged in the history point."""

    history_log_point: TLPInstance | None
    """TLPInstance object pointing to the value which is to be archived by history."""

    archive_type: Annotated[HistoryArchiveType, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """Defines how the system archives a data point to history."""

    averaging_rate_type: Annotated[HistoryAveragingRateType, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """The rate of accumulation or averaging technique."""


    @field_validator('archive_type', mode='before')
    @classmethod
    def validate_archive_type(cls, v, info: ValidationInfo) -> HistoryArchiveType:
        if isinstance(v, HistoryArchiveType):
            return v
        elif isinstance(v, int):
            return HistoryArchiveType(v)
        else:
            raise ValueError('Expected integer or ArchiveType enum for archive type.')
        
    @field_validator('averaging_rate_type', mode='before')
    @classmethod
    def validate_averaging_rate_type(cls, v, info: ValidationInfo) -> HistoryAveragingRateType:
        if isinstance(v, HistoryAveragingRateType):
            return v
        elif isinstance(v, int):
            return HistoryAveragingRateType(v)
        else:
            raise ValueError('Expected integer or AveragingRateType enum for averaging/rate type.')



class HistorySegmentConfiguration(BaseModel):

    segment_number: int
    """ID of the history segment."""

    segment_description: str
    """Identifies what the segment of history is used for."""

    segment_size: int
    """Specifies how many history points are in the history segment."""

    max_segment_size: int
    """Maximum number of history points that can be configured for segment."""

    periodic_entries: int
    """Number of periodic entries per history point in the history segment."""

    daily_entries: int
    """Number of daily entries per history point in the history segment."""

    periodic_index: int
    """Location in each history point for the segment where the next periodic entry will be saved."""

    daily_index: int
    """Location in each history point for the segment where the next daily entry will be saved."""

    periodic_sample_rate: int
    """Number of minute intervals that pass before an entry is made in the periodic history."""

    contract_hour: int
    """Hour that indicates the beginning of a new day."""

    on_off_switch: bool
    """Switch that control hsitory logging for the history segment. Logging is suspended while the switch is off."""

    free_space: int
    """
    Specifies the number of history entries that are unaccounted for and may be added to history points in various segments.
        This applies to all history segments.
    """

    number_of_configured_points: int
    """Number of history points that are configured in the segment."""

    user_weighting_tlp: TLPInstance | None
    """The parameter of the value to use as the weight when using 'User Weighted Averaging'."""

    point_configurations: List[HistorySegmentPointConfiguration] = []
    """List of History Segment Point Configuration objects defining individual points."""


class HistoryDefinition:

    def __init__(self):

        self._defined: bool = False
        """Flag to indicate if all history segment/point definitions have been uploaded."""

        self.history_configuration_map: Dict[int, HistorySegmentConfiguration] = {}
        """Map of History Segment Configurations indexed by history segment number."""

    def as_dict(self) -> Dict[str, Dict[int, Dict]]:
        self_dict: dict[str, dict[int, dict]] = {'history_definition': {}}
        for index, segment in self.history_configuration_map.items():
            self_dict['history_definition'][index] = segment.model_dump()
        return self_dict
    
    def get_point_by_tlp(self, tlp: TLPInstance) -> HistorySegmentPointConfiguration:
        for segment_index, segment_config in self.history_configuration_map.items():
            for point_config in segment_config.point_configurations:
                point_tlp: TLPInstance | None = point_config.history_log_point
                if point_tlp:
                    if (
                        tlp.parameter, 
                        tlp.point_type.point_type_number, 
                        tlp.logical_number
                    ) == (
                        point_tlp.parameter,
                        point_tlp.point_type.point_type_number,
                        point_tlp.logical_number
                    ):
                        return point_config
        raise KeyError('No history point found.')
    
    def get_tlp_by_point(self, history_segment: int, point_number: int) -> TLPInstance:
        segment_config: HistorySegmentConfiguration = self.history_configuration_map[history_segment]
        for point_config in segment_config.point_configurations:
            if point_config.history_point_number == point_number:
                tlp: TLPInstance | None = point_config.history_log_point
                if tlp:
                    return tlp
        raise KeyError('No TLP found.')
    

class HistoryPointData(BaseModel):

    history_segment: int

    point_number: int

    timestamp: datetime

    value: float


class HistoryData(BaseModel):

    values: list[HistoryPointData]



class MeterConfig(BaseModel):

    meter_number: int

    station_number: int
    
    point_tag_id: str

    point_description: str


class StationConfig(BaseModel):

    point_tag_id: str

    calculation_standard: int

    calculation_edition: int

    history_segment: int

    meter_configs: list[MeterConfig] = []

    def get_meter_by_number(self, meter_number: int) -> MeterConfig:
        for meter_config in self.meter_configs:
            if meter_config.meter_number == meter_number:
                return meter_config
        raise ValueError(f'No meter found for meter number {meter_number}.')