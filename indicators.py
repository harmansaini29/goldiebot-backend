# FILE: indicators.py
# =============================================================================

import pandas as pd
import pandas_ta as ta
import warnings
import configs as config

try:
    from logger import log
except ImportError:
    import logging
    log = logging.getLogger(__name__)
    log.addHandler(logging.StreamHandler())

# =============================================================================
# 1. VOLATILITY INDICATOR (ATR) - NEW
# =============================================================================
def calculate_atr(df: pd.DataFrame, period: int, point: float) -> float:
    """Calculates the current ATR value in pips."""
    if df is None or df.empty or len(df) < period:
        return 0.0
    
    atr_values = ta.atr(df['high'], df['low'], df['close'], length=period)
    if atr_values is None or atr_values.empty:
        return 0.0
        
    # Convert the raw ATR price value into pips
    current_atr_in_price = atr_values.iloc[-1]
    current_atr_in_pips = current_atr_in_price / (config.POINTS_PER_PIP * point)
    return current_atr_in_pips

# =============================================================================
# 2. STACKED EMA ENTRY SIGNAL
# =============================================================================
def calculate_ema_crossover_signal(df: pd.DataFrame, fast: int, medium: int, slow: int, point: float) -> pd.DataFrame:
    if df is None or df.empty or len(df) < slow:
        return pd.DataFrame()

    df_out = df.copy()
    df_out[f'ema_{fast}'] = ta.ema(df_out['close'], length=fast)
    df_out[f'ema_{medium}'] = ta.ema(df_out['close'], length=medium)
    df_out[f'ema_{slow}'] = ta.ema(df_out['close'], length=slow)
    df_out.dropna(inplace=True)
    if df_out.empty: return pd.DataFrame()

    is_bullish_stack = (df_out[f'ema_{fast}'] > df_out[f'ema_{medium}']) & (df_out[f'ema_{medium}'] > df_out[f'ema_{slow}'])
    is_bearish_stack = (df_out[f'ema_{fast}'] < df_out[f'ema_{medium}']) & (df_out[f'ema_{medium}'] < df_out[f'ema_{slow}'])
    was_bullish_stack = is_bullish_stack.shift(1, fill_value=False)
    was_bearish_stack = is_bearish_stack.shift(1, fill_value=False)
    is_buy_crossover_event = is_bullish_stack & ~was_bullish_stack
    is_sell_crossover_event = is_bearish_stack & ~was_bearish_stack

    is_green_candle = df_out['close'] > df_out['open']
    is_red_candle = df_out['close'] < df_out['open']

    min_separation_in_price = config.MIN_SEPARATION_PIPS * config.POINTS_PER_PIP * point
    is_bullish_separation = (df_out[f'ema_{fast}'] - df_out[f'ema_{slow}']) > min_separation_in_price
    is_bearish_separation = (df_out[f'ema_{slow}'] - df_out[f'ema_{fast}']) > min_separation_in_price

    df_out['signal'] = 'HOLD'
    df_out.loc[is_buy_crossover_event & is_green_candle & is_bullish_separation, 'signal'] = 'BUY'
    df_out.loc[is_sell_crossover_event & is_red_candle & is_bearish_separation, 'signal'] = 'SELL'
    return df_out

# =============================================================================
# 3. TREND LEVELS REVERSAL SIGNAL
# =============================================================================
def calculate_trend_levels(df: pd.DataFrame, length: int) -> pd.DataFrame:
    if df is None or df.empty or len(df) < length: return pd.DataFrame()
    df_out = df.copy()
    df_out['h'] = df_out['high'].rolling(window=length, min_periods=1).max()
    df_out['l'] = df_out['low'].rolling(window=length, min_periods=1).min()
    trend_signal = pd.Series(index=df_out.index, dtype=object)
    trend_signal.loc[df_out['h'] == df_out['high']] = True
    trend_signal.loc[df_out['l'] == df_out['low']] = False
    with warnings.catch_warnings():
        warnings.simplefilter(action='ignore', category=FutureWarning)
        trend_signal = trend_signal.ffill()

    if pd.isna(trend_signal.iloc[0]): df_out['trend'] = False
    else: df_out['trend'] = trend_signal.astype(bool)
        
    trend_changed = df_out['trend'] != df_out['trend'].shift(1, fill_value=df_out['trend'].iloc[0])
    buy_signal_event = (trend_changed) & (df_out['trend'] == True)
    sell_signal_event = (trend_changed) & (df_out['trend'] == False)
    
    df_out['signal'] = 'HOLD'
    df_out.loc[buy_signal_event, 'signal'] = 'BUY'
    df_out.loc[sell_signal_event, 'signal'] = 'SELL'
    return df_out