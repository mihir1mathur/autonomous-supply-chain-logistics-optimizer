"""
DELIVERY ROUTE MODEL  (table: delivery_routes)  -- WAREHOUSE -> CUSTOMER trips.

Source: simulation/delivery_routes.csv (Week 2).
  - REAL: order, warehouse, customer and their coordinates.
  - COMPUTED: estimated distance / time / cost (haversine estimate).

A route ties together an order, the warehouse it ships from, and the customer
it goes to. The vehicle_id column is reserved for LATER (OR-Tools, Week 3+):
the simple Week 2 estimate does not assign a vehicle, so it stays NULL for now.
"""

from sqlalchemy import Column, Float, ForeignKey, String
from sqlalchemy.orm import relationship

from database.connection import Base


class DeliveryRoute(Base):
    __tablename__ = "delivery_routes"

    # PRIMARY KEY (e.g. "RT-000001").
    route_id = Column(String, primary_key=True)

    # FOREIGN KEYS - a route connects three real things.
    order_id = Column(String, ForeignKey("orders.order_id"), index=True)
    warehouse_id = Column(String, ForeignKey("warehouses.warehouse_id"), index=True)
    customer_id = Column(String, ForeignKey("customers.customer_id"), index=True)

    # FUTURE FOREIGN KEY: which vehicle runs this route. Nullable because the
    # Week 2 estimate has no vehicle assignment; the optimizer fills it later.
    vehicle_id = Column(String, ForeignKey("vehicles.vehicle_id"), nullable=True, index=True)

    # Endpoints (denormalized for convenience / quick display).
    source_city = Column(String)
    source_state = Column(String)
    destination_city = Column(String)
    destination_state = Column(String)
    source_latitude = Column(Float)
    source_longitude = Column(Float)
    destination_latitude = Column(Float)
    destination_longitude = Column(Float)

    # Estimates (COMPUTED in Week 2; the optimizer improves these later).
    estimated_distance_km = Column(Float)
    estimated_time_minutes = Column(Float)
    estimated_cost = Column(Float)

    # planned / in_transit / completed. Indexed: we filter by status.
    route_status = Column(String, index=True)

    # RELATIONSHIPS.
    order = relationship("Order", back_populates="delivery_routes")
    warehouse = relationship("Warehouse", back_populates="delivery_routes")
    customer = relationship("Customer", back_populates="delivery_routes")
    vehicle = relationship("Vehicle", back_populates="routes")
    # Disruptions that specifically delay THIS route (reserved for Week 7;
    # empty for now because Week 2 disruptions are area/warehouse level).
    disruptions = relationship("Disruption", back_populates="affected_route")

    def __repr__(self):
        return (
            f"<DeliveryRoute {self.route_id} {self.source_city}->{self.destination_city} "
            f"{self.estimated_distance_km}km ({self.route_status})>"
        )
