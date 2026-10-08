"""Catalogs and configuration tables.

These tables are the same for every size (except brands and SLA rules, which
depend on the number of brands). They contain no randomness.
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from seed.config import CARRIER_ACTIVE, CUTOFF_HOUR
from seed.reference_data import (
    CALENDAR_FIRST_DAY,
    CALENDAR_LAST_DAY,
    CARRIER_COUNT,
    CARRIER_MODALITIES,
    COUNTRY_TZ,
    DISTRIBUTION_CENTERS,
    FAR_REGION_IDS,
    HOLIDAYS,
    PENALTY_RULES,
    REGIONS,
    SHIPPING_TYPES,
    STATUS_STYLES,
)

MAP_VALID_FROM = datetime(2026, 1, 1, tzinfo=timezone.utc)


def generate(ctx):
    _brands(ctx)
    _distribution_centers(ctx)
    _shipping_types(ctx)
    _regions(ctx)
    _carriers(ctx)
    _status_map(ctx)
    _calendar(ctx)
    _sla_rules(ctx)
    _penalty_rules(ctx)


def _brands(ctx):
    for brand_id in range(1, ctx.size.brands + 1):
        ctx.add(
            "brand",
            brand_id=brand_id,
            nombre=f"Brand {brand_id:03d}",
            es_premium=(brand_id - 1) % 5 == 0,  # brands 1, 6, 11, ... are premium
        )


def _distribution_centers(ctx):
    for name, city, country in DISTRIBUTION_CENTERS:
        cd_id = ctx.next_id("distribution_center")
        row = ctx.add(
            "distribution_center",
            cd_id=cd_id,
            nombre=name,
            ciudad=city,
            pais=country,
            zona_horaria=COUNTRY_TZ[country],
        )
        ctx.lookup.cds[cd_id] = row


def _shipping_types(ctx):
    for name, _days in SHIPPING_TYPES:
        ctx.add("shipping_type", tipo_envio_id=ctx.next_id("shipping_type"), nombre=name)


def _regions(ctx):
    for name, country in REGIONS:
        region_id = ctx.next_id("region")
        row = ctx.add("region", region_id=region_id, nombre=name, pais=country)
        ctx.lookup.regions[region_id] = row


def _carriers(ctx):
    for carrier_id in range(1, CARRIER_COUNT + 1):
        modalidad = CARRIER_MODALITIES[carrier_id - 1]
        ctx.add(
            "carrier",
            carrier_id=ctx.next_id("carrier"),
            nombre=f"Carrier {carrier_id:02d}",
            modalidad=modalidad,
            estado=CARRIER_ACTIVE,
        )
        # The "style" decides which status codes this carrier uses.
        ctx.lookup.carriers[carrier_id] = {
            "modalidad": modalidad,
            "style": (carrier_id - 1) % len(STATUS_STYLES),
        }


def _status_map(ctx):
    for carrier_id, info in ctx.lookup.carriers.items():
        for code, canonical in STATUS_STYLES[info["style"]]:
            ctx.add(
                "carrier_status_map",
                map_id=ctx.next_id("carrier_status_map"),
                carrier_id=carrier_id,
                estado_origen=code,
                estado_canonico=canonical,
                vigente_desde=MAP_VALID_FROM,
                vigente_hasta=None,
                version=1,
            )


def _calendar(ctx):
    for country in COUNTRY_TZ:
        holidays = set(HOLIDAYS[country])
        day = CALENDAR_FIRST_DAY
        while day <= CALENDAR_LAST_DAY:
            is_holiday = day in holidays
            ctx.add(
                "calendar_day",
                pais=country,
                fecha=day,
                es_habil=day.weekday() != 6 and not is_holiday,
                es_festivo=is_holiday,
                hora_corte=time(CUTOFF_HOUR, 0),
            )
            day += timedelta(days=1)


def _sla_rules(ctx):
    for brand_id in range(1, ctx.size.brands + 1):
        for tipo_id, (_name, base_days) in enumerate(SHIPPING_TYPES, start=1):
            for region_id in ctx.lookup.regions:
                days = base_days + (1 if region_id in FAR_REGION_IDS else 0)
                ctx.add(
                    "sla_rule",
                    regla_id=ctx.next_id("sla_rule"),
                    brand_id=brand_id,
                    tipo_envio_id=tipo_id,
                    region_id=region_id,
                    dias_habiles=days,
                )
                ctx.lookup.sla_days[(brand_id, tipo_id, region_id)] = days


def _penalty_rules(ctx):
    for days_from, days_to, pct in PENALTY_RULES:
        row = ctx.add(
            "penalty_rule",
            tramo_id=ctx.next_id("penalty_rule"),
            dias_desde=days_from,
            dias_hasta=days_to,
            pct_flete=pct,
        )
        ctx.lookup.penalty_rules.append(row)
