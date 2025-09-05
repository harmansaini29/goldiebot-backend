# FILE: indicators.py (Definitive Final Version)
# =============================================================================

import pandas as pd
import pandas_ta as ta
import warnings # <-- IMPORT THE WARNINGS LIBRARY

try:
    from logger import log
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.StreamHandler())
    log.setLevel(logging.INFO)
    log.warning("Logger not found, using basic logging.")

# =============================================================================
# 1. STACKED EMA ENTRY SIGNAL (EVENT-BASED)
# =============================================================================
def calculate_ema_crossover_signal(df: pd.DataFrame, fast: int, medium: int, slow: int) -> pd.DataFrame:
    if df is None or df.empty or len(df) < slow:
        log.warning("Not enough data to calculate EMA crossover event.")
        return pd.DataFrame()

    df_out = df.copy()
    df_out[f'ema_{fast}'] = ta.ema(df_out['close'], length=fast)
    df_out[f'ema_{medium}'] = ta.ema(df_out['close'], length=medium)
    df_out[f'ema_{slow}'] = ta.ema(df_out['close'], length=slow)
    df_out.dropna(inplace=True)
    if df_out.empty:
        return pd.DataFrame()

    is_bullish_stack = (df_out[f'ema_{fast}'] > df_out[f'ema_{medium}']) & (df_out[f'ema_{medium}'] > df_out[f'ema_{slow}'])
    is_bearish_stack = (df_out[f'ema_{fast}'] < df_out[f'ema_{medium}']) & (df_out[f'ema_{medium}'] < df_out[f'ema_{slow}'])

    was_bullish_stack = is_bullish_stack.shift(1, fill_value=False)
    was_bearish_stack = is_bearish_stack.shift(1, fill_value=False)

    is_buy_signal = is_bullish_stack & ~was_bullish_stack
    is_sell_signal = is_bearish_stack & ~was_bearish_stack

    df_out['signal'] = 'HOLD'
    df_out.loc[is_buy_signal, 'signal'] = 'BUY'
    df_out.loc[is_sell_signal, 'signal'] = 'SELL'
    return df_out

# =============================================================================
# 2. TREND LEVELS REVERSAL SIGNAL (VECTORIZED)
# =============================================================================
def calculate_trend_levels(df: pd.DataFrame, length: int = 30) -> pd.DataFrame:
    if df is None or df.empty or len(df) < 2:
        return pd.DataFrame()
        
    df_out = df.copy()
    df_out['h'] = df_out['high'].rolling(window=length, min_periods=1).max()
    df_out['l'] = df_out['low'].rolling(window=length, min_periods=1).min()

    trend_signal = pd.Series(index=df_out.index, dtype=object)
    trend_signal.loc[df_out['h'] == df_out['high']] = True
    trend_signal.loc[df_out['l'] == df_out['low']] = False
    
    # --- THIS IS THE DEFINITIVE FIX FOR THE WARNING ---
    with warnings.catch_warnings():
        warnings.simplefilter(action='ignore', category=FutureWarning)
        trend_signal = trend_signal.ffill()
    # --- END OF FIX ---
    
    if pd.isna(trend_signal.iloc[0]):
        df_out['trend'] = False
    else:
        df_out['trend'] = trend_signal.astype(bool)
            
    trend_changed = df_out['trend'] != df_out['trend'].shift(1, fill_value=df_out['trend'].iloc[0])
    buy_signal_event = (trend_changed) & (df_out['trend'] == True)
    sell_signal_event = (trend_changed) & (df_out['trend'] == False)

    df_out['signal'] = 'HOLD'
    df_out.loc[buy_signal_event, 'signal'] = 'BUY'
    df_out.loc[sell_signal_event, 'signal'] = 'SELL'
    return df_out