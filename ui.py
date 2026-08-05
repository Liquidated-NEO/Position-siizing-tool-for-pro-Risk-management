from __future__ import annotations

import csv
import json
import threading
import requests
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


APP_NAME = "PRO SIZER TERMINAL"
PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_FILE = PROJECT_ROOT / "settings.json"
TRADES_FILE = PROJECT_ROOT / "trades.csv"

COLORS = {
    "bg": "#05070A",
    "panel": "#0B1016",
    "panel_alt": "#111820",
    "border": "#1E293B",
    "text_primary": "#FFFFFF",
    "text_muted": "#64748B",
    "accent": "#3B82F6",
    "accent_hover": "#2563EB",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "purple": "#8B5CF6",
}

FONTS = {
    "title": ("Segoe UI", 24, "bold"),
    "subtitle": ("Segoe UI", 12),
    "section": ("Segoe UI", 14, "bold"),
    "label": ("Segoe UI", 12),
    "input": ("Segoe UI", 14, "bold"),
    "metric": ("Consolas", 26, "bold"),
    "metric_label": ("Segoe UI", 11, "bold"),
    "button": ("Segoe UI", 12, "bold"),
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
            corner_radius=8,
        )
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=title.upper(), font=FONTS["section"], text_color=COLORS["text_muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=16,
            pady=(12, 8),
        )


class LabeledEntry(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str, variable: ctk.StringVar, suffix: str = "", update_callback: Any = None) -> None:
        super().__init__(master, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label, font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            pady=(0, 2),
        )
        entry = ctk.CTkEntry(
            self,
            textvariable=variable,
            height=34,
            fg_color=COLORS["panel_alt"],
            border_width=0,
            text_color=COLORS["text_primary"],
            font=FONTS["input"],
        )
        entry.grid(row=1, column=0, sticky="ew")
        
        if update_callback:
            variable.trace_add("write", lambda *args: update_callback())
            
        if suffix:
            ctk.CTkLabel(entry, text=suffix, font=FONTS["label"], text_color=COLORS["text_muted"]).place(
                relx=0.96,
                rely=0.5,
                anchor="e",
            )


class MetricCard(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkBaseClass, label: str, accent: str) -> None:
        super().__init__(
            master,
            fg_color=COLORS["panel_alt"],
            corner_radius=6,
        )
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=label.upper(), font=FONTS["metric_label"], text_color=COLORS["text_muted"], anchor="w").grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(8, 0),
        )
        self.value = ctk.CTkLabel(self, text="—", font=FONTS["metric"], text_color=COLORS[accent], anchor="w")
        self.value.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))

    def set(self, text: str) -> None:
        self.value.configure(text=text)


