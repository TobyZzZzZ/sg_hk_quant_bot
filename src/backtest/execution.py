class Execution:
    def __init__(self, maker_fee=0.0005, taker_fee=0.001):
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee

    def execute_order(self, signal, current_data, portfolio, timestamp):
        """
        Executes a single order dict. Expected keys: 'type', 'level', 'amount_usd' / 'amount_btc'
        """
        price = current_data["open"] if "open" in current_data else current_data["close"]

        if signal["type"] == "BUY":
            amount_usd = signal.get("amount_usd", 0)
            if portfolio.capital >= amount_usd:
                fee = amount_usd * self.taker_fee
                cost = amount_usd + fee
                qty = amount_usd / price

                portfolio.capital -= cost
                portfolio.holdings["default"] = portfolio.holdings.get("default", 0) + qty
                trade = {
                    "timestamp": timestamp,
                    "type": "BUY",
                    "price": price,
                    "qty": qty,
                    "cost": cost,
                    "fee": fee,
                    "level": signal.get("level"),
                }
                portfolio.record_trade(trade)
                return trade

        elif signal["type"] == "SELL":
            qty = signal.get("amount_btc", portfolio.holdings.get("default", 0))
            if portfolio.holdings.get("default", 0) >= qty and qty > 0:
                revenue_usd = qty * price
                fee = revenue_usd * self.taker_fee
                net_revenue = revenue_usd - fee

                portfolio.capital += net_revenue
                portfolio.holdings["default"] -= qty
                trade = {
                    "timestamp": timestamp,
                    "type": "SELL",
                    "price": price,
                    "qty": qty,
                    "revenue": net_revenue,
                    "fee": fee,
                    "level": signal.get("level"),
                    "buy_level": signal.get("buy_level"),
                }
                portfolio.record_trade(trade)
                return trade
        return None

    def execute_simple_signal(self, signal_int, current_data, portfolio, timestamp):
        """
        Executes a simple 1 (BUY ALL) or -1 (SELL ALL) signal
        """
        price = current_data['close']
        
        if signal_int == 1 and portfolio.capital > 0:
            # Buy with all capital
            amount_usd = portfolio.capital * 0.99 # Leave room for fees
            fee = amount_usd * self.taker_fee
            qty = amount_usd / price
            
            portfolio.capital -= (amount_usd + fee)
            portfolio.holdings['default'] = portfolio.holdings.get('default', 0) + qty
            portfolio.record_trade({
                'timestamp': timestamp,
                'type': 'BUY',
                'price': price,
                'qty': qty,
                'cost': amount_usd + fee,
                'fee': fee
            })
            
        elif signal_int == -1 and portfolio.holdings.get('default', 0) > 0:
            # Sell all
            qty = portfolio.holdings['default']
            revenue_usd = qty * price
            fee = revenue_usd * self.taker_fee
            net_revenue = revenue_usd - fee
            
            portfolio.capital += net_revenue
            portfolio.holdings['default'] = 0
            portfolio.record_trade({
                'timestamp': timestamp,
                'type': 'SELL',
                'price': price,
                'qty': qty,
                'revenue': net_revenue,
                'fee': fee
            })

    def execute_rebalance(self, scores_dict, current_data, portfolio, timestamp):
        """
        Executes rebalancing based on scores (for multi-factor)
        """
        pass # Simplified for now
