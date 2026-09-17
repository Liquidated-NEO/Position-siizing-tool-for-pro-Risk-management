# Crypto Futures Position Sizing tool

A professional desktop position sizing tool for crypto futures traders.

The app sizes positions from fixed account risk first, then uses leverage only to calculate required margin. This keeps the trade risk controlled instead of letting leverage inflate exposure.

## Project Layout

```text
crypto-futures-position-sizer/
├── main.py
├── calculator.py
├── risk.py
├── exchange.py
├── ui.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
├── assets/
│   ├── logo.png
│   └── screenshot.png
└── tests/
```

## Features

- Modern dark CustomTkinter interface
- Long and short futures position sizing
- Decimal-based financial calculations
- Leverage and required margin calculation
- Fees, slippage, max loss, net profit, and risk/reward
- Estimated liquidation price and liquidation buffer warnings
- Exchange tick-size and lot-size handling
- Risk controls for daily loss, open risk, max margin usage, and max notional
- Settings persistence in `settings.json`
- Trade export to `trades.csv`

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Test

```powershell
python -m unittest discover -s tests
```

## Risk Model

Position size is calculated from risk:

```text
risk amount = account balance × risk %
position size = risk amount ÷ risk per unit
required margin = position notional ÷ leverage
```

Leverage does not increase the selected risk. It only changes the margin required to hold the position.

## Disclaimer

This is a planning and sizing tool, not financial advice. Liquidation estimates are simplified and should be checked against the actual exchange before placing live orders.
