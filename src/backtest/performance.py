import pandas as pd
import numpy as np
import logging
import os


class PerformanceAnalyzer:
    def __init__(self, equity_curve, trades):
        self.equity_curve = equity_curve
        self.trades = trades
        self.logger = logging.getLogger("PerformanceAnalyzer")

    def calculate_metrics(self):
        if self.equity_curve.empty:
            return {}

        initial_equity = self.equity_curve["equity"].iloc[0]
        final_equity = self.equity_curve["equity"].iloc[-1]

        total_return = (final_equity - initial_equity) / initial_equity

        self.equity_curve["returns"] = self.equity_curve["equity"].pct_change()

        # Max Drawdown
        cum_max = self.equity_curve["equity"].cummax()
        drawdown = (self.equity_curve["equity"] - cum_max) / cum_max
        max_drawdown = drawdown.min()

        metrics = {
            "Initial Capital": initial_equity,
            "Final Capital": final_equity,
            "Total Return": total_return,
            "Max Drawdown": max_drawdown,
            "Total Trades": len(self.trades),
        }

        self.logger.info("=" * 40)
        self.logger.info("📊 Performance Metrics")
        self.logger.info("=" * 40)
        for k, v in metrics.items():
            if isinstance(v, float):
                self.logger.info(
                    f"{k}: {v:.2%}"
                    if "Return" in k or "Drawdown" in k
                    else f"{k}: {v:.2f}"
                )
            else:
                self.logger.info(f"{k}: {v}")

        return metrics

    def export_results(self, output_dir="reports"):
        """
        Export equity curve and trades to CSV files.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        if not self.equity_curve.empty:
            equity_path = os.path.join(output_dir, "equity_curve.csv")
            self.equity_curve.to_csv(equity_path)
            self.logger.info(f"✅ Equity curve exported to {equity_path}")

        if self.trades:
            trades_df = pd.DataFrame(self.trades)
            trades_path = os.path.join(output_dir, "trades.csv")
            trades_df.to_csv(trades_path, index=False)
            self.logger.info(f"✅ Trades exported to {trades_path}")
