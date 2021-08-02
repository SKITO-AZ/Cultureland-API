from pydantic import BaseModel
from typing import List, Optional


class ChargePinBody(BaseModel):
    token: str
    pins: list

class TokenResult(BaseModel):
    token: str

class ChargePins(BaseModel):
    result : Optional[list] = []
    cash : Optional[int] = 0
    error : bool
    msg : Optional[str] = None
