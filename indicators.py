# =============================================================================
#
#   INDICATOR CALCULATION ENGINE
#
# -----------------------------------------------------------------------------
#   This module contains the Python implementations of the core indicators.
#   Each function is designed to be pure and testable, taking a pandas
#   DataFrame of OHLCV data and returning the calculated indicator values.
#
# =============================================================================

import pandas as pd
import numpy as np
import math
from typing import Dict, Any

# =============================================================================
# 1. TREND LEVELS
# =============================================================================
# Primary signal generator based on the "Trend Levels [ChartPrime]" concept.
# It identifies trend changes by tracking new highs or lows over a lookback
# period.

def calculate_trend_levels(df: pd.DataFrame, length: int = 30) -> pd.DataFrame:
    """
    Calculates trend levels and identifies trend reversals.

    This function replicates the stateful logic of many trading indicators where
    the current trend direction depends on the previous state.

    Args:
        df (pd.DataFrame): DataFrame with 'high' and 'low' columns.
        length (int): The lookback period for finding highest highs and lowest lows.

    Returns:
        pd.DataFrame: A copy of the input DataFrame with new columns:
                      'trend' (bool): True for uptrend, False for downtrend.
                      'signal' (str): 'BUY', 'SELL', or 'HOLD'.
    """
    df_out = df.copy()
    
    # Calculate highest high and lowest low over the rolling window
    df_out['h'] = df_out['high'].rolling(window=length, min_periods=1).max()
    df_out['l'] = df_out['low'].rolling(window=length, min_periods=1).min()

    # Replicate Pine Script's stateful 'trend' variable in pandas
    trend = np.zeros(len(df_out), dtype=bool)
    for i in range(1, len(df_out)):
        # If a new high is made, trend becomes bullish (True)
        if df_out['h'].iloc[i] == df_out['high'].iloc[i]:
            trend[i] = True
        # If a new low is made, trend becomes bearish (False)
        elif df_out['l'].iloc[i] == df_out['low'].iloc[i]:
            trend[i] = False
        # Otherwise, the trend continues from the previous bar
        else:
            trend[i] = trend[i-1]
            
    df_out['trend'] = trend
    df_out['trend_prev'] = df_out['trend'].shift(1)

    # A signal is generated only on the bar where the trend flips
    df_out['signal'] = np.where(
        (df_out['trend'] == True) & (df_out['trend_prev'] == False), 'BUY',
        np.where(
            (df_out['trend'] == False) & (df_out['trend_prev'] == True), 'SELL',
            'HOLD'
        )
    )
    
    # Clean up intermediate columns before returning
    df_out.drop(columns=['h', 'l', 'trend_prev'], inplace=True)
    
    return df_out


# =============================================================================
# 2. VOLATILITY GAUSSIAN BANDS
# =============================================================================
# Provides dynamic levels for stop-loss and take-profit based on the
# "Volatility Gaussian Bands [BigBeluga]" concept.

def _gaussian_filter(src: pd.Series, length: int, sigma: float) -> pd.Series:
    """Helper function to apply a 1D Gaussian filter."""
    weights = np.zeros(length)
    for i in range(length):
        # Calculate weight for each point in the window based on Gaussian distribution
        weights[i] = math.exp(-0.5 * math.pow((i - (length - 1) / 2) / sigma, 2.0))
    
    # Normalize weights to sum to 1
    weights /= np.sum(weights)
    
    # Apply the weighted average
    return src.rolling(window=length).apply(lambda x: np.sum(x * weights), raw=True)

def calculate_gaussian_bands(df: pd.DataFrame, length: int = 20, distance: float = 1.0) -> pd.DataFrame:
    """
    Calculates Volatility Gaussian Bands.

    Args:
        df (pd.DataFrame): DataFrame with 'high', 'low', 'close' columns.
        length (int): The base length for the Gaussian filter.
        distance (float): Multiplier for the volatility bands' width.

    Returns:
        pd.DataFrame: A copy of the input DataFrame with new columns:
                      'gauss_avg', 'gauss_upper', 'gauss_lower'.
    """
    df_out = df.copy()
    
    # Use a simple moving average of the bar's range as a stable volatility measure
    volatility = (df_out['high'] - df_out['low']).rolling(window=100, min_periods=1).mean()

    # Create a smoothed central line using a Gaussian filter on the close price
    # A sigma of length / 3 is a common choice for a good smoothing effect
    gauss_avg = _gaussian_filter(df_out['close'], length, length / 3)

    # Calculate upper and lower bands based on volatility
    df_out['gauss_avg'] = gauss_avg
    df_out['gauss_upper'] = gauss_avg + (volatility * distance)
    df_out['gauss_lower'] = gauss_avg - (volatility * distance)
    
    return df_out