class CryptoSizerApp(ctk.CTk):
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=COLORS["bg"])

        self.calculator = PositionCalculator()
        self.last_snapshot: CalculationSnapshot | None = None
        self.settings = load_settings()
        self.vars = {key: ctk.StringVar(value=value) for key, value in self.settings.items()}
        self.status_var = ctk.StringVar(value="SYSTEM READY")
        self.metric_cards: dict[str, MetricCard] = {}
        
        self.title(APP_NAME)
        self.geometry("1400x860")
        self.minsize(1200, 780)

        self._build_layout()
        self.after(150, self.calculate)

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build_header()

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, weight=2)
        body.grid_rowconfigure(0, weight=1)

        self._build_account_panel(body)
        self._build_trade_panel(body)
        self._build_results_panel(body)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=16)
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text=APP_NAME,
            font=FONTS["title"],
            text_color=COLORS["text_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header,
            textvariable=self.status_var,
            font=FONTS["label"],
            text_color=COLORS["accent"],
            anchor="e"
        ).grid(row=0, column=1, sticky="e")

    def _build_account_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        scroll.grid_columnconfigure(0, weight=1)

        card = Card(scroll, "Risk Parameters")
        card.grid(row=0, column=0, sticky="ew")
        card.grid_columnconfigure((0, 1), weight=1)
        
        self._entry(card, "Account Balance", "account_balance", "$", 1, 0)
        self._entry(card, "Available Balance", "available_balance", "$", 1, 1)
        self._entry(card, "Risk Per Trade", "risk_percent", "%", 2, 0)
        self._entry(card, "Max Margin Use", "max_margin_usage_percent", "%", 2, 1)
        self._entry(card, "Daily Loss Limit", "daily_loss_limit_percent", "%", 3, 0)
        self._entry(card, "Max Open Risk", "max_open_risk_percent", "%", 3, 1)

        exc = Card(scroll, "Exchange Specs")
        exc.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        exc.grid_columnconfigure((0, 1), weight=1)
        self._entry(exc, "Maker Fee", "maker_fee_percent", "%", 1, 0)
        self._entry(exc, "Taker Fee", "taker_fee_percent", "%", 1, 1)
        self._entry(exc, "Slippage", "slippage_percent", "%", 2, 0)
        self._entry(exc, "Tick Size", "tick_size", "", 2, 1)
        self._entry(exc, "Lot Size", "lot_size", "", 3, 0)
        self._entry(exc, "Multiplier", "contract_multiplier", "", 3, 1)

    def _build_trade_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=1, sticky="nsew", padx=8)
        scroll.grid_columnconfigure(0, weight=1)

        trade = Card(scroll, "Execution")
        trade.grid(row=0, column=0, sticky="ew")
        trade.grid_columnconfigure((0, 1), weight=1)
        
        self._entry(trade, "Symbol", "symbol", "", 1, 0)
        self._entry(trade, "Leverage", "leverage", "×", 1, 1)
        self._segmented(trade, "Direction", "direction", [Direction.LONG.value, Direction.SHORT.value], 2, 0)
        self._segmented(trade, "Margin Mode", "margin_mode", [MarginMode.ISOLATED.value, MarginMode.CROSS.value], 2, 1)
        
        entry_frame = ctk.CTkFrame(trade, fg_color="transparent")
        entry_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=6)
        entry_frame.grid_columnconfigure(0, weight=1)
        
        LabeledEntry(entry_frame, "Entry Price", self.vars["entry_price"], suffix="$", update_callback=self._schedule_calc).grid(row=0, column=0, sticky="ew")
        
        ctk.CTkButton(
            entry_frame, 
            text="GET LIVE", 
            command=self.fetch_bybit_price, 
            width=60, 
            height=28, 
            fg_color=COLORS["accent"], 
            text_color="#FFFFFF",
            font=FONTS["button"]
        ).grid(row=0, column=1, padx=(6, 0), sticky="s", pady=(0, 2))

        self._entry(trade, "Stop Loss", "stop_loss_price", "$", 3, 1)
        self._entry(trade, "Take Profit", "take_profit_price", "$", 4, 0)
        self._entry(trade, "Max Position Size", "max_position_notional", "$", 4, 1)

        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(16, 0))
        btn_frame.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(btn_frame, text="EXPORT TRADE", command=self.export_trade, height=40, fg_color=COLORS["panel"], text_color=COLORS["text_primary"], font=FONTS["button"]).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(btn_frame, text="RESET", command=self.reset, height=40, fg_color=COLORS["danger"], text_color=COLORS["text_primary"], font=FONTS["button"]).grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_results_panel(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        scroll.grid_columnconfigure(0, weight=1)

        metrics = Card(scroll, "Execution Output")
        metrics.grid(row=0, column=0, sticky="ew")
        metrics.grid_columnconfigure((0, 1), weight=1)
        
        specs = [
            ("position_size", "Position Size (Units)", "accent"),
            ("position_notional", "Total Value ($)", "purple"),
            ("required_margin", "Margin Required", "warning"),
            ("max_loss", "Maximum Risk", "danger"),
            ("net_profit", "Net Profit", "success"),
            ("risk_reward", "R:R Ratio", "accent"),
        ]
        for index, (key, label, accent) in enumerate(specs):
            card = MetricCard(metrics, label, accent)
            card.grid(row=1 + index // 2, column=index % 2, sticky="ew", padx=6, pady=6)
            self.metric_cards[key] = card

        warnings_card = Card(scroll, "Risk Diagnostics")
        warnings_card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        warnings_card.grid_columnconfigure(0, weight=1)
        self.warnings_box = ctk.CTkTextbox(
            warnings_card,
            height=140,
            fg_color=COLORS["panel_alt"],
            border_width=0,
            text_color=COLORS["warning"],
            font=FONTS["label"],
            wrap="word",
        )
        self.warnings_box.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))

    def _entry(self, parent: ctk.CTkFrame, label: str, key: str, suffix: str, row: int, column: int) -> None:
        field = LabeledEntry(parent, label, self.vars[key], suffix=suffix, update_callback=self._schedule_calc)
        field.grid(row=row, column=column, sticky="ew", padx=12, pady=6)

    def _segmented(self, parent: ctk.CTkFrame, label: str, key: str, values: list[str], row: int, column: int) -> None:
        ctk.CTkLabel(parent, text=label, font=FONTS["label"], text_color=COLORS["text_muted"], anchor="w").grid(row=row, column=column, sticky="ew", padx=12, pady=(6, 2))
        seg = ctk.CTkSegmentedButton(
            parent,
            values=values,
            variable=self.vars[key],
            height=32,
            fg_color=COLORS["panel_alt"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_hover"],
            unselected_color=COLORS["panel_alt"],
            text_color=COLORS["text_primary"],
            command=lambda _: self._schedule_calc()
        )
        seg.grid(row=row + 1, column=column, sticky="ew", padx=12, pady=(0, 6))

    def _schedule_calc(self) -> None:
        if hasattr(self, '_calc_timer'):
            self.after_cancel(self._calc_timer)
        self._calc_timer = self.after(300, self.calculate)

    def fetch_bybit_price(self) -> None:
        symbol = self.vars["symbol"].get().strip().upper()
        if not symbol:
            self._set_warnings(["Cannot fetch price: Symbol is empty."])
            return

        self.status_var.set("FETCHING BYBIT PRICE...")

        def api_task():
            try:
                url = f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}"
                response = requests.get(url, timeout=5).json()
                
                if response.get("retCode") == 0 and response.get("result", {}).get("list"):
                    last_price = response["result"]["list"][0]["lastPrice"]
                    self.after(0, lambda: self._update_entry_price(last_price))
                else:
                    msg = response.get("retMsg", "Unknown API error")
                    self.after(0, lambda: self._set_warnings([f"Bybit API Error: {msg}"]))
                    self.after(0, lambda: self.status_var.set("API ERROR"))
            
            except Exception as e:
                self.after(0, lambda: self._set_warnings([f"Network Error: {str(e)}"]))
                self.after(0, lambda: self.status_var.set("NETWORK ERROR"))

        threading.Thread(target=api_task, daemon=True).start()

    def _update_entry_price(self, price: str) -> None:
        self.vars["entry_price"].set(price)
        self.status_var.set("PRICE UPDATED")
        self.calculate()

    def calculate(self) -> None:
        try:
            account, trade = self._collect_inputs()
            snapshot = self.calculator.calculate(account, trade)
        except ValueError as exc:
            self.status_var.set("AWAITING VALID INPUT")
            self._set_warnings([str(exc)])
            return

        self.last_snapshot = snapshot
        save_settings(self._settings_from_vars())
        self._render_result(snapshot)
        self.status_var.set("CALCULATED")

    def export_trade(self) -> None:
        if self.last_snapshot is None:
            return
        append_trade(self.last_snapshot)
        self.status_var.set(f"EXPORTED TO {TRADES_FILE.name}")
        messagebox.showinfo("Export Success", f"Trade saved to {TRADES_FILE.name}")

    def reset(self) -> None:
        for key, value in DEFAULT_SETTINGS.items():
            self.vars[key].set(value)
        self.calculate()

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
        
        self.metric_cards["position_size"].set(number(result.position_size))
        self.metric_cards["position_notional"].set(money(result.position_notional))
        self.metric_cards["required_margin"].set(money(result.required_margin))
        self.metric_cards["max_loss"].set(money(result.max_loss))
        self.metric_cards["net_profit"].set(money(result.net_profit))
        self.metric_cards["risk_reward"].set(f"1 : {number(result.risk_reward, '0.01')}")

        warnings = list(result.warnings)
        warnings.append(f"Sizing limited by: {result.limiting_factor.upper()}")
        warnings.append(f"Est. Liq Price: {money(result.liquidation_price)} (Buffer: {number(result.liquidation_buffer_percent_actual, '0.01')}%)")
        self._set_warnings(warnings)

    def _set_warnings(self, warnings: list[str]) -> None:
        self.warnings_box.configure(state="normal")
        self.warnings_box.delete("1.0", "end")
        if warnings:
            self.warnings_box.insert("1.0", "\n".join(f"> {warning}" for warning in warnings))
        else:
            self.warnings_box.insert("1.0", "> System nominal. No risk alerts.")
        self.warnings_box.configure(state="disabled")

    def _settings_from_vars(self) -> dict[str, str]:
        return {key: variable.get() for key, variable in self.vars.items() if key in DEFAULT_SETTINGS}


def load_settings() -> dict[str, str]:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
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
