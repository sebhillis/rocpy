import opcode
from typing import Type, List, Optional, Dict, Any, TypeVar, Generic, overload, Union
import struct
from datetime import datetime
from urllib import request
from numpy import number
from pydantic import BaseModel, PlainSerializer, Field, RootModel, model_validator
from enum import Enum
from typing_extensions import Annotated, Self
from abc import ABC, abstractmethod
from opcode_models.error_codes import OpcodeErrorCodes, OpcodeErrorCode
from roc_data_types import ROCDataType
from tlp_models.tlp import TLPInstance, TLPValue
from tlp_models.point_type import PointType
from tlp_models.point_types import PointTypes
from tlp_models.parameter import Parameter
from enums import (
    HistoryArchiveType,
    HistoryInformationRequestCommand,
    ROCOperatingMode,
    ROCSubType,
    ROCType,
    OpcodeRevision,
    LogicalCompatibilityStatus,
    HistoryType,
    TransactionDataTypeDict,
    TransactionHistoryRequestCommand
)
from alarm_models import AlarmTypes
from event_models import EventTypes

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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> T:
        pass

    @classmethod
    def from_binary(cls, raw_response: bytes, request_data: RequestData) -> 'ResponseData':
        opcode: int = cls.opcode_from_binary(raw_response=raw_response)
        data_length: int = cls.data_length_from_binary(raw_response=raw_response)
        data: Optional[T] = None
        if data_length > 0:
            data = cls.data_from_binary(raw_response=raw_response, request_data=request_data)
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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> SystemConfigData:
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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> ReadClockData:
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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> OpcodeTableData:
        return super().data_from_binary(raw_response=raw_response, request_data=request_data)



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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> IOLocationData:
        data_length: int = int(raw_response[5])
        location_data: Dict[int, int] = {}
        data_bytes: bytes = raw_response[6:6 + data_length]
        for location, data in enumerate(data_bytes):
            location_data[location] = data
        return IOLocationData(location_data=location_data)





"""Opcode 105: Request Today's and Yesterday's Min/Max Values"""

class TodayYestMinMaxRequestData(RequestData):

    opcode: int = 105

    history_segment: int

    history_point: int

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BB',
            self.history_segment,
            self.history_point
        )
        return data

class TodayYestMinMaxData(BaseModel):

    history_segment: int
    """History Segment (0-10)."""

    history_point: int
    """History point number."""

    history_archive_method: Annotated[
        HistoryArchiveType, 
        PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, 
                        return_type=dict, 
                        when_used='always'
        )
    ]
    """Historical archival method type."""

    history_point_tlp: TLPInstance
    """TLP definition for history point."""

    current_value: TLPValue
    """Current value of history point TLP."""

    min_value_today: TLPValue
    """Minimum value since contract hour."""

    max_value_today: TLPValue
    """Maximum value since contract hour."""

    min_value_yesterday: TLPValue
    """Minimum value yesterday."""

    max_value_yesterday: TLPValue
    """Maximum value yesterday."""

    last_period_value: TLPValue
    """Value during last completed period."""


class TodayYestMinMaxResponseData(ResponseData[TodayYestMinMaxData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[TodayYestMinMaxData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> TodayYestMinMaxData:
        
        def time_tuple_to_datetime(time_tuple: tuple[int, int, int, int, int]) -> datetime:
            return datetime(
                year=datetime.now().year,
                month=time_tuple[4],
                day=time_tuple[3],
                hour=time_tuple[2],
                minute=time_tuple[1],
                second=time_tuple[0]
            )
        
        # Unpack data
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        history_segment: int = response_data[0]
        history_point: int = response_data[1]
        history_archive_method: int = response_data[2]
        point_type: int = response_data[3]
        logical_number: int = response_data[4]
        parameter: int = response_data[5]
        current_value: float = struct.unpack('<f', response_data[6:10])[0]
        min_today: float = struct.unpack('<f', response_data[10:14])[0]
        max_today: float = struct.unpack('<f', response_data[14:18])[0]
        min_today_time_tuple: tuple[int, int, int, int, int] = struct.unpack('BBBBB', response_data[18:23])
        max_today_time_tuple: tuple[int, int, int, int, int] = struct.unpack('BBBBB', response_data[23:28])
        min_yesterday: float = struct.unpack('<f', response_data[28:32])[0]
        max_yesterday: float = struct.unpack('<f', response_data[32:36])[0]
        min_yest_time_tuple: tuple[int, int, int, int, int] = struct.unpack('BBBBB', response_data[36:41])
        max_yest_time_tuple: tuple[int, int, int, int, int] = struct.unpack('BBBBB', response_data[41:46])
        last_value: float = struct.unpack('<f', response_data[46:50])[0]
        
        # Convert some of the values into tidier objects
        history_tlp: TLPInstance = TLPInstance.from_integers(
            point_type=point_type, 
            logical_number=logical_number, 
            parameter=parameter
        )
        min_today_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=min_today,
            timestamp=time_tuple_to_datetime(min_today_time_tuple)
        )
        max_today_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=max_today,
            timestamp=time_tuple_to_datetime(max_today_time_tuple)
        )
        min_yesterday_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=min_yesterday,
            timestamp=time_tuple_to_datetime(min_yest_time_tuple)
        )
        max_yesterday_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=max_yesterday,
            timestamp=time_tuple_to_datetime(max_yest_time_tuple)
        )
        current_value_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=current_value
        )
        last_period_value_obj: TLPValue = TLPValue.from_tlp_instance(
            tlp=history_tlp,
            value=last_value
        )

        return TodayYestMinMaxData(
            history_segment=history_segment,
            history_point=history_point,
            history_archive_method=HistoryArchiveType(history_archive_method),
            history_point_tlp=history_tlp,
            current_value=current_value_obj,
            min_value_today=min_today_obj,
            max_value_today=max_today_obj,
            min_value_yesterday=min_yesterday_obj,
            max_value_yesterday=max_yesterday_obj,
            last_period_value=last_period_value_obj
        )




