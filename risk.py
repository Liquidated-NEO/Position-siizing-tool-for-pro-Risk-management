from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum


DECIMAL_HUNDRED = Decimal("100")


class Direction(StrEnum):
    LONG = "Long"
    SHORT = "Short"


class MarginMode(StrEnum):
    ISOLATED = "Isolated"
    CROSS = "Cross"


@dataclass(frozen=True)
class AccountConfig:
    account_balance: Decimal
    available_balance: Decimal
    risk_percent: Decimal
    max_margin_usage_percent: Decimal
    daily_loss_limit_percent: Decimal
    max_open_risk_percent: Decimal
    currency: str = "USDT"


@dataclass(frozen=True)
class TradeConfig:
    symbol: str
    direction: Direction
    margin_mode: MarginMode
    entry_price: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal
    leverage: Decimal
    maker_fee_percent: Decimal
    taker_fee_percent: Decimal
    slippage_percent: Decimal
    tick_size: Decimal
    lot_size: Decimal
    contract_multiplier: Decimal
    max_position_notional: Decimal
    min_risk_reward: Decimal
    liquidation_buffer_percent: Decimal
    maintenance_margin_percent: Decimal
    max_leverage_warning: Decimal


@dataclass(frozen=True)
class PositionResult:
    symbol: str
    direction: Direction
    margin_mode: MarginMode
    limiting_factor: str
    adjusted_entry_price: Decimal
    adjusted_stop_loss_price: Decimal
    adjusted_take_profit_price: Decimal
    position_size: Decimal
    position_notional: Decimal
    required_margin: Decimal
    risk_budget: Decimal
    max_loss: Decimal
    gross_profit: Decimal
    net_profit: Decimal
    risk_reward: Decimal
    open_fee: Decimal
    close_fee_at_stop: Decimal
    close_fee_at_target: Decimal
    slippage_cost_at_stop: Decimal
    slippage_cost_at_target: Decimal
    liquidation_price: Decimal
    liquidation_buffer_distance: Decimal
    liquidation_buffer_percent_actual: Decimal
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CalculationSnapshot:
    account: AccountConfig
    trade: TradeConfig
    result: PositionResult


def to_decimal(value: object, field_name: str) -> Decimal:
    if isinstance(value, Decimal):
        return value

    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required.")

    cleaned = (
        text.replace(",", "")
        .replace("$", "")
        .replace("%", "")
        .replace("×", "")
        .replace("x", "")
        .replace("X", "")
        .strip()
    )

    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a valid number.") from exc


def percent_to_rate(value: Decimal) -> Decimal:
    return value / DECIMAL_HUNDRED


def money(value: Decimal) -> str:
    return f"${value.quantize(Decimal('0.01')):,.2f}"


def number(value: Decimal, places: str = "0.00000001") -> str:
    return f"{value.quantize(Decimal(places)).normalize():f}"


def risk_budget(account: AccountConfig) -> tuple[str, Decimal]:
    risk_amount = account.account_balance * percent_to_rate(account.risk_percent)
    open_risk_cap = account.account_balance * percent_to_rate(account.max_open_risk_percent)
    daily_loss_cap = account.account_balance * percent_to_rate(account.daily_loss_limit_percent)

    candidates = [
        ("Risk %", risk_amount),
        ("Max open risk", open_risk_cap),
        ("Daily loss limit", daily_loss_cap),
    ]
    return min(candidates, key=lambda item: item[1])


def ensure_positive(value: Decimal, field_name: str) -> None:
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")


def ensure_non_negative(value: Decimal, field_name: str) -> None:
    if value < 0:
        raise ValueError(f"{field_name} cannot be negative.")


def validate_account(account: AccountConfig) -> None:
    ensure_positive(account.account_balance, "Account balance")
    ensure_positive(account.available_balance, "Available balance")
    ensure_positive(account.risk_percent, "Risk %")
    ensure_positive(account.max_margin_usage_percent, "Max margin usage %")
    ensure_positive(account.daily_loss_limit_percent, "Daily loss limit %")
    ensure_positive(account.max_open_risk_percent, "Max open risk %")

    if account.risk_percent > Decimal("100"):
        raise ValueError("Risk % cannot exceed 100%.")
    if account.max_margin_usage_percent > Decimal("100"):
        raise ValueError("Max margin usage % cannot exceed 100%.")


def validate_trade(trade: TradeConfig) -> None:
    if not trade.symbol.strip():
        raise ValueError("Symbol is required.")

    ensure_positive(trade.entry_price, "Entry price")
    ensure_positive(trade.stop_loss_price, "Stop loss price")
    ensure_positive(trade.take_profit_price, "Take profit price")
    ensure_positive(trade.leverage, "Leverage")
    ensure_positive(trade.tick_size, "Tick size")
    ensure_positive(trade.lot_size, "Lot size")
    ensure_positive(trade.contract_multiplier, "Contract multiplier")
    ensure_positive(trade.min_risk_reward, "Minimum risk/reward")
    ensure_positive(trade.liquidation_buffer_percent, "Liquidation buffer %")
    ensure_non_negative(trade.maker_fee_percent, "Maker fee %")
    ensure_non_negative(trade.taker_fee_percent, "Taker fee %")
    ensure_non_negative(trade.slippage_percent, "Slippage %")
    ensure_non_negative(trade.max_position_notional, "Max position notional")
    ensure_non_negative(trade.maintenance_margin_percent, "Maintenance margin %")
    ensure_positive(trade.max_leverage_warning, "Max leverage warning")

    if trade.direction == Direction.LONG:
        if trade.stop_loss_price >= trade.entry_price:
            raise ValueError("For a long trade, stop loss must be below entry.")
        if trade.take_profit_price <= trade.entry_price:
            raise ValueError("For a long trade, take profit must be above entry.")
    else:
        if trade.stop_loss_price <= trade.entry_price:
            raise ValueError("For a short trade, stop loss must be above entry.")
        if trade.take_profit_price >= trade.entry_price:
            raise ValueError("For a short trade, take profit must be below entry.")
