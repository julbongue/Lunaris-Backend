from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApiModel(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class TimeRange(ApiModel):
    start_time: datetime = Field(description="Inclusive UTC start time.")
    stop_time: datetime = Field(description="Inclusive UTC stop time.")
    step_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="Sampling interval in minutes.",
    )

    @field_validator("start_time", "stop_time")
    @classmethod
    def _normalize_to_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def _validate_order(self) -> TimeRange:
        if self.stop_time <= self.start_time:
            raise ValueError("stop_time must be after start_time")
        return self
