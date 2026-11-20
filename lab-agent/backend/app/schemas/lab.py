from datetime import time
from pydantic import Field, field_validator, model_validator
from pydantic import BaseModel, ConfigDict


class LabResponse(BaseModel):
    id: int
    name: str
    location: str | None = None
    capacity: int
    open_time: time | None = None
    close_time: time | None = None
    description: str | None = None
    img: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)


class LabCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    location: str | None = None
    capacity: int = Field(default=0, ge=0)
    open_time: time | None = None
    close_time: time | None = None
    description: str | None = None
    img: str | None = None
    status: int = Field(default=1, ge=0, le=1)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.open_time and self.close_time and self.open_time >= self.close_time:
            raise ValueError("开放时间必须早于关闭时间")
        return self


class LabUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    location: str | None = None
    capacity: int | None = Field(default=None, ge=0)
    open_time: time | None = None
    close_time: time | None = None
    description: str | None = None
    img: str | None = None
    status: int | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.open_time and self.close_time and self.open_time >= self.close_time:
            raise ValueError("开放时间必须早于关闭时间")
        return self
