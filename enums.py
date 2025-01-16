from enum import Enum
from roc_data_types import ParameterDataTypes as dt, ROCDataType

class ROCOperatingMode(Enum):
    """ROC Operating Mode"""
    FIRMWARE_UPDATE_MODE = 0
    RUN_MODE = 1

class LogicalCompatibilityStatus(Enum):
    """ROC Logical Compatibility Status"""
    _16_POINTS_PER_SLOT_9_SLOTS_MAX = 0
    _16_POINTS_PER_SLOT_14_SLOTS_MAX = 1
    _8_POINTS_PER_SLOT_27_SLOTS_MAX = 2

class OpcodeRevision(Enum):
    """Revision of Opcode 6"""
    ORIGINAL = 0
    EXTENDED_FOR_ADDITIONAL_POINT_TYPES = 1

class ROCSubType(Enum):
    """Subtype of ROC Device"""
    SERIES_2 = 0
    SERIES_1 = 1

class ROCType(Enum):
    """Type of ROC Device"""
    ROCPAC_ROC300_SERIES = 1
    FLO_BOSS_407 = 2
    FLASHPAC_ROC300_SERIES = 3
    FLO_BOSS_503 = 4
    FLO_BOSS_504 = 5
    ROC_800 = 6
    DL_800 = 11

class HistoryArchiveType(Enum):
    """Historical Data Archive Method"""
    HISTORY_POINT_NOT_DEFINED = 0
    USER_C_DATA = 1
    USER_C_TIME = 2
    FST_DATA_HISTORY = 65
    FST_TIME = 67
    AVERAGE = 128
    ACCUMULATE = 129
    CURRENT_VALUE = 130
    TOTALIZE = 134


class HistoryAveragingRateType(Enum):
    """Historical Data Averaging Method/Accumulation Rate"""

    # Averaging Types
    NONE = 0
    FLOW_DEPENDENT_TIME_WEIGHTED_LINEAR = 1
    FLOW_DEPENDENT_TIME_WEIGHTED_FORMULAIC = 2
    FLOW_WEIGHTED_LINEAR = 3
    FLOW_WEIGHTED_FORMULAIC = 4
    LINEAR_AVERAGING = 5
    USER_WEIGHTED_AVERAGING = 6
    
    # Accumulation Rates
    PER_SECOND = 10
    PER_MINUTE = 11
    PER_HOUR = 12
    PER_DAY = 13

class AlarmCondition(Enum):
    """Indicates if alarm is being set or cleared."""

    CLEARED = 0
    SET = 1

class ParameterAlarmCode(Enum):
    """Reason why the alarm was logged."""

    LOW_ALARM = 0
    LOW_LOW_ALARM = 1
    HIGH_ALARM = 2
    HIGH_HIGH_ALARM = 3
    RATE_ALARM = 4
    STATUS_CHANGE = 5
    POINT_FAIL = 6
    SCANNING_DISABLED = 7
    SCANNING_MANUAL = 8
    REDUNDANT_TOTAL_COUNTS = 9
    REDUNDANT_FLOW_REGISTER = 10
    NO_FLOW_ALARM = 11
    INPUT_FREEZE_MODE = 12
    SENSOR_COMMUNICATION_FAILURE = 13
    _485_COMMUNICATION_FAILURE = 14
    OFF_SCAN_MODE = 15
    MANUAL_FLOW_INPUTS = 16
    METER_TEMPERATURE_FAILURE_ALARM = 17
    COMPRESSIBILITY_CALCULATION_ALARM = 18
    SEQUENCE_OUT_OF_ORDER = 19
    PHASE_DISCREPANCY = 20
    PULSE_SYNCHRONIZATION_FAILURE = 21
    FREQUENCY_DISCREPANCY = 22
    PULSE_INPUT_ONE_FAILURE = 23
    PULSE_INPUT_TWO_FAILURE = 24
    PULSE_OUTPUT_BUFFER_OVERRUN = 25
    PULSE_OUTPUT_BUFFER_WARNING = 26
    RELAY_FAULT = 27
    RELAY_FAILURE = 28
    STATIC_PRESSURE_LOW_LIMITED = 29
    TEMPERATURE_LOW_LIMITED = 30
    ANALOG_OUTPUT_READBACK_ERROR = 31
    BAD_LEVEL_A_PULSE_STREAM = 32
    MARKET_PULSE_ALARM = 33

class AlarmTypeEnum(Enum):
    """Alarm type."""

    NO_ALARM = 0
    PARAMETER_ALARM = 1
    FST_ALARM = 2
    USER_TEXT_ALARM = 3
    USER_VALUE_ALARM = 4

class EventTypeEnum(Enum):
    """Event Type."""

    NO_EVENT = 0
    PARAMETER_CHANGE_EVENT = 1
    SYSTEM_EVENT = 2
    FST_EVENT = 3
    USER_EVENT = 4
    POWER_LOST_EVENT = 5
    CLOCK_SET_EVENT = 6
    CALIBRATE_VERIFY_EVENT = 7

EventDataTypeDict: dict[int, ROCDataType] = {
    0: dt.BIN,
    1: dt.INT8,
    2: dt.INT16,
    3: dt.INT32,
    4: dt.UINT8,
    5: dt.UINT16,
    6: dt.UINT32,
    7: dt.FL,
    8: dt.TLP,
    9: dt.AC3,
    10: dt.AC7,
    11: dt.AC10,
    12: dt.AC12,
    13: dt.AC20,
    14: dt.AC30,
    15: dt.AC40,
    16: dt.DBL,
    17: dt.TIME
}

class SystemEventTypeEnum(Enum):
    """System Event Type."""

    INITIALIZATION_SEQUENCE = 144
    ALL_POWER_REMOVED = 145
    INITIALIZE_FROM_DEFAULTS = 146
    ROM_CRC_ERROR = 147
    DATABASE_INITIALIZATION = 148
    PROGRAM_FLASH = 150
    SMART_MODULE_INSERTED = 154
    SMART_MODULE_REMOVED = 155
    CLOCK_SET = 200
    TEXT_MESSAGE = 248
    DOWNLOAD_CONFIGURATION = 249
    UPLOAD_CONFIGURATION = 250
    CALIBRATION_TIMEOUT = 251
    CALIBRATION_CANCEL = 252
    CALIBRATION_SUCCESS = 253
    MVS_RESET_TO_FACTORY_DEFAULTS = 254


class UserEventTypeEnum(Enum):
    """User Event Type."""

    INITIALIZATION_SEQUENCE = 144
    ALL_POWER_REMOVED = 145
    INITIALIZE_FROM_DEFAULTS = 146
    ROM_CRC_ERROR = 147
    DATABASE_INITIALIZATION = 148
    PROGRAM_FLASH = 150
    SMART_MODULE_INSERTED = 154
    SMART_MODULE_REMOVED = 155
    CLOCK_SET = 200
    TEXT_MESSAGE = 248
    DOWNLOAD_CONFIGURATION = 249
    UPLOAD_CONFIGURATION = 250
    CALIBRATION_TIMEOUT = 251
    CALIBRATION_CANCEL = 252
    CALIBRATION_SUCCESS = 253
    MVS_RESET_TO_FACTORY_DEFAULTS = 254