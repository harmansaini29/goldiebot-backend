# FILE: excel_reporter.py
# =============================================================================
#
#   ATOMIC & ROBUST EXCEL REPORTING ENGINE
#
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
    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.lock = threading.Lock()
        self.log_dir = self.filepath.parent
        self.log_dir.mkdir(exist_ok=True, parents=True)
        self._cleanup_temp_files()
        if not self.filepath.exists():
            self._create_empty_workbook(self.filepath)

    def _cleanup_temp_files(self):
        temp_file = self.filepath.with_suffix('.xlsx.tmp')
        if temp_file.exists():
            print(f"[RECOVERY] Removed old temporary file: {temp_file.name}")
            os.remove(temp_file)

    def _create_empty_workbook(self, path: Path):
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            pd.DataFrame().to_excel(writer, sheet_name='TradeHistory', index=False)
            pd.DataFrame().to_excel(writer, sheet_name='ActivityLog', index=False)
            pd.DataFrame().to_excel(writer, sheet_name='MonthlySummary', index=False)

    def _read_and_heal(self) -> Dict[str, pd.DataFrame]:
        try:
            return pd.read_excel(self.filepath, sheet_name=None)
        except (zipfile.BadZipFile, FileNotFoundError) as e:
            print(f"[RECOVERY] Excel file '{self.filepath.name}' is corrupt or missing. Attempting to heal. Error: {e}")
            backup_path = self.filepath.with_suffix(f".{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak")
            if self.filepath.exists():
                shutil.move(self.filepath, backup_path)
                print(f"[RECOVERY] Corrupt file backed up to: {backup_path.name}")
            self._create_empty_workbook(self.filepath)
            return self._read_and_heal()

    def _atomic_write(self, all_sheets: Dict[str, pd.DataFrame]):
        temp_filepath = self.filepath.with_suffix('.xlsx.tmp')
        try:
            with pd.ExcelWriter(temp_filepath, engine='openpyxl') as writer:
                for sheet_name, df in all_sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            shutil.move(temp_filepath, self.filepath)
        except Exception as e:
            print(f"[CRITICAL] Failed to save Excel report: {e}\n{traceback.format_exc()}")
            if temp_filepath.exists():
                os.remove(temp_filepath)

    def log_trade_history(self, deals_df: pd.DataFrame):
        with self.lock:
            all_sheets = self._read_and_heal()
            formatted_history = self._format_trade_history(deals_df)
            if formatted_history is None: return

            trade_history_df = all_sheets.get('TradeHistory', pd.DataFrame())
            all_sheets['TradeHistory'] = pd.concat([trade_history_df, formatted_history], ignore_index=True).drop_duplicates(subset=['Deal #'], keep='last')
            all_sheets['MonthlySummary'] = self._calculate_summary(all_sheets['TradeHistory'])
            self._atomic_write(all_sheets)

    def log_activity(self, level: str, message: str):
        with self.lock:
            all_sheets = self._read_and_heal()
            activity_log_df = all_sheets.get('ActivityLog', pd.DataFrame())
            new_log_entry = pd.DataFrame([{'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Level': level, 'Message': message}])
            all_sheets['ActivityLog'] = pd.concat([activity_log_df, new_log_entry], ignore_index=True)
            self._atomic_write(all_sheets)

    def _format_trade_history(self, deals_df: pd.DataFrame):
        deals_df['time'] = pd.to_datetime(deals_df['time'], unit='s')
        
        entry_deals = deals_df[deals_df['entry'] == 0]
        exit_deals = deals_df[deals_df['entry'] == 1]

        if entry_deals.empty or exit_deals.empty:
            return None

        entry_deal = entry_deals.iloc[0]
        exit_deal = exit_deals.iloc[0]
        
        return pd.DataFrame([{
            'Ticket #': entry_deal['position_id'],
            'Symbol': entry_deal['symbol'],
            'Type': 'BUY' if entry_deal['type'] == 0 else 'SELL',
            'Open Time': entry_deal['time'].strftime('%Y-%m-%d %H:%M:%S'),
            'Open Price': entry_deal['price'],
            'Close Time': exit_deal['time'].strftime('%Y-%m-%d %H:%M:%S'),
            'Close Price': exit_deal['price'],
            'Volume': entry_deal['volume'],
            'Profit ($)': deals_df['profit'].sum(),
            'Commission ($)': deals_df['commission'].sum(),
            'Swap ($)': deals_df['swap'].sum(),
            'Comment': entry_deal['comment'],
            # --- CRASH FIX: Changed 'deal' to 'ticket' which is the correct column name ---
            'Deal #': entry_deal['ticket'] 
        }])

    def _calculate_summary(self, history_df: pd.DataFrame):
        if history_df.empty: return pd.DataFrame()
        history_df['Open Time'] = pd.to_datetime(history_df['Open Time'])
        history_df['Month'] = history_df['Open Time'].dt.to_period('M')
        summary = history_df.groupby('Month').agg(Total_Trades=('Ticket #', 'count'), Total_Profit=('Profit ($)', lambda x: x[x > 0].sum()), Total_Loss=('Profit ($)', lambda x: x[x <= 0].sum()), Total_Volume=('Volume', 'sum')).reset_index()
        summary.columns = ['Month', 'Total Trades', 'Total Profit ($)', 'Total Loss ($)', 'Total Volume']
        summary['Month'] = summary['Month'].astype(str)
        summary['Net Profit/Loss ($)'] = summary['Total Profit ($)'] + summary['Total Loss ($)']
        return summary[['Month', 'Total Trades', 'Total Profit ($)', 'Total Loss ($)', 'Net Profit/Loss ($)', 'Total Volume']]

    def get_logged_tickets(self) -> List[int]:
        with self.lock:
            try:
                all_sheets = self._read_and_heal()
                trade_history = all_sheets.get('TradeHistory')
                if trade_history is not None and 'Ticket #' in trade_history.columns:
                    return trade_history['Ticket #'].dropna().unique().astype(int).tolist()
                return []
            except Exception as e:
                print(f"[ERROR] Failed to read logged tickets from Excel: {e}")
                return []

class ExcelHandler(logging.Handler):
    def __init__(self, reporter: ExcelReporter):
        super().__init__()
        self.reporter = reporter
    def emit(self, record: logging.LogRecord):
        try:
            self.reporter.log_activity(record.levelname, self.format(record))
        except Exception: pass
