# =============================================================================
#
#   INDICATOR CALCULATION ENGINE (REVISED)
#
# =============================================================================

import pandas as pd
import numpy as np
import math
from typing import Dict, Any

from logger import log # Import log for better error handling

# =============================================================================
# 1. TREND LEVELS (CORRECTED)
# =============================================================================
def calculate_trend_levels(df: pd.DataFrame, length: int = 30) -> pd.DataFrame:
    """
    Calculates trend levels and identifies trend reversals.
    CORRECTED to precisely match the Pine Script logic.
    """
    df_out = df.copy()
    
    df_out['h'] = df_out['high'].rolling(window=length, min_periods=1).max()
    df_out['l'] = df_out['low'].rolling(window=length, min_periods=1).min()

    # --- REVISED LOGIC TO MATCH PINE SCRIPT'S 'var' and sequential 'if' BEHAVIOR ---
    trend = np.zeros(len(df_out), dtype=bool)  # True=Uptrend, False=Downtrend
    trend[0] = True # Default initial trend

    for i in range(1, len(df_out)):
        # First, carry over the previous trend state, like Pine Script's `var`
        trend[i] = trend[i-1]
        
        # Next, check for a new high (can set trend to True)
        if df_out['h'].iloc[i] == df_out['high'].iloc[i]:
            trend[i] = True
            
        # Finally, check for a new low (can overwrite and set trend to False)
        if df_out['l'].iloc[i] == df_out['low'].iloc[i]:
            trend[i] = False
            
    df_out['trend'] = trend
    df_out['trend_prev'] = df_out['trend'].shift(1)

    df_out['signal'] = np.where(
        (df_out['trend'] == True) & (df_out['trend_prev'] == False), 'BUY',
        np.where(
            (df_out['trend'] == False) & (df_out['trend_prev'] == True), 'SELL', 'HOLD'
        )
    )
    
    df_out.drop(columns=['h', 'l', 'trend_prev'], inplace=True)
    return df_out


# =============================================================================
# 2. GANN ANGLES (UNCHANGED - ALREADY CORRECT)
# =============================================================================
def calculate_gann_levels(daily_data: pd.DataFrame, calculation_basis: str) -> Dict[str, Any]:
    """
    Calculates intraday buy and sell levels based on Gann Angles theory.
    This implementation correctly matches the provided Pine Script.
    """
    if len(daily_data) < 2:
        log.warning("Insufficient daily data for Gann levels. Need at least 2 days.")
        return {}

    prev_day = daily_data.iloc[-2]
    today = daily_data.iloc[-1]

    basis_map = {
        'Todays Open': today['open'],
        'Previous Days High': prev_day['high'],
        'Previous Days Low': prev_day['low'],
        'Previous Days Close': prev_day['close']
    }
    reference_price = basis_map.get(calculation_basis)
    
    if reference_price is None:
        log.error(f"Invalid calculation_basis for Gann: '{calculation_basis}'")
        return {}
    if not isinstance(reference_price, (int, float)) or reference_price <= 0:
        log.warning(f"Cannot calculate Gann levels with non-positive reference price ({reference_price}).")
        return {}
        
    sqrt_ref = math.sqrt(reference_price)
    # These fractions match the Gann Angles Pine Script
    gann_fractions = [0.0625, 0.125, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

    levels = {'buy_side': {}, 'sell_side': {}}
    
    # Buy-side levels
    levels['buy_side']['entry'] = (sqrt_ref + gann_fractions[1])**2
    levels['buy_side']['stop_loss'] = (sqrt_ref - gann_fractions[0])**2
    for i, frac in enumerate(gann_fractions[2:]):
        levels['buy_side'][f'target_{i+1}'] = (sqrt_ref + frac)**2

    # Sell-side levels
    levels['sell_side']['entry'] = (sqrt_ref - gann_fractions[1])**2
    levels['sell_side']['stop_loss'] = (sqrt_ref + gann_fractions[0])**2
    for i, frac in enumerate(gann_fractions[2:]):
        levels['sell_side'][f'target_{i+1}'] = (sqrt_ref - frac)**2
        
    return levels