# Roostoo Multi-Pair Grid Trading Bot

A simple, multi-threaded quantitative trading bot implementing a grid trading strategy for the Roostoo platform.

## Features

- **Multi-Pair Support**: Run independent grid trading strategies for multiple currency pairs simultaneously.
- **Automated Grid Initialization**: Automatically calculates grid levels and places initial buy/sell orders based on current market price.
- **Dynamic Balance Management**: Checks for sufficient base currency and automatically performs market buys/sells to meet initial strategy requirements.
- **Gap Maintenance**: Maintains a 2-spacing gap between the highest buy and lowest sell orders to prevent immediate overlapping executions.
- **Robust Monitoring**: Continuously monitors order status and replenishes filled orders to maintain the grid.

## Project Structure

```text
sg_hk_quant_bot/
├── main.py            # Main entry point and grid trading logic
├── roostoo.py         # Roostoo API wrapper for trading operations
├── pyproject.toml     # Project configuration and dependency management (uv)
└── requirements.txt   # Standard Python dependency list
```

## Quick Start

### 1. Configure API Keys

The bot requires a `config.py` file (not included in the repository for security) containing your Roostoo API credentials:

```python
# config.py
API_KEY_TEST = "your_api_key"
API_SECRET_TEST = "your_secret_key"
```

### 2. Configure Trading Pairs

Edit `GRID_CONFIGS` in `main.py` to set your desired symbols and grid parameters:

```python
GRID_CONFIGS = [
    {
        "symbol": "BTC/USD",
        "lower_bound": 63000.0,
        "upper_bound": 77000.0,
        "num_grids": 40,
        "q_per_grid": 0.0088,
    },
    # Add more pairs here...
]
```

### 3. Install Dependencies

This project uses [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
uv sync
```

Or using pip:

```bash
pip install -r requirements.txt
```

### 4. Run the Bot

```bash
uv run python main.py
```

## Strategy Details

The bot implements a standard arithmetic grid trading strategy:
- It divides the range between `lower_bound` and `upper_bound` into `num_grids` equal intervals.
- It identifies the current price level and places sell orders above it and buy orders below it.
- When a sell order is filled, it immediately places a new buy order one grid level below.
- When a buy order is filled, it immediately places a new sell order one grid level above.
- Maker and taker fees are accounted for during initialization to ensure sufficient balances.

## Version

Current version: **0.1.0**
