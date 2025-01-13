import json

# Parameters
class_type = 'AI'
point_type = 103
point_type_desc = 'Analog Input'


# Codegen script
source_file_path = f'C:\\Users\\SHillis\\OneDrive - Coterra Energy\\Documents\\rocpy\\roc_docs\\point_type_{point_type}.json'
dest_file_path = f'C:\\Users\\SHillis\\OneDrive - Coterra Energy\\Documents\\rocpy\\roc_parameters\\{class_type.lower()}.py'

code_gen_string = 'from roc_parameters.base import PointType, TLPParameter\n'
code_gen_string += 'import roc_data_types as dt\n\n'
code_gen_string += f'class {class_type}(PointType):\n\n'
code_gen_string += f'    point_type = {point_type}\n\n'
code_gen_string += f"    point_type_desc = '{point_type_desc}'\n\n"

with open(source_file_path, 'r') as f:
    data = json.load(f)

for param in data:
    parameter_number = param['Param#']
    try:
        parameter_number = int(parameter_number)
    except:
        continue
    parameter_name: str = param['Name']
    access = param['Access']
    data_type_string = param['Data Type']
    length = param['Length']
    try:
        length = int(length)
    except:
        continue
    value_range = param['Range']
    parameter_desc = param['Description']

    parameter_title = parameter_name.upper().replace(' ', '_').replace('#', '_').replace('-', '_').replace('/','_').replace('(','_').replace(')','')

    class_string = f'    {parameter_title} = TLPParameter(\n'
    class_string += f'        parameter_number={parameter_number},\n'
    class_string += f"        parameter_desc='{parameter_name}',\n"
    class_string += f'        data_type=dt.{data_type_string},\n'
    class_string += f"        access='{access}',\n"
    class_string += f"        value_range='{value_range}',\n"
    class_string += f'        point_type=point_type,\n'
    class_string += f'        point_type_desc=point_type_desc\n'
    class_string += f'    )\n'
    class_string += f'    """{parameter_desc}"""\n\n'

    code_gen_string += class_string

with open(dest_file_path, 'w') as f:
    f.write(code_gen_string)