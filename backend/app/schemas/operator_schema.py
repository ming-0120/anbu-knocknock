from pydantic import BaseModel


class NearbyOperator(BaseModel):
    operators_id: int
    name: str
    distance: float
    latitude: float
    longitude: float
    
class OperatorLogin(BaseModel):
    email: str
    password: str


class OperatorLoginResponse(BaseModel):
    access_token: str
    name: str
    role: str