from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP

from risk import Direction, TradeConfig, percent_to_rate


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    units = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return units * step


def round_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    units = (value / step).to_integral_value(rounding=ROUND_HALF_UP)
    return units * step


def is_step_aligned(value: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return True
    return value == round_to_step(value, step)


def normalize_trade_prices(trade: TradeConfig, warnings: list[str]) -> TradeConfig:
    entry = round_to_step(trade.entry_price, trade.tick_size)
    stop = round_to_step(trade.stop_loss_price, trade.tick_size)
    target = round_to_step(trade.take_profit_price, trade.tick_size)

    if not is_step_aligned(trade.entry_price, trade.tick_size):
        warnings.append(f"Entry adjusted to tick size: {entry}")
    if not is_step_aligned(trade.stop_loss_price, trade.tick_size):
        warnings.append(f"Stop adjusted to tick size: {stop}")
    if not is_step_aligned(trade.take_profit_price, trade.tick_size):
        warnings.append(f"Target adjusted to tick size: {target}")

    return TradeConfig(
        symbol=trade.symbol,
        direction=trade.direction,
        margin_mode=trade.margin_mode,
        entry_price=entry,
        stop_loss_price=stop,
        take_profit_price=target,
        leverage=trade.leverage,
        maker_fee_percent=trade.maker_fee_percent,
        taker_fee_percent=trade.taker_fee_percent,
        slippage_percent=trade.slippage_percent,
        tick_size=trade.tick_size,
        lot_size=trade.lot_size,
        contract_multiplier=trade.contract_multiplier,
        max_position_notional=trade.max_position_notional,
        min_risk_reward=trade.min_risk_reward,
        liquidation_buffer_percent=trade.liquidation_buffer_percent,
        maintenance_margin_percent=trade.maintenance_margin_percent,
        max_leverage_warning=trade.max_leverage_warning,
    )


def estimate_liquidation_price(
    *,
    direction: Direction,
    entry_price: Decimal,
    leverage: Decimal,
    maintenance_margin_percent: Decimal,
) -> Decimal:
    maintenance_rate = percent_to_rate(maintenance_margin_percent)
    leverage_rate = Decimal("1") / leverage

    if direction == Direction.LONG:
        liquidation = entry_price * (Decimal("1") - leverage_rate + maintenance_rate)
    else:
        liquidation = entry_price * (Decimal("1") + leverage_rate - maintenance_rate)

    return max(liquidation, Decimal("0"))


def liquidation_buffer(
    *,
    direction: Direction,
    entry_price: Decimal,
    stop_loss_price: Decimal,
    liquidation_price: Decimal,
) -> tuple[Decimal, Decimal]:
    if direction == Direction.LONG:
        distance = stop_loss_price - liquidation_price
    else:
        distance = liquidation_price - stop_loss_price

    percent = Decimal("0") if entry_price == 0 else (distance / entry_price) * Decimal("100")
    return distance, percent
