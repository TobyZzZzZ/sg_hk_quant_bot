import numpy as np
from src.interfaces.strategy import BaseStrategy

class MultiFactorStrategy(BaseStrategy):
    def __init__(self, params=None):
        self.params = params or {
            "fast_window": 10,
            "slow_window": 50,
            "momentum_window": 20,
            "volatility_window": 20,
            "volume_ma_window": 20,
            "weights": {"trend": 0.4, "momentum": 0.4, "volatility": 0.1, "volume": 0.1},
            "thresholds": {
                "min_score": 0.55,
                "sell_score": 0.35,
                "max_volatility": 0.05,
                "min_volume_ratio": 1.2
            }
        }
        self.initialize()

    def initialize(self, *args, **kwargs):
        self.price_history = {}
        self.volume_history = {}

    def handle_data(self, data, *args, **kwargs):
        """
        data: dict of symbol -> {'close': price, 'volume': vol}
        returns: dict of symbol -> score
        """
        scores = {}
        for sym, bars in data.items():
            if sym not in self.price_history:
                self.price_history[sym] = []
                self.volume_history[sym] = []
            
            self.price_history[sym].append(bars.get('close', 0))
            self.volume_history[sym].append(bars.get('volume', 0))
            
            # Keep only max window size
            max_window = max(self.params.values(), key=lambda x: x if isinstance(x, int) else 0)
            if isinstance(max_window, int) and len(self.price_history[sym]) > max_window:
                self.price_history[sym].pop(0)
                self.volume_history[sym].pop(0)
                
            scores[sym] = self._calculate_score(sym)
            
        return scores
        
    def _calculate_score(self, sym):
        prices = self.price_history[sym]
        volumes = self.volume_history[sym]
        p = self.params
        
        if len(prices) < p["slow_window"]:
            return 0.0
            
        # Trend
        ma_fast = np.mean(prices[-p["fast_window"]:])
        ma_slow = np.mean(prices[-p["slow_window"]:])
        bias = (ma_fast - ma_slow) / ma_slow if ma_slow != 0 else 0
        trend_score = np.clip(bias * 20 + 0.5, 0, 1)
        
        # Momentum
        if len(prices) >= p["momentum_window"]:
            mom = (prices[-1] - prices[-p["momentum_window"]]) / prices[-p["momentum_window"]] if prices[-p["momentum_window"]] != 0 else 0
            momentum_score = np.clip(mom * 10 + 0.5, 0, 1)
        else:
            momentum_score = 0.5
            
        # Volatility
        if len(prices) >= p["volatility_window"]:
            std_dev = np.std(prices[-p["volatility_window"]:])
            avg_p = np.mean(prices[-p["volatility_window"]:])
            vol_ratio = std_dev / avg_p if avg_p != 0 else 0
            if vol_ratio > p["thresholds"]["max_volatility"]:
                vol_score = 0
            else:
                vol_score = np.clip(1 - (vol_ratio / p["thresholds"]["max_volatility"]), 0, 1)
        else:
            vol_score = 0.5
            
        # Volume
        if len(volumes) >= p["volume_ma_window"]:
            avg_vol = np.mean(volumes[-p["volume_ma_window"]:])
            vol_rat_val = volumes[-1] / avg_vol if avg_vol != 0 else 1
            if vol_rat_val < p["thresholds"]["min_volume_ratio"]:
                vol_score_factor = 0.3
            else:
                vol_score_factor = np.clip(0.5 + (vol_rat_val - 1) * 0.2, 0, 1)
        else:
            vol_score_factor = 0.5
            
        w = p["weights"]
        total = (trend_score * w["trend"] + 
                 momentum_score * w["momentum"] + 
                 vol_score * w["volatility"] + 
                 vol_score_factor * w["volume"])
                 
        return total

    def analyze(self, *args, **kwargs):
        pass
