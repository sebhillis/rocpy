from re import M
from pydantic import BaseModel, field_serializer, Field
from typing import Type, Tuple, Any, ClassVar, Union, get_args
from enums import SystemEventTypeEnum, UserEventTypeEnum, EventDataTypeDict
from datetime import datetime, timedelta
from roc_data_types import ROCDataType
from tlp_models.tlp import TLPInstance, TLPValue
import struct
from typing_extensions import Annotated
from abc import ABC, abstractmethod

class EventTypeNotFoundError(KeyError):
    pass


class Event(BaseModel):
    """Base Event model."""

    _event_type_code: ClassVar[int]
    """Event Type integer identifier."""

    event_type_code: int = Field(default=-1)
    """Event Type integer identifier."""

    event_type_name: str
    """Event Type name."""

    event_type_desc: str
    """Event Type description."""

    timestamp: datetime
    """Timestamp of the event."""

    def model_post_init(self, __context: Any) -> None:
        self.event_type_code = self.__class__._event_type_code

    @classmethod
    def from_binary(cls, timestamp: datetime, data: bytes) -> 'Event':
        """
        Convert raw binary event data into an Event subclass model instance.

        Args:
            timestamp (datetime): The timestamp of the event, per the raw event data.
            data (bytes): Exactly 22 bytes of event data, as returned by event data request opcode.

        Raises:
            EventTypeNotFoundError: _description_

        Returns:
            Event: Model instance of relevant Event subclass.
        """
        ...


