from typing import Optional

from sqlmodel import Field, SQLModel


class AssignmentPersonOption(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: str
    area: str
    active: bool = True


class AssignmentResourceOption(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    type: str
    active: bool = True
