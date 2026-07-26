from __future__ import annotations

from decimal import Decimal

from exchange import (
    estimate_liquidation_price,
    floor_to_step,
    liquidation_buffer,
    normalize_trade_prices,
)
from risk import (
    AccountConfig,
    CalculationSnapshot,
    Direction,
    PositionResult,
    TradeConfig,
    percent_to_rate,
    risk_budget,
    validate_account,
    validate_trade,
)


class PositionCalculator:
    def calculate(self, account: AccountConfig, trade: TradeConfig) -> CalculationSnapshot:
        validate_account(account)
        validate_trade(trade)

        warnings: list[str] = []
        adjusted_trade = normalize_trade_prices(trade, warnings)
        validate_trade(adjusted_trade)

        risk_limit_name, risk_amount = risk_budget(account)
        open_fee_rate = percent_to_rate(adjusted_trade.taker_fee_percent)
        close_fee_rate = percent_to_rate(adjusted_trade.taker_fee_percent)
        slippage_rate = percent_to_rate(adjusted_trade.slippage_percent)

        stop_distance = abs(adjusted_trade.entry_price - adjusted_trade.stop_loss_price)
        target_distance = abs(adjusted_trade.take_profit_price - adjusted_trade.entry_price)
        risk_per_unit = (
            stop_distance
            + adjusted_trade.entry_price * open_fee_rate
            + adjusted_trade.stop_loss_price * close_fee_rate
            + (adjusted_trade.entry_price + adjusted_trade.stop_loss_price) * slippage_rate
        ) * adjusted_trade.contract_multiplier

        raw_position_size = risk_amount / risk_per_unit
        position_size = floor_to_step(raw_position_size, adjusted_trade.lot_size)
        limiting_factor = risk_limit_name

        margin_cap_size = self._margin_cap_size(account, adjusted_trade)
        if margin_cap_size < position_size:
            position_size = margin_cap_size
            limiting_factor = "Max margin usage"

        notional_cap_size = self._notional_cap_size(adjusted_trade)
        if notional_cap_size is not None and notional_cap_size < position_size:
            position_size = notional_cap_size
            limiting_factor = "Max position notional"

        if position_size <= 0:
            raise ValueError("Position size rounds to zero. Increase risk, reduce stop distance, or lower lot size.")

        position_notional = position_size * adjusted_trade.entry_price * adjusted_trade.contract_multiplier
        required_margin = position_notional / adjusted_trade.leverage

        open_fee = position_size * adjusted_trade.entry_price * adjusted_trade.contract_multiplier * open_fee_rate
        close_fee_at_stop = position_size * adjusted_trade.stop_loss_price * adjusted_trade.contract_multiplier * close_fee_rate
        close_fee_at_target = position_size * adjusted_trade.take_profit_price * adjusted_trade.contract_multiplier * close_fee_rate
        slippage_cost_at_stop = (
            position_size
            * (adjusted_trade.entry_price + adjusted_trade.stop_loss_price)
            * adjusted_trade.contract_multiplier
            * slippage_rate
        )
        slippage_cost_at_target = (
            position_size
            * (adjusted_trade.entry_price + adjusted_trade.take_profit_price)
            * adjusted_trade.contract_multiplier
            * slippage_rate
        )

        gross_loss = position_size * stop_distance * adjusted_trade.contract_multiplier
        max_loss = gross_loss + open_fee + close_fee_at_stop + slippage_cost_at_stop
        gross_profit = position_size * target_distance * adjusted_trade.contract_multiplier
        net_profit = gross_profit - open_fee - close_fee_at_target - slippage_cost_at_target
        risk_reward = Decimal("0") if max_loss == 0 else net_profit / max_loss

        liquidation_price = estimate_liquidation_price(
            direction=adjusted_trade.direction,
            entry_price=adjusted_trade.entry_price,
            leverage=adjusted_trade.leverage,
            maintenance_margin_percent=adjusted_trade.maintenance_margin_percent,
        )
        liquidation_buffer_distance, liquidation_buffer_percent_actual = liquidation_buffer(
            direction=adjusted_trade.direction,
            entry_price=adjusted_trade.entry_price,
            stop_loss_price=adjusted_trade.stop_loss_price,
            liquidation_price=liquidation_price,
        )

        self._append_warnings(
            account=account,
            trade=adjusted_trade,
            required_margin=required_margin,
            max_loss=max_loss,
            risk_reward=risk_reward,
            liquidation_buffer_percent_actual=liquidation_buffer_percent_actual,
            warnings=warnings,
        )

        result = PositionResult(
            symbol=adjusted_trade.symbol.upper().strip(),
            direction=adjusted_trade.direction,
            margin_mode=adjusted_trade.margin_mode,
            limiting_factor=limiting_factor,
            adjusted_entry_price=adjusted_trade.entry_price,
            adjusted_stop_loss_price=adjusted_trade.stop_loss_price,
            adjusted_take_profit_price=adjusted_trade.take_profit_price,
            position_size=position_size,
            position_notional=position_notional,
            required_margin=required_margin,
            risk_budget=risk_amount,
            max_loss=max_loss,
            gross_profit=gross_profit,
            net_profit=net_profit,
            risk_reward=risk_reward,
            open_fee=open_fee,
            close_fee_at_stop=close_fee_at_stop,
            close_fee_at_target=close_fee_at_target,
            slippage_cost_at_stop=slippage_cost_at_stop,
            slippage_cost_at_target=slippage_cost_at_target,
            liquidation_price=liquidation_price,
            liquidation_buffer_distance=liquidation_buffer_distance,
            liquidation_buffer_percent_actual=liquidation_buffer_percent_actual,
            warnings=warnings,
        )
        return CalculationSnapshot(account=account, trade=adjusted_trade, result=result)

    def _margin_cap_size(self, account: AccountConfig, trade: TradeConfig) -> Decimal:
        max_margin = account.available_balance * percent_to_rate(account.max_margin_usage_percent)
        max_notional = max_margin * trade.leverage
        raw_size = max_notional / (trade.entry_price * trade.contract_multiplier)
        return floor_to_step(raw_size, trade.lot_size)

    def _notional_cap_size(self, trade: TradeConfig) -> Decimal | None:
        if trade.max_position_notional <= 0:
            return None
        raw_size = trade.max_position_notional / (trade.entry_price * trade.contract_multiplier)
        return floor_to_step(raw_size, trade.lot_size)

    def _append_warnings(
        self,
        *,
        account: AccountConfig,
        trade: TradeConfig,
        required_margin: Decimal,
        max_loss: Decimal,
        risk_reward: Decimal,
        liquidation_buffer_percent_actual: Decimal,
        warnings: list[str],
    ) -> None:
        if trade.leverage > trade.max_leverage_warning:
            warnings.append(f"Leverage is above the warning threshold of {trade.max_leverage_warning}x.")

        if risk_reward < trade.min_risk_reward:
            warnings.append(f"Risk/reward is below the minimum target of {trade.min_risk_reward}:1.")

        max_margin = account.available_balance * percent_to_rate(account.max_margin_usage_percent)
        if required_margin > max_margin:
            warnings.append("Required margin exceeds max margin usage.")

        daily_loss_limit = account.account_balance * percent_to_rate(account.daily_loss_limit_percent)
        if max_loss > daily_loss_limit:
            warnings.append("Trade risk exceeds the configured daily loss limit.")

        if liquidation_buffer_percent_actual < trade.liquidation_buffer_percent:
            warnings.append("Stop is too close to the estimated liquidation price.")

        if trade.direction == Direction.LONG and liquidation_buffer_percent_actual <= 0:
            warnings.append("Long stop is beyond or at the estimated liquidation price.")
        if trade.direction == Direction.SHORT and liquidation_buffer_percent_actual <= 0:
            warnings.append("Short stop is beyond or at the estimated liquidation price.")
