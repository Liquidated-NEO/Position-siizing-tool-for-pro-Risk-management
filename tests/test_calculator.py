from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test_calculator import PositionCalculator
from risk import AccountConfig, Direction, MarginMode, TradeConfig


class PositionCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calculator = PositionCalculator()

    def account(self, **overrides: Decimal) -> AccountConfig:
        values = {
            "account_balance": Decimal("10000"),
            "available_balance": Decimal("10000"),
            "risk_percent": Decimal("1"),
            "max_margin_usage_percent": Decimal("100"),
            "daily_loss_limit_percent": Decimal("3"),
            "max_open_risk_percent": Decimal("2"),
        }
        values.update(overrides)
        return AccountConfig(currency="USDT", **values)

    def trade(self, **overrides: Decimal | Direction | str) -> TradeConfig:
        values = {
            "symbol": "BTCUSDT",
            "direction": Direction.LONG,
            "margin_mode": MarginMode.ISOLATED,
            "entry_price": Decimal("115000"),
            "stop_loss_price": Decimal("113500"),
            "take_profit_price": Decimal("119500"),
            "leverage": Decimal("10"),
            "maker_fee_percent": Decimal("0"),
            "taker_fee_percent": Decimal("0"),
            "slippage_percent": Decimal("0"),
            "tick_size": Decimal("0.1"),
            "lot_size": Decimal("0.001"),
            "contract_multiplier": Decimal("1"),
            "max_position_notional": Decimal("0"),
            "min_risk_reward": Decimal("2"),
            "liquidation_buffer_percent": Decimal("5"),
            "maintenance_margin_percent": Decimal("0.5"),
            "max_leverage_warning": Decimal("20"),
        }
        values.update(overrides)
        return TradeConfig(**values)

    def test_long_position_sizes_from_risk_not_leverage(self) -> None:
        snapshot = self.calculator.calculate(self.account(), self.trade())

        self.assertEqual(snapshot.result.position_size, Decimal("0.066"))
        self.assertEqual(snapshot.result.max_loss, Decimal("99.000"))
        self.assertEqual(snapshot.result.required_margin, Decimal("759.000"))
        self.assertEqual(snapshot.result.limiting_factor, "Risk %")

    def test_fees_and_slippage_reduce_position_size(self) -> None:
        clean = self.calculator.calculate(self.account(), self.trade())
        with_costs = self.calculator.calculate(
            self.account(),
            self.trade(taker_fee_percent=Decimal("0.05"), slippage_percent=Decimal("0.01")),
        )

        self.assertLess(with_costs.result.position_size, clean.result.position_size)
        self.assertLess(with_costs.result.max_loss, Decimal("100"))

    def test_short_position_is_supported(self) -> None:
        snapshot = self.calculator.calculate(
            self.account(),
            self.trade(
                direction=Direction.SHORT,
                entry_price=Decimal("100"),
                stop_loss_price=Decimal("105"),
                take_profit_price=Decimal("90"),
                leverage=Decimal("5"),
                lot_size=Decimal("0.01"),
            ),
        )

        self.assertEqual(snapshot.result.position_size, Decimal("20.00"))
        self.assertEqual(snapshot.result.position_notional, Decimal("2000.00"))
        self.assertEqual(snapshot.result.required_margin, Decimal("400.00"))

    def test_margin_cap_limits_position(self) -> None:
        snapshot = self.calculator.calculate(
            self.account(
                account_balance=Decimal("10000"),
                available_balance=Decimal("1000"),
                risk_percent=Decimal("10"),
                max_margin_usage_percent=Decimal("10"),
            ),
            self.trade(
                entry_price=Decimal("100"),
                stop_loss_price=Decimal("99"),
                take_profit_price=Decimal("103"),
                leverage=Decimal("2"),
                lot_size=Decimal("0.01"),
                min_risk_reward=Decimal("1"),
            ),
        )

        self.assertEqual(snapshot.result.position_size, Decimal("2.00"))
        self.assertEqual(snapshot.result.required_margin, Decimal("100.00"))
        self.assertEqual(snapshot.result.limiting_factor, "Max margin usage")

    def test_invalid_long_stop_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.calculator.calculate(self.account(), self.trade(stop_loss_price=Decimal("116000")))


if __name__ == "__main__":
    unittest.main()