# =============================================================================
# 3. GANN ANGLES
# =============================================================================
# Provides static, mathematically derived price levels based on Gann theory.

def calculate_gann_levels(daily_data: pd.DataFrame, calculation_basis: str) -> Dict[str, Any]:
    """
    Calculates intraday buy and sell levels based on Gann Angles theory.

    Args:
        daily_data (pd.DataFrame): DataFrame containing at least two days of
                                   OHLC data with columns ['open', 'high', 'low', 'close'].
        calculation_basis (str): The reference price to use for calculations.

    Returns:
        Dict[str, Any]: A dictionary containing all calculated Gann levels,
                        or an empty dict if calculation is not possible.
    """
    if len(daily_data) < 2:
        print("Error: Insufficient daily data for Gann levels. Need at least 2 days.")
        return {}

    prev_day = daily_data.iloc[-2]
    today = daily_data.iloc[-1]

    # Select the reference price based on the configuration
    basis_map = {
        'Todays Open': today['open'],
        'Previous Days High': prev_day['high'],
        'Previous Days Low': prev_day['low'],
        'Previous Days Close': prev_day['close']
    }
    reference_price = basis_map.get(calculation_basis)
    
    if reference_price is None:
        raise ValueError(f"Invalid calculation_basis for Gann: '{calculation_basis}'")

    if reference_price <= 0:
        print(f"Warning: Cannot calculate Gann levels with non-positive reference price ({reference_price}).")
        return {}
        
    sqrt_ref = math.sqrt(reference_price)
    # Define the Gann fractions for level calculation
    gann_fractions = [0.0625, 0.125, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]

    levels = {'buy_side': {}, 'sell_side': {}}
    
    # Calculate buy-side levels (entry, targets, stop loss)
    levels['buy_side']['entry'] = (sqrt_ref + gann_fractions[1])**2
    levels['buy_side']['stop_loss'] = (sqrt_ref - gann_fractions[0])**2
    for i in range(2, len(gann_fractions)):
        levels['buy_side'][f'target_{i-1}'] = (sqrt_ref + gann_fractions[i])**2

    # Calculate sell-side levels (entry, targets, stop loss)
    levels['sell_side']['entry'] = (sqrt_ref - gann_fractions[1])**2
    levels['sell_side']['stop_loss'] = (sqrt_ref + gann_fractions[0])**2
    for i in range(2, len(gann_fractions)):
        levels['sell_side'][f'target_{i-1}'] = (sqrt_ref - gann_fractions[i])**2
        
    return levels

# =============================================================================
#                             SCRIPT TESTING
# =============================================================================
if __name__ == '__main__':
    # This block runs only when the script is executed directly (for testing)
    
    # Create a sample DataFrame mimicking exchange data
    data = {
        'timestamp': pd.to_datetime(pd.date_range(start='2023-01-01', periods=100, freq='5T')),
        'open': np.random.uniform(95, 105, 100).cumsum() + 1000,
        'close': np.random.uniform(-2, 2, 100).cumsum() + 1002,
        'volume': np.random.uniform(10, 100, 100)
    }
    df = pd.DataFrame(data)
    df['high'] = df[['open', 'close']].max(axis=1) + np.random.uniform(0, 2, 100)
    df['low'] = df[['open', 'close']].min(axis=1) - np.random.uniform(0, 2, 100)
    df.set_index('timestamp', inplace=True)

    print("="*80)
    print("RUNNING INDICATOR TESTS")
    print("="*80)

    # 1. Test Trend Levels Signal
    df_with_signals = calculate_trend_levels(df, length=30)
    print("\n[1] Trend Levels Signals Found:")
    print(df_with_signals[df_with_signals['signal'] != 'HOLD'][['close', 'signal']])

    # 2. Test Gaussian Bands
    df_with_bands = calculate_gaussian_bands(df, length=20, distance=1.0)
    print("\n[2] Latest Gaussian Bands:")
    print(df_with_bands[['gauss_avg', 'gauss_upper', 'gauss_lower']].tail(1))

    # 3. Test Gann Levels (requires daily data)
    daily_df = df.resample('D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'
    }).dropna()
    
    if not daily_df.empty and len(daily_df) > 1:
        gann_levels = calculate_gann_levels(daily_df, 'Previous Days Close')
        print("\n[3] Gann Levels for Today (based on Previous Day's Close):")
        import json
        print(json.dumps(gann_levels, indent=2))
    else:
        print("\n[3] Not enough daily data to calculate Gann Levels.")
        
    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)