class EventTypes:
    """Container class for event type models."""



    class NoEvent(Event):
        """No event defined."""

        _event_type_code: ClassVar[int] = 0
        """Event Type integer identifier."""

        event_type_name: str = 'No Event'
        """Event Type name."""

        event_type_desc: str = 'No Event defined.'
        """Event Type description."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.NoEvent':
            return EventTypes.NoEvent(timestamp=timestamp)



    class ParameterChangeEvent(Event):

        _event_type_code: ClassVar[int] = 1
        """Event Type integer identifier."""

        event_type_name: str = 'Parameter Change Event'
        """Event Type name."""

        event_type_desc: str = 'A Parameter Change event is logged any time a user makes a change to any TLP.'
        """Event Type description."""

        operator_id: str
        """Identifies who made the change."""

        tlp: TLPInstance
        """TLP definition for the relevant parameter."""

        data_type: ROCDataType
        """Data type of the new value and old value fields."""

        new_value: TLPValue
        """New value of the changed parameter."""

        old_value: TLPValue | None = None
        """Old value of the changed parameter."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.ParameterChangeEvent':
            
            # Get Operator ID
            operator_id: str = struct.unpack('<3s', data[5:8])[0]
            
            # Get raw TLP integers and create TLP model instance
            point_type: int = data[8]
            logical_number: int = data[9]
            parameter: int = data[10]
            tlp: TLPInstance = TLPInstance.from_integers(
                point_type=point_type, 
                logical_number=logical_number, 
                parameter=parameter
            )

            # Get data type of value
            data_type_int: int = data[11]
            data_type: ROCDataType = EventDataTypeDict[data_type_int]
            
            # Extract new value based on data type and create TLP Value instance
            new_value_bytes: bytes = data[12:12 + data_type.structure.size]
            new_value_tuple: tuple[Any] = struct.unpack(
                data_type.structure.format, 
                new_value_bytes
            )
            if len(new_value_tuple) == 1:
                new_value: Any = new_value_tuple[0]
            else:
                new_value: Any = [val for val in new_value_tuple]
            
            new_value_obj: TLPValue = TLPValue.from_tlp_instance(
                tlp=tlp, 
                value=new_value, 
                timestamp=timestamp
            )
            
            # Extract old value based on data type and create TLP Value instance
            ## NOTE: Old value only included if new value doesn't exceed 4 bytes
            if data_type.structure.size > 4:
                old_value = None
            else:
                old_value_bytes: bytes = data[16:16 + data_type.structure.size]
                old_value_tuple: tuple[Any] = struct.unpack(
                    data_type.structure.format,
                    old_value_bytes
                )
                if len(old_value_tuple) == 1:
                    old_value: Any = old_value_tuple[0]
                else:
                    old_value: Any = [val for val in old_value_tuple]
            
            ## Create timestamp, as this is not provided by the protocol
            old_timestamp: datetime = timestamp - timedelta(seconds=1)

            old_value_obj: TLPValue = TLPValue.from_tlp_instance(
                tlp=tlp,
                value=old_value,
                timestamp=old_timestamp
            )
            
            return EventTypes.ParameterChangeEvent(
                timestamp=timestamp,
                operator_id=operator_id,
                tlp=tlp,
                data_type=data_type,
                new_value=new_value_obj,
                old_value=old_value_obj
            )



    class SystemEvent(Event):
        """ROC system event."""

        _event_type_code: ClassVar[int] = 2
        """Event Type integer identifier."""

        event_type_name: str = 'System Event'
        """Event Type name."""

        event_type_desc: str = 'A system event logs internally in the ROC800.'
        """Event Type description."""

        event_code: SystemEventTypeEnum
        """Specific definition of the system event."""

        event_description: str
        """System event description."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.SystemEvent':

            # Get specific system event type from code integer
            system_event_code: int = data[5]
            system_event_type: SystemEventTypeEnum = SystemEventTypeEnum(system_event_code)
            
            # Get text description
            description: str = struct.unpack('<16s', data[6:22])[0]
            
            return EventTypes.SystemEvent(
                timestamp=timestamp,
                event_code=system_event_type,
                event_description=description
            )

    class FSTEvent(Event):
        """FST-related event."""

        _event_type_code: ClassVar[int] = 3
        """Event Type integer identifier."""

        event_type_name: str = 'FST Event'
        """Event Type name."""

        event_type_desc: str = 'An FST event is logged by an FST.'
        """Event Type description."""

        fst: int
        """The FST that logged the event."""

        value: float
        """Value associated with the event."""

        event_description: str
        """Event description."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.FSTEvent':

            # Extract FST index
            fst: int = data[5]

            # Get float value
            value: float = struct.unpack('<f', data[6:10])[0]

            # Get text description
            description: str = struct.unpack('<10s', data[10:20])[0]

            return EventTypes.FSTEvent(
                timestamp=timestamp,
                fst=fst,
                value=value,
                event_description=description
            )


    class UserEvent(Event):
        """User Event."""

        _event_type_code: ClassVar[int] = 4
        """Event Type integer identifier."""

        event_type_name: str = 'User Event'
        """Event Type name."""

        event_type_desc: str = 'A User event is logged by the action of a logged-in user.'
        """Event Type description."""

        operator_id: str
        """Identifies who made the change."""

        event_code: UserEventTypeEnum
        """Specific definition of the event."""

        event_description: str
        """Event description."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.UserEvent':
            
            # Get operator ID
            operator_id: str = struct.unpack('<3s', data[5:8])[0]
            
            # Get specific user event type from code integer
            user_event_code: int = data[8]
            user_event_type: UserEventTypeEnum = UserEventTypeEnum(user_event_code)

            # Get text description
            description: str = struct.unpack('<13s', data[9:22])[0]

            return EventTypes.UserEvent(
                timestamp=timestamp,
                operator_id=operator_id,
                event_code=user_event_type,
                event_description=description
            )

    class PowerLostEvent(Event):

        _event_type_code: ClassVar[int] = 5
        """Event Type integer identifier."""

        event_type_name: str = 'Power Lost Event'
        """Event Type name."""

        event_type_desc: str = 'A Power Lost event is logged when the power to the ROC800 has been lost.'
        """Event Type description."""
        
        power_lost_timestamp: datetime
        """Timestamp at which power was lost."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.PowerLostEvent':
            
            # Get power loss timestamp
            time_int: int = struct.unpack('<I', data[5:9])[0]
            power_timestamp: datetime = datetime.fromtimestamp(time_int)

            return EventTypes.PowerLostEvent(
                timestamp=timestamp,
                power_lost_timestamp=power_timestamp
            )

    class ClockSetEvent(Event):
        
        _event_type_code: ClassVar[int] = 6
        """Event Type integer identifier."""

        event_type_name: str = 'Clock Set Event'
        """Event Type name."""

        event_type_desc: str = 'A Clock Set event is logged when the time is set on the ROC800.'
        """Event Type description."""

        clock_set_timestamp: datetime
        """Timestamp that the ROC800 time was set to."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.ClockSetEvent':

            # Get time the ROC800 was set to
            time_int: int = struct.unpack('<I', data[5:9])[0]
            roc_timestamp: datetime = datetime.fromtimestamp(time_int)

            return EventTypes.ClockSetEvent(
                timestamp=timestamp,
                clock_set_timestamp=roc_timestamp
            )

    class CalibrateVerifyEvent(Event):

        _event_type_code: ClassVar[int] = 7
        """Event Type integer identifier."""

        event_type_name: str = 'Calibration Verify Event'
        """Event Type name."""

        event_type_desc: str = 'A Calibrate Verify event is logged any time a user tests the calibration of an I/O point.'
        """Event Type description."""

        operator_id: str
        """Identifies who made the change."""

        tlp: TLPInstance
        """TLP definition for the parameter that was tested."""

        raw_value: TLPValue
        """Value of the input before calibration was applied."""

        calibrated_value: TLPValue
        """Value of the input after calibration was applied."""

        @classmethod
        def from_binary(cls, timestamp: datetime, data: bytes) -> 'EventTypes.CalibrateVerifyEvent':

            # Get Operator ID
            operator_id: str = struct.unpack('<3s', data[5:8])[0]

            # Get raw TLP integers and create TLP model instance
            point_type: int = data[8]
            logical_number: int = data[9]
            parameter: int = data[10]
            tlp: TLPInstance = TLPInstance.from_integers(
                point_type=point_type, 
                logical_number=logical_number, 
                parameter=parameter
            )

            # Get raw value and create TLP value instance
            raw_value: float = struct.unpack('<f', data[11:15])[0]
            raw_value_obj: TLPValue = TLPValue.from_tlp_instance(
                tlp=tlp, 
                value=raw_value, 
                timestamp=timestamp
            )

            # Get calibrated value and create TLP value instance
            cal_value: float = struct.unpack('<f', data[15:19])[0]
            cal_value_obj: TLPValue = TLPValue.from_tlp_instance(
                tlp=tlp,
                value=raw_value,
                timestamp=timestamp
            )

            return EventTypes.CalibrateVerifyEvent(
                timestamp=timestamp,
                operator_id=operator_id,
                tlp=tlp,
                raw_value=raw_value_obj,
                calibrated_value=cal_value_obj
            )

    EventT = Union[
        NoEvent,
        ParameterChangeEvent,
        SystemEvent,
        FSTEvent,
        UserEvent,
        PowerLostEvent,
        ClockSetEvent,
        CalibrateVerifyEvent
    ]

    EventTTuple: tuple[type] = get_args(EventT)


    @classmethod
    def get_event_type_by_code(cls, event_type_code: int) -> Type[EventT]:

        event_type_cls: Type[EventTypes.EventT] | None = None
        for k, v in cls.__dict__.items():
            if isinstance(v, type):
                if issubclass(v, EventTypes.EventTTuple):
                    if v._event_type_code == event_type_code:
                        event_type_cls = v
        if event_type_cls is None:
            raise EventTypeNotFoundError(f'No event type found for event type code {event_type_code}.')
        else:
            return event_type_cls
        
    @classmethod
    def get_event_from_binary(cls, data: bytes) -> EventT:

        # Get relevant event type subclass
        event_type: Type[Event] = cls.get_event_type_by_code(event_type_code=data[0])

        # Extract the timestamp from the timestamp bytes
        time_int: int = struct.unpack('<I', data[1:5])[0]
        timestamp: datetime = datetime.fromtimestamp(time_int)

        # Invoke the decode method on the event class
        event_instance: EventTypes.EventT = event_type.from_binary(timestamp=timestamp, data=data)

        return event_instance