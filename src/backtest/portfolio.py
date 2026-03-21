import pandas as pd

class Portfolio:
    def __init__(self, initial_capital=100000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.holdings = {} # symbol -> quantity
        self.equity_curve = []
        self.trades = []
        self.current_market_prices = {}

    def update_market_prices(self, current_data):
        if isinstance(current_data, pd.Series) and 'close' in current_data:
            # Assuming single asset for simplicity if it's just 'close'
            self.current_market_prices['default'] = current_data['close']
        elif isinstance(current_data, pd.Series):
            # Might be multi-asset row
            for sym in current_data.index:
                self.current_market_prices[sym] = current_data[sym]

    def get_total_equity(self):
        equity = self.capital
        for sym, qty in self.holdings.items():
            price = self.current_market_prices.get(sym, self.current_market_prices.get('default', 0))
            equity += qty * price
        return equity

    def record_equity(self, timestamp):
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': self.get_total_equity(),
            'capital': self.capital
        })

    def record_trade(self, trade):
        self.trades.append(trade)

    def get_equity_curve(self):
        return pd.DataFrame(self.equity_curve)

    def get_trades(self):
        return self.trades
