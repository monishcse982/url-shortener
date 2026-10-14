import enum
import ipaddress
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class LinkPolicyType(enum.StrEnum):
    PUBLIC = "public"
    PASSWORD_PROTECTED = "password_protected"
    IP_RESTRICTED = "ip_restricted"


class LinkPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LinkPolicyType = LinkPolicyType.PUBLIC
    password: str | None = Field(default=None, min_length=1, max_length=256)
    ip_list: list[str] | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_policy_config(self) -> "LinkPolicy":
        if self.type == LinkPolicyType.PASSWORD_PROTECTED:
            if self.password is None:
                raise ValueError("password is required for password_protected policy")
            if self.ip_list is not None:
                raise ValueError("ip_list is only valid for ip_restricted policy")

        elif self.type == LinkPolicyType.IP_RESTRICTED:
            if self.ip_list is None:
                raise ValueError("ip_list is required for ip_restricted policy")
            if self.password is not None:
                raise ValueError("password is only valid for password_protected policy")

            for entry in self.ip_list:
                try:
                    ipaddress.ip_network(entry, strict=False)
                except ValueError as error:
                    raise ValueError(f"Invalid IP address or CIDR: {entry}") from error

        elif self.password is not None or self.ip_list is not None:
            raise ValueError("public policy does not accept password or ip_list")

        return self


class ShortenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=256)
    max_visits: int | None = Field(default=None, gt=0)
    ttl_seconds: int = Field(gt=0, le=60 * 60 * 24 * 30)
    short_code: str | None = Field(
        default=None,
        min_length=3,
        max_length=32,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    url: HttpUrl
    policy: LinkPolicy = Field(default_factory=LinkPolicy)


class ShortenResponse(BaseModel):
    shortened_url: str
    expires_at: datetime
