from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Contact = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class SupplierCreate(BaseModel):
    name: Name
    contact: Contact | None = None


class SupplierUpdate(BaseModel):
    name: Name | None = None
    contact: Contact | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact: str | None
    is_active: bool
