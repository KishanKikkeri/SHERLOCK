"""SHERLOCK — Stage A: Weapon. New AER entity, separate from Property
per the handover's own node list (Property and Weapon are named
separately in Phase A5's target node list, not merged)."""

from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import WeaponType, PropertyStatus


class Weapon(Base):
    __tablename__ = "weapons"

    id = Column(Integer, primary_key=True)
    weapon_type = Column(Enum(WeaponType), nullable=False)
    description = Column(String, nullable=True)
    serial_number = Column(String, nullable=True)
    used_in_fir_id = Column(Integer, ForeignKey("firs.id"), nullable=True, index=True)
    recovered_from_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    status = Column(Enum(PropertyStatus), nullable=False, default=PropertyStatus.SEIZED)

    used_in_fir = relationship("FIR")
    recovered_from_person = relationship("Person")

    def __repr__(self):
        return f"<Weapon {self.weapon_type} ({self.status})>"
