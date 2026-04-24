from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel
from database import Base

class CertificationAuthority(Base):
    __tablename__ = "certification_authorities"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AuthorityCreate(BaseModel):
    name: str
    active: bool = True

class AuthorityRead(BaseModel):
    id: int
    name: str
    active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
