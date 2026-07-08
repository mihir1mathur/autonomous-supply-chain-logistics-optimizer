"""
VEHICLE MODEL  (table: vehicles)  -- the delivery FLEET.

Source: simulation/vehicles.csv (Week 2). Entirely SIMULATED - Olist has no
carrier/vehicle data. Each vehicle is based at a warehouse.

A vehicle carries packages along routes. Its capacity is a hard limit that
route planning (Week 3+ / OR-Tools later) must respect.
"""

from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database.connection import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    # PRIMARY KEY (e.g. "VEH-00001").
    vehicle_id = Column(String, primary_key=True)

    # FOREIGN KEY -> the home warehouse this vehicle is based at.
    warehouse_id = Column(String, ForeignKey("warehouses.warehouse_id"), index=True)

    # van / small_truck / medium_truck / large_truck.
    vehicle_type = Column(String, index=True)

    # Capacity limits (SIMULATED).
    capacity_kg = Column(Integer)
    capacity_packages = Column(Integer)

    # Where the vehicle currently is (starts at its home warehouse).
    current_location_city = Column(String)
    current_location_state = Column(String)

    # available / on_delivery / maintenance. Indexed: planners query free ones.
    availability_status = Column(String, index=True)

    # Cost and speed used to estimate route time/cost.
    cost_per_km = Column(Float)
    average_speed_kmph = Column(Integer)

    # RELATIONSHIPS.
    warehouse = relationship("Warehouse", back_populates="vehicles")
    # A vehicle can be assigned to many routes. The link lives on the route
    # side (route.vehicle_id) and is filled in LATER (OR-Tools, Week 3+).
    routes = relationship("DeliveryRoute", back_populates="vehicle")

    def __repr__(self):
        return f"<Vehicle {self.vehicle_id} ({self.vehicle_type}, {self.availability_status})>"
