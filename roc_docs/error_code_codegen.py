import json
import pathlib

current_dir = pathlib.Path().cwd()
file_path = current_dir / 'opcodes' / 'opcode_error_codes.json'
dest_path = current_dir / 'opcodes' / 'error_codes.py'

with open(file_path, 'r') as f:
    data = json.loads(f.read())

error_code_table = data['table']['rows']

code_gen_imports = 'from enum import Enum\nfrom opcodes.core import OpcodeErrorCode\n\n'
code_gen_enum_def = 'class OpcodeErrorCodes(Enum):\n'

def get_err_line(error_def: str):
    return f'    {error_def}\n'

error_lines = ''
for row in error_code_table:
    error_code = row['Error Code']
    description = row['Description']
    byte_desc = row['Byte that caused error']

    error_var = '_' + str(error_code)
    instance_str = f"OpcodeErrorCode(error_code={error_code}, error_description='{description}', cause_byte_description='{byte_desc}')"
    error_def = f'{error_var} = {instance_str}'
    error_lines += get_err_line(error_def)

code_gen = f'{code_gen_imports}{code_gen_enum_def}{error_lines}'

with open(dest_path, 'w') as f:
    f.write(code_gen)