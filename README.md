# rocpy
Open source driver for communication using the Emerson ROC/ROC Plus protocol.

## Creating a Client
A ROC client can be created using either (1) of (2) techniques.

The first method is to create a client instance directly and then call the connect() method. This approach requires that the close() method be called in order to clean up the connection.

```python
client = ROCPlusClient(
    ip='192.168.1.10',
    port=10001,
    roc_address=1,
    roc_group=2    
)
await client.connect()
value: TLPValue = await client.read_tlp(point_type=103, parameter=21, logical_number=1)
print(value.model_dump_json(indent=2))
await client.close()
```

The second approach is to use the provided async context manager. This will connect the client and automatically clean up the connection after exiting the async context.

```python
async with ROCPlusClient(
    ip='192.168.1.10',
    port=10001,
    roc_address=1,
    roc_group=2
).connect() as client:
    value: TLPValue = await client.read_tlp(point_type=103, parameter=21, logical_number=1)
    print(value.model_dump_json(indent=2))
```

All TLPs (ROC-specific data addresses) used by internal code and available for creation using this library are Pydantic models. On instantiation, there are several pieces of contextual information that get populated. For instance, the name of the parameter per the protocol documentation.

```
>>>tlp = TLPInstance.from_integers(point_type=103, parameter=21, logical_number=1)
>>>print(tlp.model_dump_json(indent=2))
{
  "parameter": {
    "parameter_number": 21,
    "parameter_name": "EU Value",
    "parameter_desc": "Value in Engineering Units.",
    "data_type": {
      "data_type_name": "FLOAT",
      "py_type": "float"
    },
    "access": "R/O",
    "value_range": "Any valid IEEE 754 float"
  },
  "point_type": {
    "point_type_name": "Analog Inputs",
    "point_type_number": 103
  },
  "logical_number": 1,
  "tag_name": null
}
```