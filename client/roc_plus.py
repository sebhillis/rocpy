from typing import List, Dict, Tuple, overload, AsyncGenerator, Optional, TypeVar, Type, Union
import asyncio
from contextlib import asynccontextmanager
from loguru import logger
from pydantic import ValidationError, BaseModel
from datetime import datetime
import json
from opcode_models.opcodes import SinglePointParameterData, SinglePointParameterRequestData
from client.models import *
from opcode_models import *
from client.exceptions import *
from client.models import (
    ConfigurableOpcodeTableDefinition, 
    ConfigurableOpcodeTablesDefinition, 
    HistoryDefinition, 
    IODefinition, 
    IOPointDefinition, 
    HistorySegmentPointConfiguration, 
    HistorySegmentConfiguration
)
from tlp_models.point_types import PointTypeNotFoundError
from tlp_models.tlp import TLPInstance, TLPValue, TLPValues
from client.async_tcp_generic import TCPClient


class ROCPlusClient:
    """
    ROC Plus Client/Driver for communicating with Emerson ROC800 and similar devices.

    Arguments passed to the constructor are validated via Pydantic model and may raise a ValidationError. The easiest
        way to communicate with the device is to use it as an async context manager and then make individual Opcode requests
        or use the methods encapsulating common Opcodes. It can also be used as a regular object instance, but connections
        opened during method calls will NOT automatically be closed.

    Attributes:
        roc_client_def (ROCClientDefinition): ROC client definition data model with validated IP, Port, etc.
        io_definition (IODefinition): I/O definition of ROC device. Initialized as empty IODefinition object.
        stream_reader (asyncio.StreamReader, optional): ROC Client TCP socket reader object. Initialized as None.
        stream_writer (asyncio.StreamWriter, optional): ROC Client TCP socket writer object. Initialized None.
        logger (loguru.Logger): Internal logger object.
    """

    def __init__(
        self, 
        ip: str, 
        port: int, 
        roc_address: int, 
        roc_group: int, 
        host_address: int = 1, 
        host_group: int = 0
    ):
        try:
            self.roc_client_def = ROCClientDefinition(
                ip=ip, # type: ignore
                port=port,
                roc_address=roc_address,
                roc_group=roc_group,
                host_address=host_address,
                host_group=host_group
            )
        except ValidationError as e:
            raise ROCConfigError('Failed to validate ROC config.') from e
        
        self.io_definition = IODefinition()
        self.configurable_opcode_tables_definition = ConfigurableOpcodeTablesDefinition()
        self.history_definition = HistoryDefinition()
        self.system_config: SystemConfigData | None = None
        self._connection = TCPClient(ip=str(self.roc_client_def.ip), port=self.roc_client_def.port)
        self.is_async_context_manager = False
        self._active_request: bool = False
        self.logger = logger


    def __str__(self) -> str:
        return f'ROCPlus Client @ {self.roc_client_def.ip}:{self.roc_client_def.port} | Group: {self.roc_client_def.roc_group} Address: {self.roc_client_def.roc_address}'


    @asynccontextmanager
    async def connect(
        self, 
        init_io_def: bool = False,
        init_user_opcode_def: bool = False,
        init_history_def: bool = False,
        init_system_config: bool = False
    ) -> AsyncGenerator['ROCPlusClient', None]:
        """
        Yields a connected ROCPlusClient object for use as an async context manager.

        Args:
            initialize_io (bool, optional): If True, will upload I/O configuration on connect. Defaults to False.

        Raises:
            e: Re-raises any error encountered while opening connection.

        Yields:
            ROCPlusClient: ROCPlusClient with active, connected TCP socket to ROC device.
        """
        try:
            self.logger.debug('Opening connection within async context manager...')
            self.is_async_context_manager = True
            await self._connection.open_connection()
            self.logger.debug('Connected successfully.')
            if init_io_def:
                self.logger.debug('Reading I/O definition.')
                await self.initialize_io_definition()
                self.logger.debug('I/O definition read successfully.')
            if init_user_opcode_def:
                self.logger.debug('Reading User Opcode Table definition.')
                await self.initialize_configurable_opcode_definition()
                self.logger.debug('User Opcode Table definition read successfully.')
            if init_history_def:
                self.logger.debug('Reading History definition.')
                await self.initialize_history_definition()
                self.logger.debug('History definition read successfully.')
            if init_system_config:
                self.logger.debug('Reading system configuration.')
                await self.get_system_config()
                self.logger.debug('System config read successfully.')
            yield self
        except Exception as e:
            self.logger.error(f'Error encountered during ROC connection: {e}')
            raise e
        finally:
            self.logger.debug('Exiting async context manager...')
            self.is_async_context_manager = False
            try:
                self.logger.debug('Closing connection...')
                await self._connection.close_connection()
                self.logger.debug('Connection closed successfully.')
            except ROCOperationTimeout:
                self.logger.warning('Timed out waiting for connection to close.')
                pass
            finally:
                self.logger.debug('Async context manager exited.')



    def get_opcode_device_data(self) -> DeviceData:
        """
        Generate ROC/Host device header info for Opcode requests.

        Returns:
            DeviceData: ROC/Host device header data.
        """
        try:
            return DeviceData(
                roc_address=self.roc_client_def.roc_address,
                roc_group=self.roc_client_def.roc_group,
                host_address=self.roc_client_def.host_address,
                host_group=self.roc_client_def.host_group
            )
        except ValidationError as e:
            raise ROCConfigError('Failed to validate ROC device data.') from e
    


    async def unary_opcode_request(self, request_data: RequestData) -> Response[ResponseData]:
        """
        Send a single Opcode request and get response.

        If not being used with an async context manager, the connection will be closed after
            the response data is returned by the connection or an exception is raised.

        Args:
            request_data (RequestData): Instance of RequestData for specific Opcode request.

        Returns:
            Response[ResponseData]: Response model instance.
        """
        try:
            self.logger.debug('Making opcode request.')
            self.logger.trace(f'Request data: {request_data}')

            if self._active_request == True:
                raise ROCConnectionError('Already an active request being processed by client.')
            self._active_request = True

            self.logger.debug('Retrieving device data.')
            device_data: DeviceData = self.get_opcode_device_data()
            self.logger.debug('Device data retrieved. Constructing request.')
            request = Request(
                device_data=device_data,
                request_data=request_data
            )
            self.logger.debug('Request constructed. Converting to binary.')
            request_packet: bytes = request.to_binary()
            self.logger.debug('Submitting binary request data to stream.')
            await self._connection.write_to_stream(request_packet)
            self.logger.debug('Request written successfully. Reading response from stream.')
            response_packet: bytes = await self._connection.read_from_stream()
            self.logger.debug('Response read successfully. Decoding binary payload into response object.')
            response: Response = Response.from_binary(raw_response=response_packet)
            self.logger.debug('Response decoded successfully. Returning response object.')
            return response
        except ValidationError as e:
            raise ROCDataError('Request and/or response data failed validation.')
        finally:
            self._active_request = False
            if not self.is_async_context_manager:
                await self._connection.close_connection()
    


    TResp = TypeVar('TResp', bound=BaseModel)

    def validate_response(self, response_data: ResponseData, response_data_type: Type[TResp]) -> TResp:
        """
        Validates that the response to an Opcode has the expected data type.

        This method essentially encapsulates checking a response for an error Opcode, empty data, or unexpected data,
            and returns the core data from the response. This method gets used by the Opcode convenience methods like
            get_system_config that return the data as opposed to the entirety of the Opcode response.

        Args:
            response_data (ResponseData): The ResponseData payload returned for the request. Typically retrieved like "response.response_data".
            response_data_type (Type[TResp]): The expected return type of the "data" field of the ResponseData object. Typically retrieved like "response.response_data.data".

        Raises:
            ROCErrorResponseError: The Opcode returned an error response (Opcode 255).
            ROCDataError: The Opcode returned unexpected data.
            ROCEmptyDataError: The Opcode returned a payload with a data length of 0.

        Returns:
            TResp: The data attribute of the response data provided, if validated.
        """
        self.logger.debug('Validating response against expected data type.')
        if response_data.data:
            self.logger.debug('Response data not empty. Checking data type.')
            if isinstance(response_data.data, response_data_type):
                self.logger.debug('Response data matches expected type. Returning data payload.')
                return response_data.data
            if isinstance(response_data, OpcodeErrorResponseData):
                raise ROCErrorResponseError(errors=response_data.data.errors)
            else:
                raise ROCDataError(f'Unexpected return data type: {type(response_data)}')
        else:
            raise ROCEmptyDataError



    @overload
    async def read_tlp(self, tlp_def: TLPInstance) -> TLPValue:
        """
        Retrieve TLP value.

        Args:
            tlp_def (TLPInstance): TLP definition object.

        Returns:
            TLPValue: TLP value object.
        """
        ...
    
    @overload
    async def read_tlp(self, point_type: int, logical_number: int, parameter: int) -> TLPValue:
        """
        Retrieve TLP value.

        Args:
            point_type (int): TLP Point Type ("T")
            logical_number (int): TLP Logical Number ("L")
            parameter (int): TLP Parameter ("P")

        Returns:
            TLPValue: TLP Value object.
        """
        ...
    
    async def read_tlp(self, *args, **kwargs) -> TLPValue:
        """
        Retrieve TLP value.

        Signatures:
            1. `read_tlp(point_type: int, logical_number: int, parameter: int) -> TLPValue`
            2. `read_tlp(tlp_def: TLPInstance) -> TLPValue`

        Args:
            point_type (int): TLP Point Type ("T")
            logical_number (int): TLP Logical Number ("L")
            parameter (int): TLP Parameter ("P")

        Returns:
            TLPValue: TLP Value object.
        """
        tlp_def: Optional[TLPInstance] = None
        if len(args) == 1:
            tlp_def = args[0]
        elif 'tlp_def' in kwargs:
            tlp_def = kwargs['tlp_def']
        elif len(args) == 3:
            tlp_def = TLPInstance.from_integers(
                point_type=args[0],
                logical_number=args[1],
                parameter=args[2]
            )
        elif 'point_type' in kwargs and 'logical_number' in kwargs and 'parameter' in kwargs:
            tlp_def = TLPInstance.from_integers(
                point_type=kwargs['point_type'],
                logical_number=kwargs['logical_number'],
                parameter=kwargs['parameter']
            )
        else:
            raise ROCError('Invalid arguments supplied.')
        
        if tlp_def:
            request_data = ParameterRequestData(tlps=[tlp_def])
            response: Response[ResponseData] = await self.unary_opcode_request(request_data=request_data)
            data: ParameterData = self.validate_response(response_data=response.response_data, response_data_type=ParameterData)
            tlp_values: List[TLPValue] = self.get_named_values(data.values)
            return tlp_values[0]
        else:
            raise ROCDataError('Unable to construct TLP Instance.')
        


    @overload
    async def read_tlps(self, tlp_defs: List[TLPInstance]) -> TLPValues:
        """
        Retrieve TLP values.

        Args:
            tlp_defs (List[TLPInstance]): TLP definition objects.

        Returns:
            List[TLPValue]: TLP value objects.
        """
        ...

    @overload
    async def read_tlps(self, tlp_defs: List[Tuple[int, int, int]]) -> TLPValues:
        """
        Retrieve TLP values

        Args:
            tlp_defs (List[Tuple[int, int, int]]): List of tuples containing T, L, and P values.

        Returns:
            List[TLPValue]: TLP value objects.
        """
        ...

    async def read_tlps(self, *args, **kwargs) -> TLPValues:
        tlp_defs: Optional[List[TLPInstance]] = None

        # Parse args vs. kwargs
        if len(args) == 1:
            tlp_def_list = args[0]
        elif 'tlp_defs' in kwargs:
            tlp_def_list = kwargs['tlp_defs']
        else:
            raise ValueError('Invalid arguments supplied.')
        
        # Determine argument type
        if isinstance(tlp_def_list, list):
            if isinstance(tlp_def_list[0], tuple):
                tlp_defs = []
                for _type, _logical, _parameter in tlp_def_list:
                    tlp_defs.append(
                        TLPInstance.from_integers(
                            point_type=_type, 
                            logical_number=_logical,
                            parameter=_parameter
                        )
                    )
            elif isinstance(tlp_def_list[0], TLPInstance):
                tlp_defs = tlp_def_list
            else:
                raise ROCError('Invalid types within list.')
        else:
            raise ROCError('Argument provided not a list.')
    
        # Make opcode request
        if tlp_defs:
            request_data = ParameterRequestData(tlps=tlp_defs)
            response: Response[ResponseData] = await self.unary_opcode_request(request_data=request_data)
            data: ParameterData = self.validate_response(response_data=response.response_data, response_data_type=ParameterData)
            tlp_values: List[TLPValue] = self.get_named_values(data.values)
            return TLPValues(values=tlp_values, timestamp=datetime.now())
        else:
            raise ROCDataError('Unable to construct TLP Instance.')
        


    @overload
    async def read_contiguous_tlps(
        self, 
        starting_tlp: TLPInstance, 
        number_of_parameters: int
    ) -> TLPValues:
        """
        Read contiguous set of parameters from a given point type and logical number.

        Args:
            starting_tlp (TLPInstance): TLPInstance instance representing the point type, logical point, and starting parameter number.
            number_of_parameters (int): Number of parameters to request.

        Returns:
            TLPValues: Values object with value of the parameters requested.
        """
        ...

    @overload
    async def read_contiguous_tlps(
        self, 
        point_type: Type[PointType],
        logical_number: int,
        number_of_parameters: int,
        starting_parameter_number: int
    ) -> TLPValues:
        """
        Read contiguous set of parameters from a given point type and logical number.

        Args:
            point_type (Type[PointType]): PointType subclass.
            logical_number (int): Logical/Point number.
            number_of_parameters (int): Number of parameters to request.
            starting_parameter_number (int): Starting parameter number for the request.

        Returns:
            TLPValues: Values object with value of the parameters requested.
        """
        ...

    @overload
    async def read_contiguous_tlps(
        self, 
        point_type: int,
        logical_number: int,
        number_of_parameters: int,
        starting_parameter_number: int
    ) -> TLPValues:
        """
        Read contiguous set of parameters from a given point type and logical number.

        Args:
            point_type (int): Point type number.
            logical_number (int): Logical/Point number.
            number_of_parameters (int): Number of parameters to request.
            starting_parameter_number (int): Starting parameter number for the request.

        Returns:
            TLPValues: Values object with value of the parameters requested.
        """
        ...

    async def read_contiguous_tlps(self, *args, **kwargs) -> TLPValues:
        
        # Determine argument composition
        if len(args) == 2 or len(kwargs) == 2:
            if len(args) == 2:
                starting_tlp: TLPInstance = args[0]
                number_of_parameters: int = args[1]
            elif len(kwargs) == 2:
                starting_tlp: TLPInstance = kwargs['starting_tlp']
                number_of_parameters: int = kwargs['number_of_parameters']
            else:
                raise TypeError('Invalid arguments.')
            point_type_number: int = starting_tlp.point_type.point_type_number
            logical_number: int = starting_tlp.logical_number
            starting_parameter_number: int = starting_tlp.parameter.parameter_number
        elif len(args) == 4 or len(kwargs) == 4:
            if len(args) == 4:
                point_type_arg: int | Type[PointType] = args[0]
                logical_number: int = args[1]
                number_of_parameters: int = args[2]
                starting_parameter_number: int = args[3]
            elif len(kwargs) == 4:
                point_type_arg: int | Type[PointType] = kwargs['point_type']
                logical_number: int = kwargs['logical_number']
                number_of_parameters: int = kwargs['number_of_parameters']
                starting_parameter_number: int = kwargs['starting_parameter_number']
            else:
                raise ValueError('Invalid arguments.')

            if isinstance(point_type_arg, int):
                point_type_number: int = point_type_arg
            elif issubclass(point_type_arg, PointType):
                point_type_number: int = point_type_arg.point_type_number
            else:
                raise TypeError('Invalid arguments.')
        else:
            raise TypeError('Invalid arguments.')
    
        # Make opcode request
        request_data = SinglePointParameterRequestData(
            point_type=point_type_number, 
            logical_number=logical_number, 
            number_of_parameters=number_of_parameters, 
            starting_parameter_number=starting_parameter_number
        )
        response: Response[ResponseData] = await self.unary_opcode_request(request_data=request_data)
        data: SinglePointParameterData = self.validate_response(response_data=response.response_data, response_data_type=SinglePointParameterData)
        tlp_values: List[TLPValue] = self.get_named_values(data.values)
        return TLPValues(values=tlp_values, timestamp=datetime.now())



    async def stream_tlp(self, tlp_def: TLPInstance, poll_rate_ms: int) -> AsyncGenerator[TLPValue, None]:
        """
        Persistent value stream for provided TLP.

        Requests the TLP value at the provided interval and yields the value.

        Args:
            tlp_def (TLPInstance): TLP instance definition.
            poll_rate_ms (int): Poll rate in milliseconds at which to request value from ROC.

        Yields:
            TLPValue: TLP Value returned by Opcode request for a single poll cycle.
        """
        try:
            while True:
                self.logger.debug('Constructing TLP request.')
                request_data = ParameterRequestData(tlps=[tlp_def])
                self.logger.debug('Submitting TLP Opcode request.')
                response: Response[ResponseData] = await self.unary_opcode_request(request_data=request_data)
                self.logger.debug('Validating Opcode response.')
                data: ParameterData = self.validate_response(response_data=response.response_data, response_data_type=ParameterData)
                self.logger.debug('Yielding response data.')
                tlp_values: List[TLPValue] = self.get_named_values(data.values)
                yield tlp_values[0]
                self.logger.debug('Waiting for poll cycle.')
                await asyncio.sleep(poll_rate_ms / 1000)
        except asyncio.CancelledError:
            self.logger.warning('TLP Stream cancelled.')
            pass
        finally:
            self.logger.debug('Exiting TLP stream.')

    

    async def stream_tlps(self, tlp_defs: List[TLPInstance], poll_rate_ms: int) -> AsyncGenerator[List[TLPValue], None]:
        try:
            while True:
                self.logger.debug('Constructing TLP request.')
                request_data = ParameterRequestData(tlps=tlp_defs)
                self.logger.debug('Submitting TLP Opcode request.')
                response: Response = await self.unary_opcode_request(request_data=request_data)
                self.logger.debug('Validating Opcode response.')
                data: ParameterData = self.validate_response(response_data=response.response_data, response_data_type=ParameterData)
                self.logger.debug('Yielding response data.')
                tlp_values: List[TLPValue] = self.get_named_values(data.values)
                yield tlp_values
                self.logger.debug('Waiting for poll cycle.')
                await asyncio.sleep(poll_rate_ms / 1000)
        except asyncio.CancelledError:
            self.logger.warning('TLP Stream cancelled.')
            pass
        finally:
            self.logger.debug('Exiting TLP stream.')



    def get_named_values(self, tlp_values: List[TLPValue]) -> List[TLPValue]:
        """
        Helper function to populate TLPValue objects with tag names.

        Args:
            tlp_values (List[TLPValue]): List of TLPValues.

        Returns:
            List[TLPValue]: List of original TLPValues with tag name attribute populated.
        """
        if self.io_definition._defined:
            for tlp_value in tlp_values:
                tlp_value.tag_name = self.io_definition.get_point_definition(tlp_instance=tlp_value).point_tag_id
        return tlp_values




    async def get_system_config(self, store_internally=True) -> SystemConfigData:
        """
        Retrieve ROC system configuration.

        Returns:
            Response[SystemConfigResponseData]: System Configuration opcode response object.
        """
        request_data = SystemConfigRequestData()
        response: Response[ResponseData] = await self.unary_opcode_request(request_data=request_data)
        if response.response_data.data:
            if isinstance(response.response_data, SystemConfigResponseData):
                if store_internally:
                    self.system_config = response.response_data.data
                return response.response_data.data
            elif isinstance(response.response_data, OpcodeErrorResponseData):
                raise ROCErrorResponseError(errors=response.response_data.data.errors)
            else:
                raise ROCDataError(f'Unexpected return data type: {type(response.response_data)}')
        else:
            raise ROCEmptyDataError



    async def get_clock_time(self) -> datetime:
        """
        Retrieve current time from ROC device clock.

        Returns:
            datetime: Datetime object representing the current time of the ROC device clock.
        """
        self.logger.debug('Clock time requested. Constructing request.')
        request_data = ReadClockRequestData()
        self.logger.debug('Submitting Opcode request.')
        response: Response[ResponseData]= await self.unary_opcode_request(request_data=request_data)
        self.logger.debug('Validating Opcode response.')
        data: ReadClockData = self.validate_response(response_data=response.response_data, response_data_type=ReadClockData)
        self.logger.debug('Converting to datetime and returning.')
        return data.as_datetime



    async def get_io_logical_numbers(self) -> IOLocationData:
        """
        Retrieve I/O Logical Number configuration.

        Returns:
            Response[IOLocationResponseData]: I/O Location opcode response object.
        """
        self.logger.debug('Requesting I/O Logical Numbers.')
        request_data = IOLocationRequestData(request_type=IOLocationRequestType.LOGICAL_NUMBER)
        self.logger.debug('Submitting Opcode request.')
        response: Response = await self.unary_opcode_request(request_data=request_data)
        self.logger.debug('Validating Opcode response.')
        validated_response: IOLocationData = self.validate_response(response_data=response.response_data, response_data_type=IOLocationData)
        self.io_definition._logical_numbers_uploaded = True
        return validated_response



    async def get_io_point_types(self) -> IOLocationData:
        """
        Retrieve I/O Point Type configuration.

        Returns:
            Response[IOLocationResponseData]: I/O Location opcode response object.
        """
        self.logger.debug('Requesting I/O Point Types.')
        request_data = IOLocationRequestData(request_type=IOLocationRequestType.IO_POINT_TYPE)
        self.logger.debug('Submitting Opcode request.')
        response: Response = await self.unary_opcode_request(request_data=request_data)
        self.logger.debug('Validating Opcode response.')
        validated_response: IOLocationData = self.validate_response(response_data=response.response_data, response_data_type=IOLocationData)
        self.io_definition._point_types_uploaded = True
        return validated_response



    async def get_physical_io_definition(self) -> IODefinition:
        """
        Convenience function to retrieve both I/O Logical Numbers and Point Types.

        Returns:
            IODefinition: I/O definition object used to set self.io_definition.
        """
        self.logger.debug('Requesting Physical I/O Definition.')

        # Get I/O logical numbers
        self.logger.debug('Retrieving Logical I/O Numbers.')
        logical_numbers_response: IOLocationData = await self.get_io_logical_numbers()
        self.logger.debug('Logical I/O Numbers retrieved. Storing to I/O Definition.')
        logical_numbers: Dict[int, int] = logical_numbers_response.location_data
        for physical_location, logical_number in logical_numbers.items():
            self.io_definition.add_point_definition(
                physical_location=physical_location,
                point_definition=IOPointDefinition(
                    physical_location=physical_location, 
                    logical_number=logical_number
                )
            )

        # Get I/O point types
        self.logger.debug('Retrieving I/O Point Types.')
        io_point_types_response: IOLocationData = await self.get_io_point_types()
        self.logger.debug('I/O Point Types retrieved. Storing to I/O Definition.')
        io_point_types: Dict[int, int] = io_point_types_response.location_data
        for physical_location, point_type in io_point_types.items():
            self.io_definition.io_map[physical_location].point_type = point_type
        return self.io_definition



    async def get_io_point_tag_ids(self) -> IODefinition:
        """
        Retrieve Point Tag ID (tag name) for all configured TLPs.

        Returns:
            IODefinition: Updated I/O definition object used to update self.io_definition.
        """
        self.logger.debug('Retrieving Point Tag IDs.')
        tlp_defs: List[TLPInstance] = []
        if not self.io_definition._point_types_uploaded:
            raise ROCError('I/O definition has not been initialized. Please populate physical I/O definition first.')
        defined_tlps: List[IOPointDefinition] = self.io_definition.get_points_for_point_type(point_type_number=103)
        for io_def in defined_tlps:
            tlp = TLPInstance(
                parameter=io_def.get_point_tag_id_param(),
                point_type=io_def.get_point_type_object(),
                logical_number=io_def.physical_location
            )
            tlp_defs.append(tlp)
        tlp_values: TLPValues = await self.read_tlps(tlp_defs=tlp_defs)
        for value in tlp_values.values:
            self.io_definition.io_map[value.logical_number].point_tag_id = value.value
        self.io_definition._point_tag_ids_uploaded = True
        return self.io_definition
    


    async def initialize_io_definition(self) -> IODefinition:
        """
        Convenience method to populate both physical I/O definition and point tag IDs.

        Returns:
            IODefinition: Full I/O definition object used to set self.io_definition.
        """
        self.logger.debug('Initializing I/O Definition.')
        io_def: IODefinition = await self.get_physical_io_definition()
        io_def_with_names: IODefinition = await self.get_io_point_tag_ids()
        self.io_definition._defined = True
        return io_def_with_names
    


    async def get_opcode_table_definition(self, table_index: int) -> ConfigurableOpcodeTableDefinition:
        """
        Retrieve a definition model instance for the specified User Opcode table.

        Args:
            table_index (int): Index of the target User Opcode table.

        Returns:
            OpcodeTableDefinition: Model instance representing definition of User Opcode table.
        """

        self.logger.debug(f'Retrieving Opcode Table definition for table index {table_index}.')
        
        # Make opcode request
        tlp_values: TLPValues = await self.read_contiguous_tlps(
            point_type=PointTypes.CONFIGURABLE_OPCODE_TABLE, 
            logical_number=table_index, 
            number_of_parameters=44, 
            starting_parameter_number=1
        )

        # Loop through returned values
        entry_defs: List[OpcodeTableEntryDefinition] = []
        for val in tlp_values.values:

            # The data entry index is the same as the parameter number
            data_index: int = val.parameter.parameter_number
            
            # Filter out non-defined entries
            if val.value[0] > 0:

                # Get TLP Instance definition for TLP integers
                try:
                    mapping_tlp_def: TLPInstance = TLPInstance.from_integers(
                        point_type=val.value[0], 
                        logical_number=val.value[1], 
                        parameter=val.value[2]
                    )
                except PointTypeNotFoundError:
                    self.logger.error(f'Couldnt find point type for {val.value[0]}')
                    continue

                # Try to retrieve tag name from I/O Definition
                mapping_io_def: IOPointDefinition = self.io_definition.get_point_definition(mapping_tlp_def)
                if mapping_io_def.point_tag_id:
                    mapping_tlp_def.tag_name = mapping_io_def.point_tag_id
                
                # Create entry definition model instance
                entry_def = OpcodeTableEntryDefinition(table_index=table_index, data_index=data_index, tlp_definition=mapping_tlp_def)
                
                # Append to entry definition list
                entry_defs.append(entry_def)
        
        table_def = ConfigurableOpcodeTableDefinition(data_entry_definitions=entry_defs, table_index=table_index)
        return table_def
    

    async def initialize_configurable_opcode_definition(self) -> ConfigurableOpcodeTablesDefinition:
        """
        Retrieve User Opcode table definition for ALL tables.

        Returns:
            ConfigurableOpcodeDefinition: Model instance representing all User Opcode table definitions.
        """
        # There are a maximum of 16 User Opcode tables
        for i in range(0, 16):

            # Retrieve table definition
            table_def: ConfigurableOpcodeTableDefinition = await self.get_opcode_table_definition(table_index=i)
            
            # Store definition in internal attribute
            self.configurable_opcode_tables_definition.configurable_opcode_table_map[i] = table_def
        
        # Set "defined" flag
        self.configurable_opcode_tables_definition._defined = True
        
        return self.configurable_opcode_tables_definition
    

    async def get_history_segment_point_configuration(self, segment_index: int, point_number: int) -> HistorySegmentPointConfiguration:
        """
        Retrieve the configuration for a single History point.

        Args:
            segment_index (int): The numeric index of the history segment.
            point_number (int): The numeric index of the history point.

        Returns:
            HistorySegmentPointConfiguration: History point configuration model instance.
        """
        # Derive point type name from segment index
        point_type_name = f'HISTORY_SEGMENT_{segment_index}_POINT_CONFIGURATION'
        
        # Read contiguous parameters for config data
        values: TLPValues = await self.read_contiguous_tlps(
            point_type=PointTypes.get_point_type_by_name(point_type_name=point_type_name),
            logical_number=point_number,
            number_of_parameters=5,
            starting_parameter_number=0
        )

        # Generate TLP Instance from TLP integers for history log point
        history_point_tlp = values.values[2].value
        if history_point_tlp[0] == 0:
            history_log_point = None
        else:
            history_log_point = TLPInstance.from_integers(point_type=history_point_tlp[0], logical_number=history_point_tlp[1], parameter=history_point_tlp[2])
            if self.io_definition._defined:
                history_log_point.tag_name = self.io_definition.get_point_definition(tlp_instance=history_log_point).point_tag_id

        # Instantiate a point definition
        return HistorySegmentPointConfiguration(
            history_point_number=point_number,
            point_tag_id=values.values[0].value,
            parameter_description=values.values[1].value,
            history_log_point=history_log_point,
            archive_type=values.values[3].value,
            averaging_rate_type=values.values[4].value
        )
    

    async def get_history_segment_configuration(self, segment_index: int, include_point_definitions=True, include_undefined_points=True) -> HistorySegmentConfiguration:
        """
        Retrieve the configuration for a single History segment.

        Args:
            segment_index (int): The numeric index of the history segment.
            include_point_definitions (bool, optional): If True, the configuration for all points belonging to the history segment will also be read. Defaults to True.
            include_undefined_points (bool, optional): If True, the configuration for all undefined points will be included in the final configuration instance. If False, these 
                configurations are omitted. Defaults to True.

        Returns:
            HistorySegmentConfiguration: History segment configuration model instance.
        """
        # Read contiguous parameters for config data
        values: TLPValues = await self.read_contiguous_tlps(
            point_type=PointTypes.HISTORY_SEGMENT_CONFIGURATION,
            logical_number=segment_index,
            number_of_parameters=14,
            starting_parameter_number=0
        )

        # Generate TLP Instance from TLP integers for user-weighting TLP, if needed
        user_weighting_tlp_ints = values.values[13].value
        if user_weighting_tlp_ints[0] == 0:
            user_weighting_tlp = None
        else:
            user_weighting_tlp = TLPInstance.from_integers(
                point_type=user_weighting_tlp_ints[0], 
                logical_number=user_weighting_tlp_ints[1], 
                parameter=user_weighting_tlp_ints[2]
            )

        # Instantiate the segment definition
        segment_size: int = values.values[1].value
        segment_config = HistorySegmentConfiguration(
            segment_number=segment_index,
            segment_description=values.values[0].value,
            segment_size=segment_size,
            max_segment_size=values.values[2].value,
            periodic_entries=values.values[3].value,
            periodic_index=values.values[4].value,
            daily_entries=values.values[5].value,
            daily_index=values.values[6].value,
            periodic_sample_rate=values.values[7].value,
            contract_hour=values.values[8].value,
            on_off_switch=values.values[9].value,
            free_space=values.values[10].value,
            number_of_configured_points=values.values[12].value,
            user_weighting_tlp=user_weighting_tlp
        )

        # Populate point definitions if requested
        if include_point_definitions:
            for i in range(segment_size):
                point_config: HistorySegmentPointConfiguration = await self.get_history_segment_point_configuration(
                    segment_index=segment_index, 
                    point_number=i
                )
                
                # Filter out undefined points if requested
                if point_config.history_log_point is None and not(include_undefined_points):
                    continue
                else:
                    segment_config.point_configurations.append(point_config)

        return segment_config
    

    async def initialize_history_definition(self) -> HistoryDefinition:
        """
        Retrieve History definition for ALL history segments and points.

        The HistoryDefinition instance created is also stored internally to the ROCPlus client for access via the history_definition attribute.

        Returns:
            HistoryDefinition: Model instance representing all History segment and point definitions.
        """
        self.logger.info('Initializing History Definition.')
        segment_definitions: Dict[int, HistorySegmentConfiguration] = {}
        
        # There are a maximum of 13 History Segments
        for i in range(13):

            # Read the segment definition, including each point configuration within the segment
            segment_definition: HistorySegmentConfiguration = await self.get_history_segment_configuration(
                segment_index=i, 
                include_point_definitions=True, 
                include_undefined_points=True
            )

            # Add the segment definition to the segment definition map
            segment_definitions[i] = segment_definition
        
        # Store in internal attribute
        self.history_definition.history_configuration_map = segment_definitions
        
        return self.history_definition
    

    async def get_config_json(self) -> str:
        """
        Retrieve a JSON containing comprehensive ROC configuration data.

        Returns:
            str: JSON containing ROC configuration data. This includes System Configuration, I/O Configuration, User Opcode Table Configuration,
                and History Configuration.
        """
        # Initialize history definition if needed
        if not(self.history_definition._defined):
            await self.initialize_history_definition()

        # Initialize history definition if needed
        if not(self.io_definition._defined):
            await self.initialize_io_definition()
        
        # Initialize history definition if needed
        if not(self.configurable_opcode_tables_definition._defined):
            await self.initialize_configurable_opcode_definition()
        
        # Initialize history definition if needed
        if not(self.system_config):
            await self.get_system_config(store_internally=True)
        
        # Construct definition payload
        config_list = [
            self.history_definition.as_dict(),
            self.io_definition.as_dict(),
            self.configurable_opcode_tables_definition.as_dict(),
            self.system_config.model_dump() if self.system_config else None
        ]
        config_json: str = json.dumps(config_list, indent=2)
        
        return config_json