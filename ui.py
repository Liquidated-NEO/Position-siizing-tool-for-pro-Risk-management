from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from calculator import PositionCalculator
from risk import (
    AccountConfig,
    CalculationSnapshot,
    Direction,
    MarginMode,
    TradeConfig,
    money,
    number,
    to_decimal,
)


APP_NAME = "Crypto Futures Position Sizer"
PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
TRADES_FILE = PROJECT_ROOT / "trades.csv"


COLORS = {
    "bg": "#0B1020",
    "panel": "#11182D",
    "panel_alt": "#151E36",
    "field": "#0E1628",
    "border": "#263550",
    "text": "#E5ECF8",
    "muted": "#8EA0BC",
    "accent": "#38BDF8",
    "accent_hover": "#0EA5E9",
    "success": "#22C55E",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "purple": "#A78BFA",
}

FONTS = {
    "title": ("Segoe UI Semibold", 28),
    "subtitle": ("Segoe UI", 13),
    "section": ("Segoe UI Semibold", 15),
    "label": ("Segoe UI", 12),
    "input": ("Segoe UI", 13),
    "metric": ("Segoe UI Semibold", 22),
    "metric_label": ("Segoe UI", 12),
    "button": ("Segoe UI Semibold", 13),
}

DEFAULT_SETTINGS: dict[str, str] = {
    "account_balance": "10000",
    "available_balance": "10000",
    "risk_percent": "1",
    "max_margin_usage_percent": "35",
    "daily_loss_limit_percent": "3",
    "max_open_risk_percent": "2",
    "currency": "USDT",
    "symbol": "BTCUSDT",
    "direction": "Long",
    "margin_mode": "Isolated",
    "entry_price": "115000",
    "stop_loss_price": "113500",
    "take_profit_price": "119500",
    "leverage": "10",
    "maker_fee_percent": "0.02",
    "taker_fee_percent": "0.05",
    "slippage_percent": "0.01",
    "tick_size": "0.1",
    "lot_size": "0.001",
    "contract_multiplier": "1",
    "max_position_notional": "0",
    "min_risk_reward": "2",
    "liquidation_buffer_percent": "5",
    "maintenance_margin_percent": "0.5",
    "max_leverage_warning": "20",
}


