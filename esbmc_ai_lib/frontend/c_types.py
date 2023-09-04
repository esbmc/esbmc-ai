_primitives_base_defaults: list[str] = [
    # Bool
    "bool",
    # Decimals
    "float",
    "double",
    "long double",
    # Char
    "char",
    "signed char",
    "unsigned char",
    # Int
    "int",
    "signed int",
    "unsigned int",
    # Short
    "short",
    "signed short",
    "unsigned short",
    # Short (int)
    "short int",
    "signed short int",
    "unsigned short int",
    # Long
    "long",
    "signed long",
    "unsigned long",
    # Long (int)
    "long int",
    "signed long int",
    "unsigned long int",
    # Long Long
    "long long",
    "signed long long",
    "unsigned long long",
    # Long Long (int)
    "long long int",
    "signed long long int",
    "unsigned long long int",
]
"""Assign the following values for each primitive data type."""


def is_primitive_type(type_name: str) -> bool:
    return type_name in _primitives_base_defaults
