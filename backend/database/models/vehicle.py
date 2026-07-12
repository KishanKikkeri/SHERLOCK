"""SHERLOCK — Stage A: Vehicle. Unchanged shape from the legacy schema,
plus an optional `used_in_fir_id` so the new USES graph edge (Phase A5)
has something to source from when a vehicle is tied to a specific case."""

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from backend.database.config import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    registration_number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    vehicle_type = Column(String, nullable=False)
    used_in_fir_id = Column(Integer, ForeignKey("firs.id"), nullable=True, index=True)
    seized = Column(Boolean, nullable=False, default=False)

    owner = relationship("Person", back_populates="vehicles")
    used_in_fir = relationship("FIR")

    def __repr__(self):
        return f"<Vehicle {self.registration_number}>"