class Card(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, title: str) -> None:
        super().__init__(
            master,
            fg_color=COLORS["panel"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=18,
        )
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title, font=FONTS["section"], text_color=COLORS["text"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=18,
            pady=(16, 10),
        )


class LabeledEntry(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str, variable: ctk.StringVar, suffix: str = "") -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=FONTS["label"], text_color=COLORS["muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 5),
        )
        entry = ctk.CTkEntry(
            self,
            textvariable=variable,
            height=38,
            fg_color=COLORS["field"],
            border_color=COLORS["border"],
            text_color=COLORS["text"],
            font=FONTS["input"],
        )
        entry.grid(row=1, column=0, sticky="ew")
        if suffix:
            ctk.CTkLabel(entry, text=suffix, font=FONTS["label"], text_color=COLORS["muted"]).place(
                relx=0.97,
                rely=0.5,
                anchor="e",
            )


class MetricCard(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str, accent: str) -> None:
        super().__init__(
            master,
            fg_color=COLORS["panel_alt"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=16,
        )
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=FONTS["metric_label"], text_color=COLORS["muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=14,
            pady=(12, 2),
        )
        self.value = ctk.CTkLabel(self, text="—", font=FONTS["metric"], text_color=COLORS[accent], anchor="w")
        self.value.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

    def set(self, text: str) -> None:
        self.value.configure(text=text)


class ResultRow(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(self, text=label, font=FONTS["label"], text_color=COLORS["muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=5,
        )
        self.value = ctk.CTkLabel(self, text="—", font=FONTS["label"], text_color=COLORS["text"], anchor="e")
        self.value.grid(row=0, column=1, sticky="e", pady=5)

    def set(self, text: str) -> None:
        self.value.configure(text=text)


def primary_button(master: ctk.CTkBaseClass, text: str, command: Any) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        height=42,
        corner_radius=14,
        fg_color=COLORS["accent"],
        hover_color=COLORS["accent_hover"],
        text_color="#04111F",
        font=FONTS["button"],
    )


def secondary_button(master: ctk.CTkBaseClass, text: str, command: Any) -> ctk.CTkButton:
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        height=42,
        corner_radius=14,
        fg_color=COLORS["panel_alt"],
        hover_color=COLORS["border"],
        border_color=COLORS["border"],
        border_width=1,
        text_color=COLORS["text"],
        font=FONTS["button"],
    )


class CryptoSizerApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__(fg_color=COLORS["bg"])

        self.calculator = PositionCalculator()
        self.last_snapshot: CalculationSnapshot | None = None
        self.settings = load_settings()
        self.vars = {key: ctk.StringVar(value=value) for key, value in self.settings.items()}
        self.status_var = ctk.StringVar(value="Ready")
        self.metric_cards: dict[str, MetricCard] = {}
        self.result_rows: dict[str, ResultRow] = {}

        self.title(APP_NAME)
        self.geometry("1280x820")
        self.minsize(1120, 740)

        self._build_layout()
        self.after(150, self.calculate)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 24))
        body.grid_columnconfigure((0, 1, 2), weight=1, uniform="body")
        body.grid_rowconfigure(0, weight=1)

        self._build_account_panel(body)
        self._build_trade_panel(body)
        self._build_results_panel(body)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 18))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=FONTS["title"],
            text_color=COLORS["text"],
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header,
            text="Risk-first sizing, fee-aware projections, liquidation buffer checks, and trade export.",
            font=FONTS["subtitle"],
            text_color=COLORS["muted"],
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))
        ctk.CTkLabel(
            header,
            textvariable=self.status_var,
            font=FONTS["label"],
            text_color=COLORS["accent"],
            fg_color=COLORS["panel"],
            corner_radius=999,
            padx=14,
            pady=7,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

    def _build_account_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=COLORS["border"])
        scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        scroll.grid_columnconfigure(0, weight=1)

        card = Card(scroll, "Account & Risk Controls")
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure((0, 1), weight=1)
        self._entry(card, "Account Balance", "account_balance", "$", 1, 0)
        self._entry(card, "Available Balance", "available_balance", "$", 1, 1)
        self._entry(card, "Risk Per Trade", "risk_percent", "%", 2, 0)
        self._entry(card, "Max Margin Usage", "max_margin_usage_percent", "%", 2, 1)
        self._entry(card, "Daily Loss Limit", "daily_loss_limit_percent", "%", 3, 0)
        self._entry(card, "Max Open Risk", "max_open_risk_percent", "%", 3, 1)

        presets = ctk.CTkFrame(card, fg_color="transparent")
        presets.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 18))
        presets.grid_columnconfigure((0, 1, 2, 3), weight=1)
        for index, risk in enumerate(("0.25", "0.5", "1", "2")):
            secondary_button(presets, f"{risk}%", lambda value=risk: self._set_risk_preset(value)).grid(
                row=0,
                column=index,
                sticky="ew",
                padx=4,
            )

        ctk.CTkLabel(
            scroll,
            text="Professional sizing keeps risk fixed first. Leverage only changes required margin.",
            font=FONTS["subtitle"],
            text_color=COLORS["muted"],
            fg_color=COLORS["panel"],
            corner_radius=16,
            wraplength=330,
            justify="left",
            padx=18,
            pady=16,
        ).grid(row=1, column=0, sticky="ew", pady=(14, 0))

    def _build_trade_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=COLORS["border"])
        scroll.grid(row=0, column=1, sticky="nsew", padx=10)
        scroll.grid_columnconfigure(0, weight=1)

        trade = Card(scroll, "Trade Setup")
        trade.grid(row=0, column=0, sticky="ew")
        trade.grid_columnconfigure((0, 1), weight=1)
        self._entry(trade, "Symbol", "symbol", "", 1, 0)
        self._entry(trade, "Leverage", "leverage", "×", 1, 1)

        self._segmented(trade, "Direction", "direction", [Direction.LONG.value, Direction.SHORT.value], 2, 0)
        self._segmented(trade, "Margin Mode", "margin_mode", [MarginMode.ISOLATED.value, MarginMode.CROSS.value], 2, 1)
        self._entry(trade, "Entry Price", "entry_price", "$", 4, 0)
        self._entry(trade, "Stop Loss", "stop_loss_price", "$", 4, 1)
        self._entry(trade, "Take Profit", "take_profit_price", "$", 5, 0)
        self._entry(trade, "Max Position Notional", "max_position_notional", "$", 5, 1)

        exchange = Card(scroll, "Exchange, Fees & Precision")
        exchange.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        exchange.grid_columnconfigure((0, 1), weight=1)
        self._entry(exchange, "Maker Fee", "maker_fee_percent", "%", 1, 0)
        self._entry(exchange, "Taker Fee", "taker_fee_percent", "%", 1, 1)
        self._entry(exchange, "Slippage", "slippage_percent", "%", 2, 0)
        self._entry(exchange, "Tick Size", "tick_size", "", 2, 1)
        self._entry(exchange, "Lot Size", "lot_size", "", 3, 0)
        self._entry(exchange, "Contract Multiplier", "contract_multiplier", "", 3, 1)
        self._entry(exchange, "Minimum R:R", "min_risk_reward", "", 4, 0)
        self._entry(exchange, "Liq. Buffer", "liquidation_buffer_percent", "%", 4, 1)
        self._entry(exchange, "Maintenance Margin", "maintenance_margin_percent", "%", 5, 0)
        self._entry(exchange, "Leverage Warning", "max_leverage_warning", "×", 5, 1)

        actions = ctk.CTkFrame(scroll, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", pady=(16, 0))
        actions.grid_columnconfigure((0, 1, 2), weight=1)
        primary_button(actions, "Calculate", self.calculate).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        secondary_button(actions, "Reset", self.reset).grid(row=0, column=1, sticky="ew", padx=6)
        secondary_button(actions, "Export Trade", self.export_trade).grid(row=0, column=2, sticky="ew", padx=(6, 0))

    def _build_results_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent", scrollbar_button_color=COLORS["border"])
        scroll.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        scroll.grid_columnconfigure(0, weight=1)

        metrics = Card(scroll, "Position Output")
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.grid_columnconfigure((0, 1), weight=1)
        specs = [
            ("position_size", "Position Size", "accent"),
            ("position_notional", "Position Value", "purple"),
            ("required_margin", "Margin Required", "warning"),
            ("max_loss", "Maximum Loss", "danger"),
            ("net_profit", "Net Profit", "success"),
            ("risk_reward", "Risk/Reward", "accent"),
        ]
        for index, (key, label, accent) in enumerate(specs):
            card = MetricCard(metrics, label, accent)
            card.grid(row=1 + index // 2, column=index % 2, sticky="ew", padx=8, pady=8)
            self.metric_cards[key] = card

        details = Card(scroll, "Detailed Breakdown")
        details.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        details.grid_columnconfigure(0, weight=1)
        rows = [
            ("risk_budget", "Risk Budget"),
            ("limiting_factor", "Sizing Limited By"),
            ("gross_profit", "Gross Profit"),
            ("open_fee", "Open Fee"),
            ("close_fee_at_stop", "Close Fee at Stop"),
            ("close_fee_at_target", "Close Fee at Target"),
            ("slippage_cost_at_stop", "Slippage at Stop"),
            ("slippage_cost_at_target", "Slippage at Target"),
            ("liquidation_price", "Estimated Liquidation"),
            ("liquidation_buffer", "Liquidation Buffer"),
            ("adjusted_prices", "Adjusted Prices"),
        ]
        for index, (key, label) in enumerate(rows, start=1):
            row = ResultRow(details, label)
            row.grid(row=index, column=0, sticky="ew", padx=18)
            self.result_rows[key] = row

        warnings_card = Card(scroll, "Risk Notes")
        warnings_card.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        warnings_card.grid_columnconfigure(0, weight=1)
        self.warnings_box = ctk.CTkTextbox(
            warnings_card,
            height=130,
            fg_color=COLORS["field"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=14,
            text_color=COLORS["text"],
            font=FONTS["label"],
            wrap="word",
        )
        self.warnings_box.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 18))
        self._set_warnings(["No calculation yet."])

    def _entry(self, parent: ctk.CTkFrame, label: str, key: str, suffix: str, row: int, column: int) -> None:
        field = LabeledEntry(parent, label, self.vars[key], suffix=suffix)
        field.grid(row=row, column=column, sticky="ew", padx=18, pady=8)

    def _segmented(
        self,
        parent: ctk.CTkFrame,
        label: str,
        key: str,
        values: list[str],
        row: int,
        column: int,
    ) -> None:
        ctk.CTkLabel(parent, text=label, font=FONTS["label"], text_color=COLORS["muted"], anchor="w").grid(
            row=row,
            column=column,
            sticky="ew",
            padx=18,
            pady=(8, 5),
        )
        ctk.CTkSegmentedButton(
            parent,
            values=values,
            variable=self.vars[key],
            height=38,
            fg_color=COLORS["field"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["field"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text"],
        ).grid(row=row + 1, column=column, sticky="ew", padx=18, pady=(0, 10))

    def calculate(self) -> None:
        try:
            account, trade = self._collect_inputs()
            snapshot = self.calculator.calculate(account, trade)
        except ValueError as exc:
            self.status_var.set("Input needs attention")
            messagebox.showerror("Check Inputs", str(exc))
            return

        self.last_snapshot = snapshot
        save_settings(self._settings_from_vars())
        self._render_result(snapshot)
        self.status_var.set("Calculated and saved")

    def export_trade(self) -> None:
        if self.last_snapshot is None:
            self.calculate()
        if self.last_snapshot is None:
            return

        append_trade(self.last_snapshot)
        self.status_var.set(f"Exported to {TRADES_FILE.name}")
        messagebox.showinfo("Trade Exported", f"Trade saved to:\n{TRADES_FILE}")

    def reset(self) -> None:
        save_settings(DEFAULT_SETTINGS)
        for key, value in DEFAULT_SETTINGS.items():
            self.vars[key].set(value)
        self.last_snapshot = None
        self._clear_results()
        self.status_var.set("Reset to defaults")
        self.after(100, self.calculate)

    def _collect_inputs(self) -> tuple[AccountConfig, TradeConfig]:
        values = {key: variable.get().strip() for key, variable in self.vars.items()}
        account = AccountConfig(
            account_balance=to_decimal(values["account_balance"], "Account balance"),
            available_balance=to_decimal(values["available_balance"], "Available balance"),
            risk_percent=to_decimal(values["risk_percent"], "Risk %"),
            max_margin_usage_percent=to_decimal(values["max_margin_usage_percent"], "Max margin usage %"),
            daily_loss_limit_percent=to_decimal(values["daily_loss_limit_percent"], "Daily loss limit %"),
            max_open_risk_percent=to_decimal(values["max_open_risk_percent"], "Max open risk %"),
            currency=values["currency"],
        )
        trade = TradeConfig(
            symbol=values["symbol"],
            direction=Direction(values["direction"]),
            margin_mode=MarginMode(values["margin_mode"]),
            entry_price=to_decimal(values["entry_price"], "Entry price"),
            stop_loss_price=to_decimal(values["stop_loss_price"], "Stop loss price"),
            take_profit_price=to_decimal(values["take_profit_price"], "Take profit price"),
            leverage=to_decimal(values["leverage"], "Leverage"),
            maker_fee_percent=to_decimal(values["maker_fee_percent"], "Maker fee %"),
            taker_fee_percent=to_decimal(values["taker_fee_percent"], "Taker fee %"),
            slippage_percent=to_decimal(values["slippage_percent"], "Slippage %"),
            tick_size=to_decimal(values["tick_size"], "Tick size"),
            lot_size=to_decimal(values["lot_size"], "Lot size"),
            contract_multiplier=to_decimal(values["contract_multiplier"], "Contract multiplier"),
            max_position_notional=to_decimal(values["max_position_notional"], "Max position notional"),
            min_risk_reward=to_decimal(values["min_risk_reward"], "Minimum risk/reward"),
            liquidation_buffer_percent=to_decimal(values["liquidation_buffer_percent"], "Liquidation buffer %"),
            maintenance_margin_percent=to_decimal(values["maintenance_margin_percent"], "Maintenance margin %"),
            max_leverage_warning=to_decimal(values["max_leverage_warning"], "Max leverage warning"),
        )
        return account, trade

    def _render_result(self, snapshot: CalculationSnapshot) -> None:
        result = snapshot.result
        trade = snapshot.trade
        base_asset = base_asset_from_symbol(result.symbol)

        self.metric_cards["position_size"].set(f"{number(result.position_size)} {base_asset}")
        self.metric_cards["position_notional"].set(money(result.position_notional))
        self.metric_cards["required_margin"].set(money(result.required_margin))
        self.metric_cards["max_loss"].set(money(result.max_loss))
        self.metric_cards["net_profit"].set(money(result.net_profit))
        self.metric_cards["risk_reward"].set(f"1 : {number(result.risk_reward, '0.01')}")

        self.result_rows["risk_budget"].set(money(result.risk_budget))
        self.result_rows["limiting_factor"].set(result.limiting_factor)
        self.result_rows["gross_profit"].set(money(result.gross_profit))
        self.result_rows["open_fee"].set(money(result.open_fee))
        self.result_rows["close_fee_at_stop"].set(money(result.close_fee_at_stop))
        self.result_rows["close_fee_at_target"].set(money(result.close_fee_at_target))
        self.result_rows["slippage_cost_at_stop"].set(money(result.slippage_cost_at_stop))
        self.result_rows["slippage_cost_at_target"].set(money(result.slippage_cost_at_target))
        self.result_rows["liquidation_price"].set(money(result.liquidation_price))
        self.result_rows["liquidation_buffer"].set(
            f"{money(result.liquidation_buffer_distance)} ({number(result.liquidation_buffer_percent_actual, '0.01')}%)"
        )
        self.result_rows["adjusted_prices"].set(
            f"E {number(trade.entry_price, '0.01')} / S {number(trade.stop_loss_price, '0.01')} / T {number(trade.take_profit_price, '0.01')}"
        )
        self._set_warnings(result.warnings)

    def _clear_results(self) -> None:
        for metric in self.metric_cards.values():
            metric.set("—")
        for row in self.result_rows.values():
            row.set("—")
        self._set_warnings(["No calculation yet."])

    def _set_warnings(self, warnings: list[str]) -> None:
        self.warnings_box.configure(state="normal")
        self.warnings_box.delete("1.0", "end")
        if warnings:
            self.warnings_box.insert("1.0", "\n".join(f"• {warning}" for warning in warnings))
        else:
            self.warnings_box.insert("1.0", "No risk warnings. Setup passes configured controls.")
        self.warnings_box.configure(state="disabled")

    def _settings_from_vars(self) -> dict[str, str]:
        return {key: variable.get() for key, variable in self.vars.items() if key in DEFAULT_SETTINGS}

    def _set_risk_preset(self, risk_percent: str) -> None:
        self.vars["risk_percent"].set(risk_percent)
        self.calculate()


def load_settings() -> dict[str, str]:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_SETTINGS.copy()

    if not isinstance(loaded, dict):
        return DEFAULT_SETTINGS.copy()

    settings = DEFAULT_SETTINGS.copy()
    settings.update({str(key): str(value) for key, value in loaded.items()})
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    clean_settings = {str(key): str(value) for key, value in settings.items()}
    SETTINGS_FILE.write_text(json.dumps(clean_settings, indent=2), encoding="utf-8")


def append_trade(snapshot: CalculationSnapshot) -> None:
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **flatten("account", asdict(snapshot.account)),
        **flatten("trade", asdict(snapshot.trade)),
        **flatten("result", asdict(snapshot.result)),
    }
    row["result_warnings"] = " | ".join(snapshot.result.warnings)
    row = {key: stringify(value) for key, value in row.items()}
    write_header = not TRADES_FILE.exists() or TRADES_FILE.stat().st_size == 0

    with TRADES_FILE.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(row.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def flatten(prefix: str, values: dict[str, Any]) -> dict[str, Any]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def stringify(value: Any) -> str:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    return str(value)


def base_asset_from_symbol(symbol: str) -> str:
    upper_symbol = symbol.upper()
    for quote in ("USDT", "USD", "USDC", "BUSD", "PERP"):
        if upper_symbol.endswith(quote):
            return upper_symbol[: -len(quote)] or "Contracts"
    return "Contracts"
