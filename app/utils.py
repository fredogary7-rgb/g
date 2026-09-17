"""Utilitaires partagés (monnaie, dates, références)."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


def to_dec(value) -> Decimal:
    """Convertit n'importe quelle valeur numérique en Decimal de façon sûre."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(str(value))


def money(value) -> str:
    """Formate un montant en FCFA (ex: 4000 -> '4 000 FCFA')."""
    v = to_dec(value)
    if v == v.to_integral():
        text = f"{v.quantize(Decimal('1'), rounding=ROUND_HALF_UP):,.0f}"
    else:
        text = f"{v:,.2f}"
    return f"{text.replace(',', ' ')} FCFA"


def number(value) -> str:
    """Formate un entier avec séparateur de milliers (espaces)."""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def int_amount(value) -> int:
    """Montant arrondi à l'entier le plus proche (adapté au FCFA)."""
    return int(to_dec(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt_date(value, with_time: bool = False) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        dt = value
    else:
        dt = value
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    pattern = "%d/%m/%Y %H:%M" if with_time else "%d/%m/%Y"
    return dt.strftime(pattern)


def timeago(value) -> str:
    """Affiche un délai relatif court en français."""
    if not value:
        return ""
    now = datetime.now(timezone.utc)
    if isinstance(value, datetime) and value.tzinfo is not None:
        delta = now - value
    else:
        delta = now - value.replace(tzinfo=timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "à l'instant"
    minutes = seconds // 60
    if minutes < 60:
        return f"il y a {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"il y a {hours} h"
    days = hours // 24
    if days < 30:
        return f"il y a {days} j"
    months = days // 30
    if months < 12:
        return f"il y a {months} mois"
    return f"il y a {days // 365} an(s)"
