import pandas as pd
from typing import Optional


class WindowedDataFrame:
    window: float
    columns: list[str]
    index_column: str
    df: pd.DataFrame

    def __init__(self, window: float, columns: list[str], index_column: str, init_data: Optional[dict]=None):
        self.window = window

        if init_data is None:
            init_data = []

        self.df = pd.DataFrame(init_data, columns=columns).set_index(index_column)
        self.columns = columns
        self.index_column = index_column

    def append(self, data: dict, curr: Optional[float]=None) -> None:
        new_data = pd.DataFrame(data, columns=self.columns).set_index(self.index_column)

        dfs = [_df for _df in [self.df, new_data] if len(_df) != 0]
        if len(dfs) == 0:
            self.df = pd.DataFrame([], columns=self.columns).set_index(self.index_column)
        elif len(dfs) == 1:
            self.df = dfs[0]
        else:
            self.df = pd.concat([self.df, new_data])

        if curr is None:
            curr = self.df.index[-1]

        self._remove_old(curr)

    def _remove_old(self, current_time: float) -> None:
        self.df = self.df.loc[(current_time - self.window):current_time]
