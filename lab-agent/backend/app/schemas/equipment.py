from pydantic import BaseModel, ConfigDict, Field


class EquipmentResponse(BaseModel):
    id: int
    lab_id: int
    lab_name: str
    name: str
    description: str | None = None
    img: str | None = None
    spec: str | None = None
    quantity: int
    status: int

    model_config = ConfigDict(from_attributes=True)


class EquipmentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    img: str | None = Field(default=None, max_length=200)
    spec: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=1, ge=1, le=10000)
    status: int = Field(default=1, ge=0, le=1)


class EquipmentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    img: str | None = Field(default=None, max_length=200)
    spec: str | None = Field(default=None, max_length=100)
    quantity: int | None = Field(default=None, ge=1, le=10000)
    status: int | None = Field(default=None, ge=0, le=2)
