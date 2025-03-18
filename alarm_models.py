from pydantic import BaseModel, PlainSerializer, Field
from enums import AlarmCondition, ParameterAlarmCode
from datetime import datetime
from typing import ClassVar, Any, Union, get_args, Type
from tlp_models.tlp import TLPInstance
import struct
from typing_extensions import Annotated


class AlarmTypeNotFoundError(KeyError):
    pass

class Alarm(BaseModel):

    is_srbx: bool
    """True if SRBX was issued."""

    condition: Annotated[AlarmCondition, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
    """Alarm condition enumeration."""

    _alarm_type_code: ClassVar[int]
    """Alarm Type integer identifier."""

    alarm_type_code: int = Field(default=-1)
    """Alarm Type integer identifier."""

    timestamp: datetime
    """Timestamp at which the alarm occurred."""

    def model_post_init(self, __context: Any) -> None:
        self.alarm_type_code = self.__class__._alarm_type_code

    @classmethod
    def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'Alarm':
        """
        Convert raw binary event data into an Alarm subclass model instance.

        Args:
            timestamp (datetime): The timestamp of the alarm, per the raw alarm data.
            is_srbx (bool): True if SRBX was issued, per the raw alarm data.
            condition (bool): Condition boolean, per the raw alarm data.
            data (bytes): Exactly 23 bytes of alarm data, as returned by alarm data request opcode.

        Returns:
            Alarm: Model instance of relevant Alarm subclass.
        """
        ...


class AlarmTypes:
    """Container class for alarm type models."""


    class NoAlarm(Alarm):
        """No alarm configured."""

        _alarm_type_code: ClassVar[int] = 0
        """Alarm Type integer identifier."""

        alarm_type_name: str = 'No Alarm'
        """Alarm Type name."""

        alarm_type_desc: str = 'No Alarm defined.'
        """Alarm Type description."""

        @classmethod
        def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'AlarmTypes.NoAlarm':
            return AlarmTypes.NoAlarm(
                timestamp=timestamp,
                is_srbx=is_srbx,
                condition=AlarmCondition(condition)
            )


    class ParameterAlarm(Alarm):
        """TLP-related alarm."""

        _alarm_type_code: ClassVar[int] = 1
        """Alarm Type integer identifier."""

        alarm_type_name: str = 'Parameter Alarm'
        """Alarm Type name."""

        alarm_type_desc: str = 'This type of alarm is typically generated as a parameter reaches a particular value.'
        """Alarm Type description."""

        alarm_code: Annotated[ParameterAlarmCode, PlainSerializer(lambda x: {'name': x.name, 'value': x.value}, return_type=dict, when_used='always')]
        """Reason why the alarm was logged."""

        tlp: TLPInstance
        """TLP definition for parameter on which alarm occurred."""

        alarm_description: str
        """Description of alarm."""

        value: float
        """Value at the time the alarm occurred. Value is a float regardless of underlying TLP data type."""

        @classmethod
        def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'AlarmTypes.ParameterAlarm':
            
            # Extract specific alarm code
            alarm_code_int: int = data[5]
            alarm_code: ParameterAlarmCode = ParameterAlarmCode(alarm_code_int)
            
            # Extract raw TLP integers and create TLP instance
            point_type: int = data[6]
            logical_number: int = data[7]
            parameter: int = data[8]
            tlp: TLPInstance = TLPInstance.from_integers(
                point_type=point_type, 
                logical_number=logical_number, 
                parameter=parameter
            )

            # Get text description
            alarm_description: str = struct.unpack('<10s', data[9:19])[0]
            
            # Get float value
            alarm_value: float = struct.unpack('<f', data[19:23])[0]

            return AlarmTypes.ParameterAlarm(
                is_srbx=is_srbx,
                condition=AlarmCondition(condition),
                timestamp=timestamp,
                alarm_code=alarm_code,
                tlp=tlp,
                alarm_description=alarm_description,
                value=alarm_value
            )


    class FSTAlarm(Alarm):
        """FST-related alarm."""

        _alarm_type_code: ClassVar[int] = 2
        """Alarm Type integer identifier."""

        alarm_type_name: str = 'FST Alarm'
        """Alarm Type name."""

        alarm_type_desc: str = 'Alarm that was logged from an FST.'
        """Alarm Type description."""

        fst: int
        """Which running FST logged the alarm."""

        alarm_description: str
        """Description of alarm."""

        value: float
        """Value at the time the alarm occurred."""

        @classmethod
        def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'AlarmTypes.FSTAlarm':
            
            # Get FST index
            fst_index: int = data[5]
            
            # Get text description 
            alarm_description: str = struct.unpack('<13s', data[6:19])[0]
            
            # Get float value
            alarm_value: float = struct.unpack('<f', data[19:23])[0]
            
            return AlarmTypes.FSTAlarm(
                is_srbx=is_srbx,
                condition=AlarmCondition(condition),
                timestamp=timestamp,
                fst=fst_index,
                alarm_description=alarm_description,
                value=alarm_value
            )


    class UserTextAlarm(Alarm):
        """Text alarm generated by user C++ program."""

        _alarm_type_code: ClassVar[int] = 3
        """Alarm Type integer identifier."""

        alarm_type_name: str = 'User Text Alarm'
        """Alarm Type name."""

        alarm_type_desc: str = 'Alarm that was logged by a User C++ Program.'
        """Alarm Type description."""

        alarm_description: str
        """Description of alarm."""

        @classmethod
        def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'AlarmTypes.UserTextAlarm':
            
            # Get text description
            alarm_description: str = struct.unpack('<18s', data[5:23])[0]

            return AlarmTypes.UserTextAlarm(
                is_srbx=is_srbx,
                condition=AlarmCondition(condition),
                timestamp=timestamp,
                alarm_description=alarm_description
            )


    class UserValueAlarm(Alarm):
        """Value alarm generated by user C++ program."""

        _alarm_type_code: ClassVar[int] = 4
        """Alarm Type integer identifier."""

        alarm_type_name: str = 'User Value Alarm'
        """Alarm Type name."""

        alarm_type_desc: str = 'Alarm that was logged by a User C++ Program.'
        """Alarm Type description."""

        alarm_description: str
        """Description of alarm."""

        value: float
        """Value at the time the alarm occurred."""

        @classmethod
        def from_binary(cls, timestamp: datetime, is_srbx: bool, condition: bool, data: bytes) -> 'AlarmTypes.UserValueAlarm':
            
            # Get text description
            alarm_description: str = struct.unpack('<14s', data[5:19])[0]

            # Get float value
            alarm_value: float = struct.unpack('<f', data[19:23])[0]
            
            return AlarmTypes.UserValueAlarm(
                is_srbx=is_srbx,
                condition=AlarmCondition(condition),
                timestamp=timestamp,
                alarm_description=alarm_description,
                value=alarm_value
            )
    
    AlarmT = Union[
        NoAlarm,
        ParameterAlarm,
        FSTAlarm,
        UserTextAlarm,
        UserValueAlarm
    ]

    AlarmTTuple: tuple[type] = get_args(AlarmT)


    @classmethod
    def get_alarm_type_by_code(cls, alarm_type_code: int) -> Type[AlarmT]:

        alarm_type_cls: Type[AlarmTypes.AlarmT] | None = None
        for k, v in cls.__dict__.items():
            if isinstance(v, type):
                if issubclass(v, AlarmTypes.AlarmTTuple):
                    if v._alarm_type_code == alarm_type_code:
                        alarm_type_cls = v
        if alarm_type_cls is None:
            raise AlarmTypeNotFoundError(f'No alarm type found for alarm type code {alarm_type_code}.')
        else:
            return alarm_type_cls
        
    @classmethod
    def get_alarm_from_binary(cls, data: bytes) -> AlarmT:

        # Unpack type byte into type int and bool flags
        type_int: int = data[0]
        bit_array: list[bool] = []
        for i in range(8):
            bit: int = (type_int >> i) & 1
            bit_array.append(bool(bit))
        is_srbx: bool = bit_array[7]
        condition: bool = bit_array[6]
        type_code_int: int = 0
        for i, bit in enumerate(bit_array[:6]):
            type_code_int |= (bit << i)

        # Get relevant alarm type subclass
        alarm_type: Type[Alarm] = cls.get_alarm_type_by_code(alarm_type_code=type_code_int)

        # Extract the timestamp from the timestamp bytes
        time_int: int = struct.unpack('<I', data[1:5])[0]
        timestamp: datetime = datetime.fromtimestamp(time_int)

        # Invoke the decode method on the alarm class
        event_instance: AlarmTypes.AlarmT = alarm_type.from_binary(
            is_srbx=is_srbx,
            condition=condition,
            timestamp=timestamp, 
            data=data
        )

        return event_instance