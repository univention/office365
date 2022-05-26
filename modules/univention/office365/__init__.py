from typing import Union


def bool_from_bytes(value):
	# type: (Union[bytes, str,int,bool]) -> None
	return bool(int(value))