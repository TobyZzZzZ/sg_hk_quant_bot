import numpy as np
from src.interfaces.strategy import BaseStrategy


class ArithmeticGridStrategy(BaseStrategy):
    def __init__(
        self, lower_bound=60000, upper_bound=80000, grid_count=40, total_capital=50000
    ):
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound
        self.grid_count = grid_count
        self.total_capital = total_capital
        self.initialize()

    def initialize(self, *args, **kwargs):
        # 计算网格间距
        self.grid_spacing = (self.upper_bound - self.lower_bound) / self.grid_count

        # 计算所有网格价格水平 (41个价格点)
        self.levels = np.linspace(
            self.lower_bound, self.upper_bound, self.grid_count + 1
        )

        # 每个网格分配的资金
        self.capital_per_grid = self.total_capital / self.grid_count

        # 状态追踪：记录在每个价格水平是否有待卖出的持仓
        # key: level_price, value: btc_amount
        self.positions = {level: 0.0 for level in self.levels}

        # 记录上一次的价格，用于判断穿越
        self.last_price = None

        print(f"✅ 网格策略初始化完成:")
        print(f"   区间: {self.lower_bound} - {self.upper_bound}")
        print(f"   数量: {self.grid_count} 个网格 ({len(self.levels)} 个价格水平)")
        print(f"   间距: {self.grid_spacing} USDT")
        print(f"   每网格分配资金: {self.capital_per_grid} USDT")

    def handle_data(self, current_price, *args, **kwargs):
        """
        根据当前价格生成信号
        返回: list of signals. 每个信号为 {'type': 'BUY'/'SELL', 'level': price, 'amount_usd': capital}
        """
        signals = []

        if self.last_price is None:
            self.last_price = current_price
            return signals

        # 检查每个价格水平是否被穿越
        for level in self.levels:
            # 买入触发：价格向下穿越 level (从 >level 变为 <=level)
            if self.last_price > level and current_price <= level:
                # 只有在该水平没有持仓时才买入
                if self.positions[level] == 0:
                    signals.append(
                        {
                            "type": "BUY",
                            "level": level,
                            "amount_usd": self.capital_per_grid,
                            "reason": f"Price dropped below {level}",
                        }
                    )

            # 卖出触发：价格向上穿越 level (从 <level 变为 >=level)
            # 注意：在网格交易中，通常是在 level_i 买入，在 level_{i+1} 卖出
            # 这里我们按照用户要求：价格上涨突破网格上沿时卖出
            # 假设我们在 level 买入，那么它对应的卖出水平应该是 level + grid_spacing
            sell_level = level + self.grid_spacing
            if sell_level <= self.upper_bound:
                if self.last_price < sell_level and current_price >= sell_level:
                    # 只有在该水平对应的买入位有持仓时才卖出
                    if self.positions[level] > 0:
                        signals.append(
                            {
                                "type": "SELL",
                                "level": sell_level,
                                "buy_level": level,  # 追踪是哪一笔买入
                                "amount_btc": self.positions[level],
                                "reason": f"Price rose above {sell_level}",
                            }
                        )

        self.last_price = current_price
        return signals

    def record_trade(self, trade_type, level, amount_btc=None, buy_level=None):
        """
        更新持仓状态
        """
        if trade_type == "BUY":
            self.positions[level] += amount_btc
        elif trade_type == "SELL":
            if buy_level is not None:
                self.positions[buy_level] = 0.0
            else:
                # 如果没有提供 buy_level，尝试查找
                # 这种情况在实际回测引擎中应避免
                pass

    def analyze(self, *args, **kwargs):
        pass
