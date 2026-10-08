"""SQLAlchemy models for CargaExpress.

Table and column names follow the project ERDs:
  - "Modelo operativo del WMS" (cargaexpress_01_erd_wms.pdf)
  - "Capa de seguimiento de la torre" (cargaexpress_02_erd_torre.pdf)

The ERDs do not define data types, so the types below are technical decisions.
All timestamps are timezone-aware and stored in UTC.
"""

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSONB on PostgreSQL, plain JSON everywhere else (SQLite in the tests).
JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")
UTC_DATETIME = DateTime(timezone=True)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# WMS: catalogs
# --------------------------------------------------------------------------
class Brand(Base):
    __tablename__ = "brand"

    brand_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    es_premium: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class DistributionCenter(Base):
    __tablename__ = "distribution_center"

    cd_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(100), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)
    zona_horaria: Mapped[str] = mapped_column(String(50), nullable=False)


class ShippingType(Base):
    __tablename__ = "shipping_type"

    tipo_envio_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(50), nullable=False)


class Region(Base):
    __tablename__ = "region"

    region_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)


class Carrier(Base):
    __tablename__ = "carrier"
    __table_args__ = (
        CheckConstraint("modalidad IN ('A', 'B', 'C')", name="ck_carrier_modalidad"),
    )

    carrier_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    modalidad: Mapped[str] = mapped_column(String(1), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVO")


# --------------------------------------------------------------------------
# WMS: orders, picking, guides and dispatch
# --------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("brand_id", "referencia_marca", name="uq_orders_brand_ref"),
    )

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.brand_id", ondelete="RESTRICT"), nullable=False
    )
    cd_id: Mapped[int] = mapped_column(
        ForeignKey("distribution_center.cd_id", ondelete="RESTRICT"), nullable=False
    )
    tipo_envio_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_type.tipo_envio_id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        ForeignKey("region.region_id", ondelete="RESTRICT"), nullable=False
    )
    referencia_marca: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)


class Recipient(Base):
    """Personal data of the recipient. Isolated on purpose (RN-10)."""

    __tablename__ = "recipient"

    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str] = mapped_column(String(250), nullable=False)
    telefono: Mapped[str] = mapped_column(String(30), nullable=False)


class OrderLine(Base):
    __tablename__ = "order_line"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_order_line_cantidad"),)

    line_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    num_linea: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(String(30), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class PickingTask(Base):
    __tablename__ = "picking_task"

    picking_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    inicio: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    fin: Mapped[datetime | None] = mapped_column(UTC_DATETIME, nullable=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)


class PickingLine(Base):
    __tablename__ = "picking_line"
    __table_args__ = (
        CheckConstraint(
            "cant_alistada <= cant_solicitada", name="ck_picking_line_cantidades"
        ),
    )

    picking_id: Mapped[int] = mapped_column(
        ForeignKey("picking_task.picking_id", ondelete="CASCADE"), primary_key=True
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("order_line.line_id", ondelete="CASCADE"), primary_key=True
    )
    cant_solicitada: Mapped[int] = mapped_column(Integer, nullable=False)
    cant_alistada: Mapped[int] = mapped_column(Integer, nullable=False)


class ShippingLabel(Base):
    """One guide (tracking number). An order can have several (RN-07)."""

    __tablename__ = "shipping_label"
    __table_args__ = (
        UniqueConstraint("carrier_id", "numero_guia", name="uq_label_carrier_guia"),
    )

    label_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False
    )
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carrier.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    numero_guia: Mapped[str] = mapped_column(String(30), nullable=False)
    valor_flete: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class Dispatch(Base):
    __tablename__ = "dispatch"

    dispatch_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"),
        unique=True,  # 1:1 with the guide
        nullable=False,
    )
    despachado_en: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)


class LabelLine(Base):
    __tablename__ = "label_line"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_label_line_cantidad"),)

    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"), primary_key=True
    )
    line_id: Mapped[int] = mapped_column(
        ForeignKey("order_line.line_id", ondelete="CASCADE"), primary_key=True
    )
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)


# --------------------------------------------------------------------------
# Control tower: raw events, tracking and status normalization
# --------------------------------------------------------------------------
class RawEvent(Base):
    """Original carrier message. Never modified. The hash avoids duplicates."""

    __tablename__ = "raw_event"

    raw_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carrier.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    modalidad: Mapped[str] = mapped_column(String(1), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    recibido_en: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)


