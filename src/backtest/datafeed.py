import pandas as pd

class DataFeed:
    def __init__(self, df):
        """
        Initialize with a pandas DataFrame. 
        In a real scenario, this would load from DB or files dynamically.
        """
        self.df = df
        
    def get_data(self):
        return self.df
