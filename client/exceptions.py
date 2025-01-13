from opcode_models.opcodes import OpcodeError
from typing import List

class ROCError(Exception):
    def __init__(self, *args):
        super().__init__(*args)

class ROCConnectionTimeout(ROCError):
    def __init__(self, *args):
        super().__init__(*args)

class ROCConnectionError(ROCError):
    def __init__(self, *args):
        super().__init__(*args)

class ROCOperationTimeout(ROCError):
    def __init__(self, *args):
        super().__init__(*args)

class ROCConfigError(ROCError):
    def __init__(self, *args):
        super().__init__(*args)

class ROCDataError(ROCError):
    def __init__(self, *args):
        super().__init__(*args)

class ROCEmptyDataError(ROCDataError):
    def __init__(self):
        super().__init__('Data length of 0 returned for Opcode request.')

class ROCErrorResponseError(ROCDataError):
    def __init__(self, errors: List[OpcodeError]):
        super().__init__(f'Errors returned in response to Opcode request: {errors}')