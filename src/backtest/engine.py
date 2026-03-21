import pandas as pd
from tqdm import tqdm
import logging

class StrategyRunner:
    """
    Unified Backtest Engine for running strategies over historical data.
    """
    def __init__(self, strategy, datafeed, portfolio, execution):
        """
        Inject dependencies:
        - strategy: inherits from BaseStrategy
        - datafeed: provides historical data
        - portfolio: tracks holdings and capital
        - execution: handles order execution and fees
        """
        self.strategy = strategy
        self.datafeed = datafeed
        self.portfolio = portfolio
        self.execution = execution
        self.logger = logging.getLogger("StrategyRunner")
        
    def run(self):
        self.logger.info("🚀 Starting backtest...")
        df = self.datafeed.get_data()
        
        for i in tqdm(range(len(df))):
            timestamp = df.index[i]
            row = df.iloc[i]
            
            # Update portfolio value based on current close price
            self.portfolio.update_market_prices(row)
            
            # Pass data to strategy
            # For simplicity, pass the current row. 
            # In a real engine, might pass the whole slice or tick.
            signals = self.strategy.handle_data(row['close'] if 'close' in row else row)
            
            # Execute signals
            if signals:
                if isinstance(signals, list):
                    for signal in signals:
                        trade_result = self.execution.execute_order(
                            signal, row, self.portfolio, timestamp
                        )
                        if trade_result and hasattr(self.strategy, "record_trade"):
                            self.strategy.record_trade(
                                trade_type=trade_result["type"],
                                level=trade_result.get("level"),
                                amount_btc=trade_result.get("qty"),
                                buy_level=trade_result.get("buy_level"),
                            )
                elif isinstance(signals, dict):
                    # E.g. MultiFactor Strategy returning scores
                    self.execution.execute_rebalance(signals, row, self.portfolio, timestamp)
                elif isinstance(signals, int) and signals != 0:
                    # E.g. DualMA Strategy returning 1 or -1
                    self.execution.execute_simple_signal(signals, row, self.portfolio, timestamp)

            self.portfolio.record_equity(timestamp)

        self.logger.info("✅ Backtest complete.")
        self.strategy.analyze()
        return self.portfolio.get_equity_curve(), self.portfolio.get_trades()
