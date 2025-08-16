# =============================================================================
#
#   ATOMIC & ROBUST EXCEL REPORTING ENGINE
#
# =============================================================================
#   This engine is designed for maximum stability. It writes changes to a
#   temporary file first, and only replaces the main report upon successful
#   completion. This "atomic" process prevents file corruption even if the
#   bot is stopped unexpectedly.
# =============================================================================

import pandas as pd
from pathlib import Path
import threading
from datetime import datetime
import logging
import zipfile
import traceback
import os
import shutil
from typing import List, Dict, Any

class ExcelReporter:
    """
    Manages writing to an Excel file using an atomic process to prevent corruption.
    """
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.log_dir = self.filepath.parent
        self.log_dir.mkdir(exist_ok=True, parents=True)
        
        # On startup, check for and clean up any leftover temp files
        self._cleanup_temp_files()

        # Initialize the main report file if it doesn't exist
        if not self.filepath.exists():
            self._create_empty_workbook(self.filepath)

    def _cleanup_temp_files(self):
        """Removes any orphaned temporary files from a previous crashed session."""
        for item in self.log_dir.iterdir():
            if item.is_file() and item.name.endswith('.tmp'):
                try:
                    os.remove(item)
                    print(f"[RECOVERY] Removed old temporary file: {item.name}")
                except OSError:
                    pass

    def _create_empty_workbook(self, path: Path):
        """Creates a fresh, blank Excel workbook with all necessary sheets."""
        try:
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                # ActivityLog Sheet
                pd.DataFrame(columns=['Timestamp', 'Level', 'Message']).to_excel(
                    writer, sheet_name='ActivityLog', index=False)
                
                # --- UPDATED: Added TP and SL columns to TradeHistory ---
                trade_cols = [
                    'Ticket #', 'Entry Time', 'Exit Time', 'Symbol', 'Timeframe', 
                    'Direction', 'Lot Size', 'Entry Price', 'Exit Price', 
                    'Take Profit', 'Stop Loss', 'Profit/Loss ($)', 
                    'Entry Type', 'Exit Reason'
                ]
                pd.DataFrame(columns=trade_cols).to_excel(
                    writer, sheet_name='TradeHistory', index=False)
                # --- END of update ---
                
                # MonthlySummary Sheet
                summary_cols = ['Month', 'Total Profit ($)', 'Total Loss ($)', 'Net Profit/Loss ($)']
                pd.DataFrame(columns=summary_cols).to_excel(
                    writer, sheet_name='MonthlySummary', index=False)
        except Exception as e:
            print(f"[CRITICAL] Failed to create a new workbook: {e}")
            traceback.print_exc()

    def _atomic_save(self, data_sheets: dict):
        """
        Atomically saves the data to the Excel file.
        1. Writes to a temporary file.
        2. If successful, replaces the original file.
        """
        temp_filepath = self.filepath.with_suffix('.xlsx.tmp')
        
        try:
            # Write all data to the new temporary file
            with pd.ExcelWriter(temp_filepath, engine='openpyxl') as writer:
                for sheet_name, df in data_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            # Atomically replace the old file with the new one
            shutil.move(temp_filepath, self.filepath)

        except Exception as e:
            print(f"[CRITICAL] Failed to save Excel report: {e}")
            traceback.print_exc()
            # Clean up the failed temp file if it exists
            if temp_filepath.exists():
                os.remove(temp_filepath)

    def _read_and_heal(self) -> dict:
        """
        Reads the Excel file. If it's corrupt, it backs up the broken file
        and starts a fresh one.
        """
        try:
            if not self.filepath.exists() or self.filepath.stat().st_size < 100:
                    raise ValueError("File is missing or too small to be valid.")
            return pd.read_excel(self.filepath, sheet_name=None, engine='openpyxl')
        except (zipfile.BadZipFile, ValueError, KeyError) as e:
            print(f"[WARNING] Excel file '{self.filepath.name}' is corrupt. Backing up and recreating.")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.filepath.with_name(f"{self.filepath.stem}_corrupt_{timestamp}.xlsx")
            
            if self.filepath.exists():
                shutil.move(self.filepath, backup_path)
                print(f"Backed up corrupt file to: {backup_path}")

            self._create_empty_workbook(self.filepath)
            return pd.read_excel(self.filepath, sheet_name=None, engine='openpyxl')

    def log_activity(self, level: str, message: str):
        """Logs a message to the ActivityLog sheet."""
        with self.lock:
            try:
                all_sheets = self._read_and_heal()
                new_log_df = pd.DataFrame([[datetime.now(), level, message]], columns=['Timestamp', 'Level', 'Message'])
                
                # Safely handle potentially missing sheet
                activity_log = all_sheets.get('ActivityLog', pd.DataFrame(columns=['Timestamp', 'Level', 'Message']))
                all_sheets['ActivityLog'] = pd.concat([activity_log, new_log_df], ignore_index=True)

                self._atomic_save(all_sheets)
            except Exception as e:
                print(f"Error during activity logging: {e}")

    def log_trade(self, trade_data: dict):
        """Logs a completed trade and updates the summary."""
        with self.lock:
            try:
                all_sheets = self._read_and_heal()
                
                # Define all possible columns to ensure consistency
                trade_cols = [
                    'Ticket #', 'Entry Time', 'Exit Time', 'Symbol', 'Timeframe', 
                    'Direction', 'Lot Size', 'Entry Price', 'Exit Price', 
                    'Take Profit', 'Stop Loss', 'Profit/Loss ($)', 
                    'Entry Type', 'Exit Reason'
                ]
                trade_history = all_sheets.get('TradeHistory', pd.DataFrame(columns=trade_cols))
                
                new_trade_df = pd.DataFrame([trade_data])
                all_sheets['TradeHistory'] = pd.concat([trade_history, new_trade_df], ignore_index=True)
                all_sheets['MonthlySummary'] = self._calculate_monthly_summary(all_sheets['TradeHistory'])

                self._atomic_save(all_sheets)
            except Exception as e:
                print(f"Error during trade logging: {e}")

    def _calculate_monthly_summary(self, history_df: pd.DataFrame) -> pd.DataFrame:
        """Calculates the monthly summary from the trade history."""
        summary_cols = ['Month', 'Total Profit ($)', 'Total Loss ($)', 'Net Profit/Loss ($)']
        if history_df is None or history_df.empty:
            return pd.DataFrame(columns=summary_cols)

        df = history_df.copy()
        df['Exit Time'] = pd.to_datetime(df['Exit Time'])
        df['Month'] = df['Exit Time'].dt.to_period('M').astype(str)

        monthly_profit = df[df['Profit/Loss ($)'] > 0].groupby('Month')['Profit/Loss ($)'].sum()
        monthly_loss = df[df['Profit/Loss ($)'] < 0].groupby('Month')['Profit/Loss ($)'].sum()

        summary = pd.DataFrame({'Total Profit ($)': monthly_profit, 'Total Loss ($)': monthly_loss}).reset_index()
        summary = summary.fillna(0)
        summary['Net Profit/Loss ($)'] = summary['Total Profit ($)'] + summary['Total Loss ($)']

        return summary[summary_cols]

    ## MODIFICATION: Added this new function to the class
    def get_logged_tickets(self) -> List[int]:
        """
        Reads the Excel file safely and returns a list of all ticket numbers
        that have already been logged in the 'TradeHistory' sheet.
        """
        with self.lock:
            try:
                all_sheets = self._read_and_heal()
                trade_history = all_sheets.get('TradeHistory')
                if trade_history is not None and 'Ticket #' in trade_history.columns:
                    # Drop duplicates and NaNs, then convert to int
                    return trade_history['Ticket #'].dropna().unique().astype(int).tolist()
                return []
            except Exception as e:
                print(f"[ERROR] Failed to read logged tickets from Excel: {e}")
                return []

class ExcelHandler(logging.Handler):
    """A custom logging handler that directs log records to the ExcelReporter."""
    def __init__(self, reporter: ExcelReporter):
        super().__init__()
        self.reporter = reporter

    def emit(self, record: logging.LogRecord):
        try:
            message = self.format(record)
            self.reporter.log_activity(record.levelname, message)
        except Exception:
            pass # Fails silently to prevent a logging error from crashing the app
