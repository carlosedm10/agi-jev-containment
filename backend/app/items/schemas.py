from pydantic import BaseModel


class ItemRead(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}
