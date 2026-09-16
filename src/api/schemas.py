from pydantic import BaseModel, Field


class DataInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)


class DataOutput(BaseModel):
    id: int
    title: str
    content: str
