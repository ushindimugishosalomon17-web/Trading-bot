#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import requests
import os
from datetime import datetime, timedelta
from pythonpine import rsi, macd
import warnings
warnings.filterwarnings("ignore")

# ============================================
# CONFIGURATION (via variables d'environnement)
# ============================================
LOGIN = int(os.environ.get("MT5_LOGIN", "5049210516"))
PASSWORD = os.environ.get("MT5_PASSWORD", "8lLvX@Yb")
SERVER = os.environ.get("MT5_SERVER", "MetaQuotes-Demo")
SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_M5
VOLUME = 0.01

SUPERTREND_LENGTH = 10
SUPERTREND_FACTOR = 3.0
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
STOP_LOSS_PIPS = 30
TAKE_PROFIT_PIPS = 30

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# ============================================
# FONCTIONS
# ============================================
def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=10)
    except:
        pass

def calculate_supertrend(high, low, close, length=10, factor=3.0):
    hl2 = (high + low) / 2.0
    atr = np.zeros_like(close)
    tr = np.maximum(high - low, np.abs(high - np.roll(close, 1)))
    tr = np.maximum(tr, np.abs(low - np.roll(close, 1)))
    tr[0] = high[0] - low[0]
    for i in range(1, len(tr)):
        atr[i] = (atr[i-1] * (length - 1) + tr[i]) / length
    atr[length-1] = np.mean(tr[:length])
    upper_band = hl2 + (factor * atr)
    lower_band = hl2 - (factor * atr)
    trend = np.zeros_like(close)
    for i in range(1, len(close)):
        if close[i] > upper_band[i-1]:
            trend[i] = 1
        elif close[i] < lower_band[i-1]:
            trend[i] = -1
        else:
            trend[i] = trend[i-1]
    return trend

def connect_mt5():
    if not mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
        return False
    return True

def get_current_position(symbol):
    pos = mt5.positions_get(symbol=symbol)
    return pos[0] if pos else None

def execute_order(signal_type, last_close):
    point = mt5.symbol_info(SYMBOL).point
    if signal_type == "ACHAT":
        sl = last_close - STOP_LOSS_PIPS * 10 * point
        tp = last_close + TAKE_PROFIT_PIPS * 10 * point
        order_type = mt5.ORDER_TYPE_BUY
    else:
        sl = last_close + STOP_LOSS_PIPS * 10 * point
        tp = last_close - TAKE_PROFIT_PIPS * 10 * point
        order_type = mt5.ORDER_TYPE_SELL
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": VOLUME,
        "type": order_type,
        "price": last_close,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": 123456,
        "comment": "GitHubBot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        send_telegram(f"✅ Ordre {signal_type} exécuté\nSL={sl:.5f}\nTP={tp:.5f}")
    else:
        send_telegram(f"❌ Échec {signal_type}: {result.comment}")

# ============================================
# BOUCLE PRINCIPALE (exécutée une fois par déclenchement)
# ============================================
def main():
    print("🤖 Bot Sniper - Exécution unique")
    if not connect_mt5():
        print("❌ Échec connexion MT5")
        return
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 200)
    if rates is None or len(rates) < 100:
        mt5.shutdown()
        return
    df = pd.DataFrame(rates)
    close = df['close'].values
    high = df['high'].values
    low = df['low'].values
    st_trend = calculate_supertrend(high, low, close, SUPERTREND_LENGTH, SUPERTREND_FACTOR)
    rsi_vals = rsi(close, RSI_PERIOD)
    macd_line, signal_line, _ = macd(close, MACD_FAST, MACD_SLOW, MACD_SIGNAL)
    last_st = st_trend[-1]
    last_rsi = rsi_vals[-1]
    prev_rsi = rsi_vals[-2]
    last_macd = macd_line[-1]
    last_sig = signal_line[-1]
    prev_macd = macd_line[-2]
    prev_sig = signal_line[-2]
    last_close = close[-1]
    buy_signal = (last_st == 1 and prev_rsi <= 30 and last_rsi > 30 and prev_macd <= prev_sig and last_macd > last_sig)
    sell_signal = (last_st == -1 and prev_rsi >= 70 and last_rsi < 70 and prev_macd >= prev_sig and last_macd < last_sig)
    position = get_current_position(SYMBOL)
    if (buy_signal or sell_signal) and position is None:
        signal_type = "ACHAT" if buy_signal else "VENTE"
        send_telegram(f"🎯 SIGNAL {signal_type}\nPaire: {SYMBOL}\nPrix: {last_close:.5f}")
        execute_order(signal_type, last_close)
    else:
        print(f"Pas de signal. Close={last_close:.5f} ST={'📈' if last_st==1 else '📉'} RSI={last_rsi:.1f}")
    mt5.shutdown()

if __name__ == "__main__":
    main()