"""Opcode 108: Request History Tag and Periodic Index"""

class HistoryTagPeriodIndexRequestData(RequestData):

    opcode: int = 108

    history_segment: int

    history_points: List[int]

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BB',
            self.history_segment,
            len(self.history_points)
        )
        for point in self.history_points:
            data += struct.pack('B', point)
        return data


class HistoryTagPeriodIndexData(BaseModel):

    history_segment: int
    """History Segment (0-10)."""

    number_of_history_points: int
    """Number of history points defined."""

    periodic_index: int
    """Periodic index, common to all history points in segment."""

    tag_names: Dict[int, str]
    """Tag names for each of the defined history points, indexed by point number."""


class HistoryTagPeriodIndexResponseData(ResponseData[HistoryTagPeriodIndexData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[HistoryTagPeriodIndexData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> HistoryTagPeriodIndexData:
        
        # Unpack data
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        history_segment: int = response_data[0]
        number_of_points: int = response_data[1]
        periodic_index: int = struct.unpack('<h', response_data[2:4])[0]

        # Extract point data iteratively
        point_data: bytes = response_data[4:]
        tag_names: Dict[int, str] = {}
        start_index: int = 0
        for _ in range(number_of_points):
            point_number: int = point_data[start_index]
            tag_name: str = struct.unpack('<10s', point_data[start_index + 1:start_index + 11])[0]
            tag_names[point_number] = tag_name
            start_index += 11

        return HistoryTagPeriodIndexData(
            history_segment=history_segment,
            number_of_history_points=number_of_points,
            periodic_index=periodic_index,
            tag_names=tag_names
        )




"""Opcode 118: Request Alarm Data"""

class AlarmDataRequestData(RequestData):

    opcode: int = 118

    number_of_alarms: int

    starting_alarm_log_index: int

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'B',
            self.number_of_alarms
        )
        data += struct.pack(
            '<h',
            self.starting_alarm_log_index
        )
        return data


class AlarmDataData(BaseModel):

    number_of_alarms: int

    starting_alarm_log_index: int

    current_alarm_log_index: int

    alarm_data: List[AlarmTypes.AlarmT]
    


class AlarmDataResponseData(ResponseData[AlarmDataData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[AlarmDataData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> AlarmDataData:
        
        # Unpack data
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        number_of_alarms: int = response_data[0]
        starting_alarm_log_index: int = struct.unpack('<h', response_data[1:3])[0]
        current_alarm_log_index: int = struct.unpack('<h', response_data[3:5])[0]

        # Extract alarm data iteratively
        alarm_data: bytes = response_data[5:]
        alarms: List[AlarmTypes.AlarmT] = []
        start_index: int = 0
        for _ in range(number_of_alarms):
            this_alarm_data: bytes = alarm_data[start_index:start_index + 23]
            alarm_obj: AlarmTypes.AlarmT = AlarmTypes.get_alarm_from_binary(data=this_alarm_data)
            alarms.append(alarm_obj)
            start_index += 23

        return AlarmDataData(
            number_of_alarms=number_of_alarms,
            starting_alarm_log_index=starting_alarm_log_index,
            current_alarm_log_index=current_alarm_log_index,
            alarm_data=alarms
        )




"""Opcode 119: Request Event Data"""

class EventDataRequestData(RequestData):

    opcode: int = 119

    number_of_events: int

    starting_event_log_index: int

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'B',
            self.number_of_events
        )
        data += struct.pack(
            '<h', 
            self.starting_event_log_index
        )
        return data



class EventDataData(BaseModel):

    number_of_events: int

    start_event_log_index: int

    current_event_log_index: int

    event_data: List[EventTypes.EventT]



class EventDataResponseData(ResponseData[EventDataData]):
    """
    Parameter request response data meta-model.
    """
    
    data: Optional[EventDataData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> EventDataData:
        
        # Unpack data
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        number_of_events: int = response_data[0]
        starting_event_log_index: int = struct.unpack('<h', response_data[1:3])[0]
        current_event_log_index: int = struct.unpack('<h', response_data[3:5])[0]

        # Extract event data iteratively
        event_data: bytes = response_data[5:]
        events: List[EventTypes.EventT] = []
        start_index: int = 0
        for _ in range(number_of_events):
            this_event_data: bytes = event_data[start_index:start_index + 22]
            event: EventTypes.EventT = EventTypes.get_event_from_binary(data=this_event_data)
            events.append(event)
            start_index += 22

        return EventDataData(
            number_of_events=number_of_events,
            start_event_log_index=starting_event_log_index,
            current_event_log_index=current_event_log_index,
            event_data=events
        )




"""Opcode 135: Request Single Point History Data"""

class SinglePointHistoryRequestData(RequestData):

    opcode: int = 135

    history_segment: int = Field(ge=0)
    """History segment to request history data for."""

    history_point_number: int = Field(ge=0)
    """History point to request history data for."""

    history_type: HistoryType
    """Type of historical data to request."""

    starting_history_segment_index: int = Field(ge=0)
    """Starting history segment index to request."""

    number_of_values: int = Field(ge=0, lt=60)
    """Number of historical values to request."""

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BBB',
            self.history_segment,
            self.history_point_number,
            self.history_type.value
        )
        data += struct.pack(
            '<h', 
            self.starting_history_segment_index
        )
        data += struct.pack(
            'B',
            self.number_of_values
        )
        return data


class SinglePointHistoryData(BaseModel):

    history_segment: int
    """The history segment this historical data belongs to."""

    history_point_number: int
    """The history point this historical data belongs to."""

    current_history_segment_index: int
    """The current history segment index."""

    number_of_values: int
    """The number of historical points sent."""

    values: List[float | datetime]
    """List of historical values."""


class SinglePointHistoryResponseData(ResponseData[SinglePointHistoryData]):

    data: Optional[SinglePointHistoryData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> SinglePointHistoryData:
        
        if isinstance(request_data, SinglePointHistoryRequestData):

            # Parse response for request-specific data
            data_length: int = raw_response[5]
            response_data: bytes = raw_response[6:6 + data_length]

            # Extract contextual data
            history_segment: int = response_data[0]
            history_point_number: int = response_data[1]
            current_history_segment_index: int = struct.unpack('<h', response_data[2:4])[0]
            number_of_values: int = response_data[4]
            
            # Extract historical values iteratively
            start_index = 5
            values: List[float | datetime] = []
            for _ in range(number_of_values):
                value_data: bytes = response_data[start_index : start_index + 4]
                
                # Parse as datetime if timestamp requested
                if request_data.history_type in [HistoryType.DAILY_TIME_STAMPS, HistoryType.PERIODIC_TIME_STAMPS]:
                    time_int = struct.unpack('<I', value_data)[0]
                    timestamp: datetime = datetime.fromtimestamp(time_int)
                    values.append(timestamp)
                # Parse as float if value requested
                else:
                    values.append(struct.unpack('<f', response_data[start_index:start_index + 4])[0])
                start_index += 4
            
            return SinglePointHistoryData(
                history_segment=history_segment,
                history_point_number=history_point_number,
                current_history_segment_index=current_history_segment_index,
                number_of_values=number_of_values,
                values=values
            )

        else:
            raise TypeError(f'Invalid Request Data type: {type(request_data)}')




"""Opcode 136: Request Multiple History Point Data"""

class MultiplePointHistoryRequestData(RequestData):

    opcode: int = 136

    history_segment: int
    """History segment to request data for."""

    history_segment_index: int
    """History segment index to request data for."""

    history_type: HistoryType
    """Type of historical data to request."""

    starting_history_point: int
    """Starting history point number for request."""

    number_of_history_points: int
    """Number of history points to request data for."""

    number_of_time_periods: int
    """Number of time periods to request data for."""

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'B',
            self.history_segment,
        )
        data += struct.pack(
            '<h', 
            self.history_segment_index
        )
        data += struct.pack(
            'BBBB',
            self.history_type.value,
            self.starting_history_point,
            self.number_of_history_points,
            self.number_of_time_periods
        )
        return data



class MultiplePointHistoryData(BaseModel):

    history_segment: int
    """History segment for data."""

    history_segment_index: int
    """History segment index for data."""

    current_history_segment_index: int
    """Current history segment index."""

    number_of_data_elements: int
    """Number of data elements sent ((# of history points + 1) * # of time periods)."""

    values: Dict[datetime, Dict[int, float]]
    """Values by point number, by period timestamp."""



class MultiplePointHistoryResponseData(ResponseData[MultiplePointHistoryData]):

    data: Optional[MultiplePointHistoryData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> MultiplePointHistoryData:
        if isinstance(request_data, MultiplePointHistoryRequestData):

            # Parse response for request-specific data
            data_length: int = raw_response[5]
            response_data: bytes = raw_response[6:6 + data_length]

            # Extract contextual data
            history_segment: int = response_data[0]
            history_segment_index: int = struct.unpack('<h', response_data[1:3])[0]
            current_history_segment_index: int = struct.unpack('<h', response_data[3:5])[0]
            number_of_data_elements: int = response_data[5]

            # Calculate the start/end index of each time period
            number_of_points: int = request_data.number_of_history_points
            number_of_periods: int = request_data.number_of_time_periods
            start_indexes: list[int] = []
            curr_index: int = 0
            for _ in range(number_of_periods):
                start_indexes.append(curr_index)
                curr_index += (number_of_points + 1) * 4 # Number of point entries + 1 entry for the time period (all 4 bytes)

            # Extract the point/timestamp data
            points_data: bytes = response_data[6:]
            points_length: int = 4 * number_of_points
            values: Dict[datetime, Dict[int, float]] = {}
            for index in start_indexes:

                # Get timestamp and initialize entry in dictionary
                timestamp_start_index: int = index
                timestamp_end_index: int = timestamp_start_index + 4
                time_int: int = struct.unpack('<I', points_data[timestamp_start_index : timestamp_end_index])[0]
                timestamp: datetime = datetime.fromtimestamp(time_int)
                values[timestamp] = {}

                # Extract each point for the timestamp and add to dictionary
                points_start_index: int = index + 4
                points_end_index: int = points_start_index + points_length
                points_bytes: bytes = points_data[points_start_index : points_end_index]
                points_index: int = 0
                for i in range(number_of_points):
                    point_start_index: int = points_index
                    point_end_index: int = point_start_index + 4
                    point_bytes: bytes = points_bytes[point_start_index : point_end_index]
                    point_float: float = struct.unpack('<f', point_bytes)[0]
                    point_number: int = request_data.starting_history_point + i
                    values[timestamp][point_number] = point_float
                    points_index += 4
            
            return MultiplePointHistoryData(
                history_segment=history_segment,
                history_segment_index=history_segment_index,
                current_history_segment_index=current_history_segment_index,
                number_of_data_elements=number_of_data_elements,
                values=values
            ) 
        else:
            raise TypeError(f'Invalid Request Data type: {type(request_data)}')




"""Opcode 137: Request History Index for a Day"""

class DailyHistoryIndexRequestData(RequestData):

    opcode: int = 137

    history_segment: int
    """The history segment to execute the request against."""

    day_requested: int
    """The day being requested."""

    month_requested: int
    """The month being requested."""

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BBB',
            self.history_segment,
            self.day_requested,
            self.month_requested
        )
        return data


class DailyHistoryIndexData(BaseModel):

    history_segment: int
    """The history segment to which the indexes correspond."""
    
    starting_periodic_index: int
    """Starting periodic index for a day and month request."""

    number_of_periodic_entries: int
    """Number of periodic entries for the day."""

    daily_index: int
    """Daily index for day and month requested."""

    number_of_daily_entries: int
    """Number of daily entries per contract day."""


class DailyHistoryIndexResponseData(ResponseData[DailyHistoryIndexData]):

    data: Optional[DailyHistoryIndexData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> DailyHistoryIndexData:

        # Parse response for request-specific data
        data_length: int = raw_response[5]
        response_data: bytes = raw_response[6:6 + data_length]

        # Extract data
        history_segment: int = response_data[0]
        starting_periodic_index: int = struct.unpack('<h', response_data[1:3])[0]
        number_of_periodic_entries: int = struct.unpack('<h', response_data[3:5])[0]
        daily_index: int = struct.unpack('<h', response_data[5:7])[0]
        number_of_daily_entries: int = struct.unpack('<h', response_data[7:9])[0]

        return DailyHistoryIndexData(
            history_segment=history_segment,
            starting_periodic_index=starting_periodic_index,
            number_of_periodic_entries=number_of_periodic_entries,
            daily_index=daily_index,
            number_of_daily_entries=number_of_daily_entries
        )




"""Opcode 138: Request Daily and Periodic History for a Day"""

class DailyPeriodicHistoryRequestData(RequestData):
    
    opcode: int = 138

    history_segment: int
    """The history segment for which to request history."""

    history_point: int
    """The history point for which to request history."""

    day_requested: int
    """The day for which to request history."""

    month_requested: int
    """The month for which to request history."""

    @property
    def data_binary(self) -> bytes:
        data: bytes = struct.pack(
            'BBBB',
            self.history_segment,
            self.history_point,
            self.day_requested,
            self.month_requested
        )
        return data
    

class DailyPeriodicHistoryData(BaseModel):

    history_segment: int
    """The history segment the historical data belongs to."""

    history_point: int
    """The history point the historical data belongs to."""

    day_requested: int
    """The day used for the history request."""

    month_requested: int
    """The month used for the history request."""

    number_of_periodic_entries: int
    """Number of periodic entries returned."""

    number_of_daily_entries: int
    """Number of daily entries returned."""

    periodic_values: Dict[int, float]
    """Periodic historical values indexed by period."""

    daily_values: Dict[int, float]
    """Daily historical values indexed by day."""


class DailyPeriodicHistoryResponseData(ResponseData[DailyPeriodicHistoryData]):

    data: Optional[DailyPeriodicHistoryData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> DailyPeriodicHistoryData:

        # Parse response for request-specific data
        data_length: int = raw_response[5]
        response_data: bytes = raw_response[6:6 + data_length]

        # Extract contextual data
        history_segment: int = response_data[0]
        history_point: int = response_data[1]
        day_requested: int = response_data[2]
        month_requested: int = response_data[3]
        number_of_periodic_entries: int = struct.unpack('<h', response_data[4:6])[0]
        number_of_daily_entries: int = struct.unpack('<h', response_data[6:8])[0]

        # Extract value data iteratively
        periodic_values: Dict[int, float] = {}
        start_index: int = 0
        for i in range(number_of_periodic_entries):
            value: float = struct.unpack('<f', response_data[start_index : start_index + 4])[0]
            periodic_values[i] = value
            start_index += 4
        
        daily_values: Dict[int, float] = {}
        for i in range(number_of_daily_entries):
            value: float = struct.unpack('<f', response_data[start_index : start_index + 4])[0]
            daily_values[i] = value
            start_index += 4
        
        return DailyPeriodicHistoryData(
            history_segment=history_segment,
            history_point=history_point,
            day_requested=day_requested,
            month_requested=month_requested,
            number_of_periodic_entries=number_of_periodic_entries,
            number_of_daily_entries=number_of_daily_entries,
            periodic_values=periodic_values,
            daily_values=daily_values
        )
    



"""Opcode 139: History Information Data"""


class HistoryInformationRequestData(RequestData):

    opcode: int = 139

    command: HistoryInformationRequestCommand
    """Command to issue for History Information Request. 0 requests configured points, 1 requests point data."""

    history_segment: int
    """History segment to query against. Required for both commands."""

    history_segment_index: int | None = None
    """History segment index to query history for. Only required for Command 1."""

    history_type: HistoryType | None = None
    """History type for history query. Only required for Command 1."""

    number_of_time_periods: int | None = None
    """Number of time periods for history query. Only required for Command 1."""

    request_timestamps: bool | None = None
    """If True, request timestamps for each period in history query. Only required for Command 1."""

    history_points: List[int] | None = None
    """History points for history query. Only required for Command 1."""

    @property
    def data_binary(self) -> bytes:
        if self.command == HistoryInformationRequestCommand.REQUEST_POINT_DATA:
            if (
                self.history_type is not None
            ) and (
                self.request_timestamps is not None
            ) and (
                self.history_points
            ):
                data: bytes = struct.pack(
                    'BB',
                    self.command.value,
                    self.history_segment
                )
                data += struct.pack('<h', self.history_segment_index)
                data += struct.pack(
                    'BBBB',
                    self.history_type.value,
                    self.number_of_time_periods,
                    int(self.request_timestamps),
                    len(self.history_points)
                )
                for point in self.history_points:
                    data += struct.pack('B', point)
                return data
            else:
                raise TypeError('If requesting point data, must include list of history points, history type, and timestamp request arguments.')
        elif self.command == HistoryInformationRequestCommand.REQUEST_CONFIGURED_POINTS:
            data: bytes = struct.pack(
                'BB',
                self.command.value,
                self.history_segment
            )
            return data
        else:
            raise TypeError

    @model_validator(mode='after')
    def validate_for_command(self) -> Self:
        if self.command == HistoryInformationRequestCommand.REQUEST_CONFIGURED_POINTS:
            return self
        elif self.command == HistoryInformationRequestCommand.REQUEST_POINT_DATA:
            if (
                self.history_segment_index is None
                or self.history_points is None
                or self.history_type is None
                or self.number_of_time_periods is None
                or self.request_timestamps is None
            ):
                raise ValueError(
                    'For Command 1 (Request Point Data), the following arguments must be provided: '
                    'history_segment_index, history_type, history_points, number_of_time_periods, request_timestamps'
                )
            else:
                return self
        else:
            raise ValueError('Invalid command type.')


class HistoryInformationData(BaseModel):

    command: HistoryInformationRequestCommand
    """The command requested. Command 0 returns configured points. Command 1 returns point data."""

    history_segment: int
    """History segment requested."""

    number_of_configured_points: int | None = None
    """Number of configured points on the history segment. Only returned for Command 0."""

    configured_points: list[int] | None = None
    """List of configured points on the history segment. Only returned for Command 0."""

    current_index: int | None = None
    """Current history segment index. Only returned for Command 1."""

    number_of_time_periods: int | None = None
    """Number of time periods requested. Only returned for Command 1."""

    request_timestamps: bool | None = None
    """If true, timestamps were requested. Only returned for Command 1."""

    number_of_points: int | None = None
    """Number of history points requested. Only returned for Command 1."""

    values: Dict[datetime | int, Dict[int, float]] | None = None
    """
    Values by point number, then by time period. The time period key is either an integer or, if 
    timestamps were requested, the timestamp of the period. Only returned for Command 1.
    """

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        """Overridden model_dump to exclude null fields, due to duplicitous request data."""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs) -> str:
        """Overridden model_dump_json to exclude null fields, due to duplicitous request data."""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump_json(*args, **kwargs)


class HistoryInformationResponseData(ResponseData[HistoryInformationData]):
    
    data: Optional[HistoryInformationData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> HistoryInformationData:
        # Set timestamp of response receipt
        response_timestamp: datetime = datetime.now()
        
        # Parse response for TL, parameter count, and starting parameter
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]
        
        # Determine which set of data to return based on command
        command = HistoryInformationRequestCommand(response_data[0])
        if command == HistoryInformationRequestCommand.REQUEST_CONFIGURED_POINTS:
            history_segment: int = response_data[1]
            number_of_configured_points: int = response_data[2]
            configured_points: list[int] = []
            for i in range(3, len(response_data)):
                configured_points.append(response_data[i])
            return HistoryInformationData(
                command=command,
                history_segment=history_segment,
                number_of_configured_points=number_of_configured_points,
                configured_points=configured_points
            )
        elif command == HistoryInformationRequestCommand.REQUEST_POINT_DATA:
            
            # Get the requested history points from request data
            if isinstance(request_data, HistoryInformationRequestData):
                requested_points: list[int] | None = request_data.history_points
                if requested_points is None:
                    raise ValueError('Requested history points from request data was null.')
            else:
                raise TypeError('Invalid type for request data.')
            
            # Unpack basic data
            history_segment: int = response_data[1]
            current_index: int = struct.unpack('h', response_data[2:4])[0]
            number_of_time_periods: int = response_data[4]
            request_timestamps: bool = bool(response_data[5])
            number_of_points: int = response_data[6]
            point_data_bytes: bytes = response_data[7:]
            
            # Unpack history point values with or without timestamps
            values: Dict[datetime | int, Dict[int, float]] = {}
            curr_idx: int = 0

            # Quick check to make sure we have expected number of points
            if number_of_points != len(requested_points):
                raise ValueError('Received different number of points than requested points.')
            
            # Each time period batch contains the timestamp and then a value for each point
            for i in range(number_of_time_periods):
                
                # Handle timestamps if requested
                timestamp: datetime | None = None
                if request_timestamps:
                    time_int: int = struct.unpack('<I', point_data_bytes[curr_idx:curr_idx + 4])[0] # timestamp is 4 bytes
                    timestamp = datetime.fromtimestamp(time_int)
                    curr_idx += 4
                    values[timestamp] = {} # create entry for this timestamp
                else:
                    values[i] = {} # create entry for time period index
                
                for point in requested_points:
                    point_value: float = struct.unpack('<f', point_data_bytes[curr_idx:curr_idx + 4])[0] # point data is 4 bytes
                    if request_timestamps:
                        if timestamp:
                            values[timestamp][point] = point_value # store at timestamp key
                        else:
                            raise ValueError('Timestamps requested but invalid timestamp found.')
                    else:
                        values[i][point] = point_value # store at integer time period key
                    curr_idx += 4 # increment by the 4 value bytes

            return HistoryInformationData(
                command=command,
                history_segment=history_segment,
                current_index=current_index,
                number_of_time_periods=number_of_time_periods,
                request_timestamps=request_timestamps,
                number_of_points=number_of_points,
                values=values
            )
        else:
            raise TypeError('Response included invalid command value.')

    def model_dump(self, *args, **kwargs) -> Dict[str, Any]:
        """Overridden model_dump to exclude null fields, due to duplicitous request data."""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump(*args, **kwargs)

    def model_dump_json(self, *args, **kwargs) -> str:
        """Overridden model_dump_json to exclude null fields, due to duplicitous request data."""
        kwargs.setdefault('exclude_none', True)
        return super().model_dump_json(*args, **kwargs)


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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> SinglePointParameterData:
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
            print(f'Opcode 167: raw_bytes={data_bytes[start_idx:end_idx]}, start_idx={start_idx}, end_idx={end_idx}, format={parameter_def.data_type.structure.format}, size={parameter_def.data_type.structure.size}, value_tuple={value_tuple}')
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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> ParameterData:
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
            print(f'Opcode 180: raw_bytes={parameter_bytes[param_data_start_idx:end_idx]}, start_idx={param_data_start_idx}, end_idx={end_idx}, format={parameter_def.data_type.structure.format}, size={parameter_def.data_type.structure.size}, value_tuple={value_tuple}')
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



"""Opcode 206: Read Transaction History Data"""

class TransactionHistoryRequestData(RequestData):

    opcode: int = 206

    command: TransactionHistoryRequestCommand
    """Command to issue for Transaction History Request. 1 requests a list of transactions, 1 requests single transaction data."""

    transaction_segment: int
    """Transaction segment to query against. Required for both commands."""

    transaction_offset: int | None = None
    """
    Transaction offset; first transaction starts at index 0. After rollover, this is not 
    necessarily the oldest transaction. Only required for Command 1.
    """

    transaction_number: int | None = None
    """Transaction number to request. Only required for Command 2."""

    data_offset: int | None = None
    """Offset into the data type/value pairs, in # of bytes."""

    @property
    def data_binary(self) -> bytes:
        if self.command == TransactionHistoryRequestCommand.LIST_TRANSACTIONS:
            if (
                self.transaction_segment is not None
            ) and (
                self.transaction_offset is not None
            ):
                data: bytes = struct.pack(
                    'BB',
                    self.command.value,
                    self.transaction_segment
                )
                data += struct.pack('<h', self.transaction_offset)
                return data
            else:
                raise TypeError('If requesting transaction list, must include segment and transaction offset arguments.')
        elif self.command == TransactionHistoryRequestCommand.READ_TRANSACTION:
            if (
                self.transaction_segment is not None
            ) and (
                self.transaction_number is not None
            ) and (
                self.data_offset is not None
            ):
                data: bytes = struct.pack(
                    'BB',
                    self.command.value,
                    self.transaction_segment
                )
                data += struct.pack('<h', self.transaction_number)
                data += struct.pack('<h', self.data_offset)
                return data
            else:
                raise TypeError('If requesting transaction list, must include segment, transaction number, and data offset arguments.')
        else:
            raise TypeError('Invalid command type.')


class TransactionHistoryData(BaseModel):

    command: TransactionHistoryRequestCommand
    """Command to which data is responding."""

    number_of_transactions: int | None = None
    """Number of transactions returned. Only returned for Command 1."""
    
    excess_transactions: bool | None = None
    """If True, there are more transactions than were returned with this data. Only returned for Command 1."""

    description: str | None = None
    """Description of the transaction segment. Only returned for Command 1."""

    payload_size: int | None = None
    """
    Size of the data portion of the transactions returned. Equal to the sum of the size, in bytes,
    of all data type codes and values of all transactions in segment. Only returned for Command 1.
    """

    transactions: list[tuple[int, datetime]] | None = None
    """List of tuples with transaction numbers and the date the transaction was created. Only returned for Command 1."""

    message_data_size: int | None = None
    """Size of response data in bytes. Only returned for Command 2."""

    excess_data: int | None = None
    """If True, there was more transaction data than was returned with this data. Only returned for Command 2."""

    values: list[Any] | None = None
    """Transaction values."""


class TransactionHistoryResponseData(ResponseData[TransactionHistoryData]):

    data: Optional[TransactionHistoryData] = None

    @classmethod
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> TransactionHistoryData:
        
        # Parse response for parameter count and value data
        data_length: int = int(raw_response[5])
        response_data: bytes = raw_response[6:6 + data_length]

        command = TransactionHistoryRequestCommand(response_data[0])
        if command == TransactionHistoryRequestCommand.LIST_TRANSACTIONS:
            number_of_transactions: int = response_data[1]
            excess_transactions: bool = bool(response_data[2])
            description: str = struct.unpack('10s', response_data[3:13])[0]
            payload_size: int = struct.unpack('<h', response_data[13:15])[0]
            
            # Decode transactions
            transaction_bytes: bytes = response_data[15:]
            transactions: list[tuple[int, datetime]] = []
            curr_idx: int = 0
            for i in range(number_of_transactions):
                transaction_number: int = struct.unpack('<h', transaction_bytes[curr_idx:curr_idx + 2])[0] # 2 bytes for transaction number
                time_int: int = struct.unpack('<I', transaction_bytes[curr_idx + 2:curr_idx + 6])[0] # 4 bytes for date
                timestamp: datetime = datetime.fromtimestamp(time_int)
                transactions.append((transaction_number, timestamp))
                curr_idx += 6 # increment by 6 number/date bytes
            
            return TransactionHistoryData(
                command=command,
                number_of_transactions=number_of_transactions,
                excess_transactions=excess_transactions,
                description=description,
                payload_size=payload_size,
                transactions=transactions
            )

        elif command == TransactionHistoryRequestCommand.READ_TRANSACTION:
            message_data_size: int = response_data[1]
            excess_data: bool = bool(response_data[2])
            
            # Decode values
            values: list[Any] = []
            value_bytes_size: int = message_data_size - 1 # 1 byte for the excess data flag
            value_bytes: bytes = response_data[3:value_bytes_size]
            curr_idx: int = 0
            while curr_idx < len(value_bytes):
                data_type: int = value_bytes[curr_idx]
                data_type_class: ROCDataType = TransactionDataTypeDict[data_type]
                value_start_idx: int = curr_idx + 1
                value_end_idx: int = value_start_idx + data_type_class.structure.size
                value: Any = struct.unpack(
                    data_type_class.structure.format, 
                    value_bytes[value_start_idx:value_end_idx]
                )
                values.append(value)
                curr_idx += 1 + data_type_class.structure.size

            return TransactionHistoryData(
                command=command,
                message_data_size=message_data_size,
                excess_data=excess_data,
                values=values
            )
        else:
            raise TypeError('Invalid command type included in response.')


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
    def data_from_binary(cls, raw_response: bytes, request_data: RequestData) -> OpcodeErrorData:
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
    _105 = MessageModel(
        request_data=TodayYestMinMaxRequestData, 
        response_data=TodayYestMinMaxResponseData, 
        opcode_desc='Request Today and Yesterday Min/Max Values'
    )
    _108 = MessageModel(
        request_data=HistoryTagPeriodIndexRequestData, 
        response_data=HistoryTagPeriodIndexResponseData, 
        opcode_desc='Request History Tag and Periodic Index'
    )
    _118 = MessageModel(request_data=AlarmDataRequestData, response_data=AlarmDataResponseData, opcode_desc='Request Alarm Data')
    _119 = MessageModel(request_data=EventDataRequestData, response_data=EventDataResponseData, opcode_desc='Request Event Data')
    _135 = MessageModel(
        request_data=SinglePointHistoryRequestData, 
        response_data=SinglePointHistoryResponseData, 
        opcode_desc='Request Single Point History Data'
    )
    _136 = MessageModel(
        request_data=MultiplePointHistoryRequestData,
        response_data=MultiplePointHistoryResponseData,
        opcode_desc='Request Multiple History Point Data'
    )
    _137 = MessageModel(
        request_data=DailyHistoryIndexRequestData,
        response_data=DailyHistoryIndexResponseData,
        opcode_desc='Request History Index for a Day'
    )
    _138 = MessageModel(
        request_data=DailyPeriodicHistoryRequestData,
        response_data=DailyPeriodicHistoryResponseData,
        opcode_desc='Request Daily and Periodic History for a Day'
    )
    _139 = MessageModel(
        request_data=HistoryInformationRequestData,
        response_data=HistoryInformationResponseData,
        opcode_desc='Request History Information Data'
    )
    _167 = MessageModel(
        request_data=SinglePointParameterRequestData, 
        response_data=SinglePointParameterResponseData, 
        opcode_desc='Request Single Point Parameter(s)'
    )
    _180 = MessageModel(
        request_data=ParameterRequestData, 
        response_data=ParameterResponseData, 
        opcode_desc='Request Parameter(s)'
    )
    _206 = MessageModel(
        request_data=TransactionHistoryRequestData, 
        response_data=TransactionHistoryResponseData, 
        opcode_desc='Request Transaction History'
    )
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