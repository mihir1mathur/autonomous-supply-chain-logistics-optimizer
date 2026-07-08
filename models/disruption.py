"""
DISRUPTION MODEL  (table: disruptions)  -- events that delay deliveries.

Source: simulation/disruptions.csv (Week 2). Entirely SIMULATED - Olist is
historical and has no live traffic/weather.

A disruption is placed in a real city/state. Warehouse-specific disruptions
(warehouse_overload / inventory_shortage) point at a warehouse; area-wide
ones (traffic / weather / road_closure) leave affected_warehouse_id NULL.

It can ALSO point at a specific delivery route (affected_route_id). The Week 2
simulation does not link disruptions to individual routes, so this stays NULL
for now; it is reserved so that later weeks (OR-Tools re-optimization, Week 7
disruption-driven replanning) can attach a disruption to the exact route it
delays without any schema change.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database.connection import Base


class Disruption(Base):
    __tablename__ = "disruptions"

    # PRIMARY KEY (e.g. "DIS-0001").
    disruption_id = Column(String, primary_key=True)

    # heavy_traffic / severe_weather / warehouse_overload /
    # inventory_shortage / road_closure. Indexed: we filter by type.
    disruption_type = Column(String, index=True)

    # low / medium / high / critical. Indexed: we filter by severity.
    severity = Column(String, index=True)

    # Where the event is happening (real place name).
    location_city = Column(String)
    location_state = Column(String, index=True)

    # OPTIONAL FOREIGN KEY -> warehouses. NULL for area-wide events.
    affected_warehouse_id = Column(
        String, ForeignKey("warehouses.warehouse_id"), nullable=True, index=True
    )

    # OPTIONAL FOREIGN KEY -> delivery_routes. Reserved for future
    # disruption-driven replanning (Week 7); NULL for now.
    affected_route_id = Column(
        String, ForeignKey("delivery_routes.route_id"), nullable=True, index=True
    )

    # When it starts/ends and how bad the delay is.
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    impact_description = Column(Text)
    estimated_delay_minutes = Column(Integer)

    # active / resolved / scheduled. Indexed: we query active disruptions.
    status = Column(String, index=True)

    # RELATIONSHIPS (each set only when the matching id is not NULL).
    affected_warehouse = relationship("Warehouse", back_populates="disruptions")
    affected_route = relationship("DeliveryRoute", back_populates="disruptions")

    def __repr__(self):
        return f"<Disruption {self.disruption_id} ({self.disruption_type}, {self.severity}, {self.status})>"
