from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReservationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lab_id: int = Field(gt=0)
    equipment_id: int | None = Field(default=None, gt=0)
    date: date
    start_time: time
    end_time: time
    remark: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_interval(self):
        if self.start_time >= self.end_time:
            raise ValueError("预约结束时间必须晚于开始时间")
        if self.start_time.tzinfo or self.end_time.tzinfo:
            raise ValueError("预约时间使用实验室本地时间，不接受时区偏移")
        return self


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    type: str | None = None
    date: date
    start_time: time
    end_time: time
    remark: str | None = None
    status: int
    checked_in_at: datetime | None = None
    checked_out_at: datetime | None = None
    exception_reason: str | None = None
    reviewed_at: datetime | None = None
    review_result: int | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditReservationRequest(BaseModel):
    status: Literal[1, 2]


class ReservationConfirmationRequest(BaseModel):
    token: str = Field(min_length=40, max_length=256)


class ReservationExceptionRequest(BaseModel):
    action: Literal["complete", "interrupt"]
    reason: str = Field(min_length=3, max_length=255)
