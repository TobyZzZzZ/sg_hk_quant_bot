import sys
import os
sys.path.append(os.path.abspath("."))
from src.api.roostoo import get_ticker, get_balance
print("Ticker:", get_ticker("BTC/USD"))
print("Balance:", get_balance())