class TrackingEvent(Base):
    __tablename__ = "tracking_event"
    __table_args__ = (
        UniqueConstraint(
            "carrier_id",
            "label_id",
            "estado_canonico",
            "ocurrio_en",
            name="uq_tracking_event_natural_key",
        ),
    )

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_id: Mapped[int] = mapped_column(
        ForeignKey("raw_event.raw_id", ondelete="RESTRICT"), nullable=False
    )
    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"), nullable=False
    )
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carrier.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    estado_canonico: Mapped[str] = mapped_column(String(20), nullable=False)
    ocurrio_en: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    es_anomalia: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ShipmentStatus(Base):
    __tablename__ = "shipment_status"

    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    estado_actual: Mapped[str] = mapped_column(String(20), nullable=False)
    actualizado_en: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    novedad_abierta_desde: Mapped[datetime | None] = mapped_column(
        UTC_DATETIME, nullable=True
    )


class CarrierStatusMap(Base):
    """Configurable mapping from carrier status to canonical state (RN-01)."""

    __tablename__ = "carrier_status_map"

    map_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carrier.carrier_id", ondelete="RESTRICT"), nullable=False
    )
    estado_origen: Mapped[str] = mapped_column(String(50), nullable=False)
    estado_canonico: Mapped[str] = mapped_column(String(20), nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    vigente_hasta: Mapped[datetime | None] = mapped_column(UTC_DATETIME, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class UnmatchedEvent(Base):
    """Events for guides that do not exist in the WMS. No FK on purpose."""

    __tablename__ = "unmatched_event"

    unmatched_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_id: Mapped[int] = mapped_column(
        ForeignKey("raw_event.raw_id", ondelete="RESTRICT"), nullable=False
    )
    carrier_id: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_guia: Mapped[str] = mapped_column(String(30), nullable=False)
    motivo: Mapped[str] = mapped_column(String(100), nullable=False)


# --------------------------------------------------------------------------
# Control tower: SLA, penalties, settlements and compliance
# --------------------------------------------------------------------------
class SlaRule(Base):
    __tablename__ = "sla_rule"

    regla_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.brand_id", ondelete="RESTRICT"), nullable=False
    )
    tipo_envio_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_type.tipo_envio_id", ondelete="RESTRICT"), nullable=False
    )
    region_id: Mapped[int] = mapped_column(
        ForeignKey("region.region_id", ondelete="RESTRICT"), nullable=False
    )
    dias_habiles: Mapped[int] = mapped_column(Integer, nullable=False)


class ShipmentSla(Base):
    __tablename__ = "shipment_sla"

    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    fecha_limite: Mapped[datetime] = mapped_column(UTC_DATETIME, nullable=False)
    dias_retraso: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    responsable: Mapped[str | None] = mapped_column(String(20), nullable=True)
    en_riesgo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class CalendarDay(Base):
    __tablename__ = "calendar_day"

    pais: Mapped[str] = mapped_column(String(2), primary_key=True)
    fecha: Mapped[date] = mapped_column(Date, primary_key=True)
    es_habil: Mapped[bool] = mapped_column(Boolean, nullable=False)
    es_festivo: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hora_corte: Mapped[time] = mapped_column(Time, nullable=False)


class PenaltyRule(Base):
    __tablename__ = "penalty_rule"

    tramo_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dias_desde: Mapped[int] = mapped_column(Integer, nullable=False)
    dias_hasta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pct_flete: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)


class Settlement(Base):
    __tablename__ = "settlement"

    settlement_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brand.brand_id", ondelete="RESTRICT"), nullable=False
    )
    quincena_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    quincena_fin: Mapped[date] = mapped_column(Date, nullable=False)
    a_pagar_marca: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    a_cobrar_transportadora: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )
    neto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class Penalty(Base):
    __tablename__ = "penalty"

    penalty_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label_id: Mapped[int] = mapped_column(
        ForeignKey("shipping_label.label_id", ondelete="CASCADE"), nullable=False
    )
    dias_retraso: Mapped[int] = mapped_column(Integer, nullable=False)
    monto_marca: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    monto_traslado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    responsable: Mapped[str] = mapped_column(String(20), nullable=False)
    settlement_id: Mapped[int | None] = mapped_column(
        ForeignKey("settlement.settlement_id", ondelete="RESTRICT"), nullable=True
    )


class CarrierCompliance(Base):
    __tablename__ = "carrier_compliance"

    carrier_id: Mapped[int] = mapped_column(
        ForeignKey("carrier.carrier_id", ondelete="RESTRICT"), primary_key=True
    )
    quincena: Mapped[date] = mapped_column(Date, primary_key=True)
    cumplimiento_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    en_revision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
