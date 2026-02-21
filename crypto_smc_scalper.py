import sys
import subprocess
import os
import threading
import time
import io
from datetime import datetime

# GUI නොමැතිව ප්‍රස්තාර (Charts) සෑදීම සඳහා 'Agg' backend එක භාවිතා කිරීම
import matplotlib
matplotlib.use('Agg') 

# අවශ්‍ය packages ස්වයංක්‍රීයව ස්ථාපනය කිරීම (Install required packages)
def install_requirements():
    print("Packages ස්ථාපනය වෙමින් පවතී... (Installing required packages...)")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt", "pandas", "matplotlib", "requests", "pyTelegramBotAPI"])
        print("ස්ථාපනය සාර්ථකයි! (Installation complete!)\n")
    except Exception as e:
        print(f"දෝෂයකි (Error): {e}")
        sys.exit()

try:
    import ccxt
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    import requests
    import telebot
except ImportError:
    install_requirements()
    import ccxt
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.figure import Figure
    import requests
    import telebot

# ==========================================
# ටෙලිග්‍රෑම් සැකසුම් (TELEGRAM BOT SETTINGS)
# ==========================================
TELEGRAM_BOT_TOKEN = "8400049635:AAHleIW04zCFXiZXlRDQ8HT3BhqqlzKhChg" 
TELEGRAM_CHAT_ID = "@newwwwwwgw"   

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
last_report_msg_id = None

# දත්ත ගබඩාව සැකසීම (Database setup)
def setup_database():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scalping_signals.db')
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            symbol TEXT,
            signal_type TEXT,
            entry_price REAL,
            take_profit REAL,
            stop_loss REAL,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS msg_tracker (
            msg_id INTEGER PRIMARY KEY
        )
    ''')
    conn.commit()
    return conn

# මැසේජ් ID ගබඩා කිරීම (Track Telegram message IDs for deletion)
def track_msg(msg_id):
    if not msg_id: return
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scalping_signals.db'))
        conn.cursor().execute("INSERT INTO msg_tracker (msg_id) VALUES (?)", (msg_id,))
        conn.commit()
        conn.close()
    except: pass

# ටෙලිග්‍රෑම් පණිවිඩ මකා දැමීම (Delete Telegram Message)
def delete_telegram_message(msg_id):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not msg_id: return
    def _delete():
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'message_id': msg_id}
        try: requests.post(url, json=data)
        except: pass
    threading.Thread(target=_delete).start()

# ඡායාරූපය සහ විස්තරය යැවීම (Send photo and caption)
def send_telegram_photo_sync(buf, caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    files = {'photo': ('chart.png', buf.getvalue(), 'image/png')}
    data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
    try:
        res = requests.post(url, files=files, data=data).json()
        if res.get('ok'):
            msg_id = res['result']['message_id']
            track_msg(msg_id)
            return msg_id
    except Exception as e:
        print(f"Telegram Photo Error: {e}")
    return None

# පණිවිඩය වෙනස් කිරීම (Edit message caption)
def edit_telegram_caption_async(msg_id, new_caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not msg_id: return
    def _edit():
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageCaption"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'message_id': msg_id, 'caption': new_caption, 'parse_mode': 'Markdown'}
        try: requests.post(url, json=data)
        except: pass
    threading.Thread(target=_edit).start()

# රිප්ලයි කිරීම (Reply to a message)
def reply_telegram_message_async(msg_id, text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not msg_id: return
    def _reply():
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'reply_to_message_id': msg_id, 'parse_mode': 'Markdown'}
        try: 
            res = requests.post(url, json=data).json()
            if res.get('ok'): track_msg(res['result']['message_id'])
        except: pass
    threading.Thread(target=_reply).start()

# දෛනික වාර්තාව යාවත්කාලීන කිරීම (Update Daily Report in Telegram)
def update_daily_report_telegram_async(report_text):
    global last_report_msg_id
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    def _update():
        global last_report_msg_id
        if last_report_msg_id:
            del_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteMessage"
            del_data = {'chat_id': TELEGRAM_CHAT_ID, 'message_id': last_report_msg_id}
            try: requests.post(del_url, json=del_data)
            except: pass
        
        send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        send_data = {'chat_id': TELEGRAM_CHAT_ID, 'text': f"📊 *DAILY TRADING REPORT* 📊\n\n{report_text}", 'parse_mode': 'Markdown'}
        try: 
            res = requests.post(send_url, json=send_data).json()
            if res.get('ok'):
                last_report_msg_id = res['result']['message_id']
                track_msg(last_report_msg_id)
        except: pass
    threading.Thread(target=_update).start()

# ප්‍රස්තාරය නිර්මාණය කිරීම (Generate Candlestick Chart)
def generate_candlestick_chart(symbol, df, fvg_top=None, fvg_bottom=None):
    fig = Figure(figsize=(8, 4), dpi=100)
    ax = fig.add_subplot(111)
    
    df = df.tail(40).copy() 
    df['idx'] = range(len(df))
    
    up = df[df['close'] >= df['open']]
    down = df[df['close'] < df['open']]
    
    ax.vlines(df['idx'], df['low'], df['high'], color='#6B7280', linewidth=1)
    ax.vlines(up['idx'], up['open'], up['close'], color='#10B981', linewidth=4)
    ax.vlines(down['idx'], down['open'], down['close'], color='#EF4444', linewidth=4)
    
    if fvg_top and fvg_bottom:
        ax.axhspan(fvg_bottom, fvg_top, color='#F59E0B', alpha=0.3, label='FVG (Smart Money Zone)')
        ax.legend(loc="upper left")

    ax.set_title(f"SMC Market Setup: {symbol} (15m Timeframe)", fontsize=12, fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.4)
    ax.set_xticks([]) 
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

# ==========================================
# SMC TRADING LOGIC (15m High Accuracy)
# ==========================================

def get_market_data(symbol, timeframe='15m', limit=100):
    exchange = ccxt.binance()
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        return None

def analyze_smc_strict(df):
    if df is None or len(df) < 50:
        return None

    last = df.iloc[-1]
    entry_price = last['close']
    
    for i in range(len(df)-15, len(df)-2):
        if df['high'].iloc[i] < df['low'].iloc[i+2]:
            fvg_bottom = df['high'].iloc[i]
            fvg_top = df['low'].iloc[i+2]
            origin_low = df['low'].iloc[i:i+3].min()
            
            mitigated = False
            for j in range(i+3, len(df)-1):
                if df['low'].iloc[j] < fvg_bottom:
                    mitigated = True
                    break
            
            if not mitigated:
                if (last['low'] <= fvg_top) and (last['close'] > last['open']):
                    sl = origin_low * 0.999 
                    risk = entry_price - sl
                    if risk > 0 and (fvg_top - fvg_bottom) > (entry_price * 0.001): 
                        tp = entry_price + (risk * 2.5) 
                        return ('BUY', entry_price, tp, sl, risk, fvg_top, fvg_bottom)
                        
        elif df['low'].iloc[i] > df['high'].iloc[i+2]:
            fvg_top = df['low'].iloc[i]
            fvg_bottom = df['high'].iloc[i+2]
            origin_high = df['high'].iloc[i:i+3].max()
            
            mitigated = False
            for j in range(i+3, len(df)-1):
                if df['high'].iloc[j] > fvg_top:
                    mitigated = True
                    break
                    
            if not mitigated:
                if (last['high'] >= fvg_bottom) and (last['close'] < last['open']):
                    sl = origin_high * 1.001
                    risk = sl - entry_price
                    if risk > 0 and (fvg_top - fvg_bottom) > (entry_price * 0.001):
                        tp = entry_price - (risk * 2.5) 
                        return ('SELL', entry_price, tp, sl, risk, fvg_top, fvg_bottom)
    return None

def save_signal_to_db(conn, symbol, signal_type, entry, tp, sl):
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO signals (timestamp, symbol, signal_type, entry_price, take_profit, stop_loss, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (datetime.now(), symbol, signal_type, entry, tp, sl, 'PENDING'))
    conn.commit()
    return cursor.lastrowid

def update_signal_status(conn, sig_id, new_status):
    cursor = conn.cursor()
    cursor.execute("UPDATE signals SET status = ? WHERE id = ?", (new_status, sig_id))
    conn.commit()

def get_daily_report_string(conn):
    cursor = conn.cursor()
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    cursor.execute("SELECT status, COUNT(*) FROM signals WHERE timestamp >= ? GROUP BY status", (today_start,))
    results = cursor.fetchall()
    
    total = 0; wins = 0; losses = 0; pending = 0; be = 0
    for row in results:
        status, count = row
        total += count
        if status == 'WIN': wins = count
        elif status == 'LOSS': losses = count
        elif status == 'PENDING': pending = count
        elif status == 'BREAK EVEN': be = count
        
    report = f"🔹 **Total Trades Taken:** {total}\n"
    report += f"✅ **Total Wins:** {wins}\n"
    report += f"❌ **Losses:** {losses}\n"
    report += f"⚖️ **Break Even / Safe:** {be}\n"
    report += f"⏳ **Currently Running:** {pending}\n\n"
    
    if (wins + losses) > 0:
        win_rate = (wins / (wins + losses)) * 100
        report += f"🎯 **High Accuracy Win Rate:** {win_rate:.2f}%\n"
        report += f"💡 _We trade SMC concepts with strict 1-2% risk management. Quality over quantity._"
    else:
        report += "🎯 **Current Win Rate:** N/A"
    return report

def reset_telegram_history(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT msg_id FROM msg_tracker")
    messages = cursor.fetchall()
    for (msg_id,) in messages:
        delete_telegram_message(msg_id)
        time.sleep(0.1) 
    cursor.execute("DELETE FROM msg_tracker")
    conn.commit()

def reset_all_stats(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM signals")
        conn.commit()
    except Exception as e:
        print(f"Error clearing stats: {e}")


# ==========================================
# HEADLESS BOT CONTROLLER (පසුබිමේ ක්‍රියා කරන බොට්)
# ==========================================
class HeadlessScalper:
    def __init__(self):
        self.conn = setup_database()
        self.symbols_to_trade = [
            'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 
            'ADA/USDT', 'DOGE/USDT', 'MATIC/USDT', 'LINK/USDT', 'AVAX/USDT'
        ]
        self.is_running = False
        self.active_trades = {}
        self.thread = None

    def start_scanner(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.live_trading_loop)
            self.thread.daemon = True
            self.thread.start()
            return True
        return False

    def stop_scanner(self):
        if self.is_running:
            self.is_running = False
            return True
        return False

    def build_tg_caption(self, symbol, sig_type, entry, tp, sl, pnl_pct=0.0):
        sign = "+" if pnl_pct > 0 else ""
        return (f"🚨 *SMART MONEY SETUP: {symbol}* 🚨\n\n"
                f"📈 *Action:* {sig_type} (15m Timeframe)\n"
                f"🎯 *Entry:* {entry:.4f}\n"
                f"✅ *Target (TP):* {tp:.4f}\n"
                f"🛑 *Stop Loss:* {sl:.4f}\n\n"
                f"🛡️ *PROFESSIONAL RISK MANAGEMENT:*\n"
                f"• Only risk 1% of your total capital.\n"
                f"• Move your SL to *Break Even (BE)* when we hit 1:1 profit.\n"
                f"• Secure partials along the way. Stay disciplined.\n\n"
                f"📊 *Live PnL:* `{sign}{pnl_pct:.3f}%`")

    def live_trading_loop(self):
        exchange = ccxt.binance()
        print("Scanner Started...")
        
        while self.is_running:
            try:
                for symbol in self.symbols_to_trade:
                    ticker = exchange.fetch_ticker(symbol)
                    current_price = ticker['last']
                    
                    df = get_market_data(symbol, timeframe='15m')
                    signal_data = analyze_smc_strict(df)

                    if symbol not in self.active_trades:
                        if signal_data:
                            sig_type, entry, tp, sl, risk, fvg_top, fvg_bottom = signal_data
                            
                            db_id = save_signal_to_db(self.conn, symbol, sig_type, entry, tp, sl)
                            
                            img_buf = generate_candlestick_chart(symbol, df, fvg_top, fvg_bottom)
                            caption = self.build_tg_caption(symbol, sig_type, entry, tp, sl, 0.0)
                            tg_msg_id = send_telegram_photo_sync(img_buf, caption)
                            
                            self.active_trades[symbol] = {
                                'id': db_id,
                                'type': sig_type,
                                'entry': entry,
                                'tp': tp,
                                'sl': sl,
                                'initial_risk': risk, 
                                'be_set': False,
                                'tg_msg_id': tg_msg_id,
                                'last_tg_update': time.time()
                            }
                    
                    else:
                        trade = self.active_trades[symbol]
                        entry = trade['entry']
                        initial_risk = trade['initial_risk']
                        
                        if 'BUY' in trade['type']:
                            if current_price >= (entry + initial_risk) and not trade['be_set']:
                                trade['sl'] = entry
                                trade['be_set'] = True
                                
                            pnl_pct = ((current_price - entry) / entry) * 100
                            is_win = current_price >= trade['tp']
                            is_loss = current_price <= trade['sl']
                        else:
                            if current_price <= (entry - initial_risk) and not trade['be_set']:
                                trade['sl'] = entry
                                trade['be_set'] = True
                                
                            pnl_pct = ((entry - current_price) / entry) * 100
                            is_win = current_price <= trade['tp']
                            is_loss = current_price >= trade['sl']

                        if time.time() - trade['last_tg_update'] > 15:
                            if trade['tg_msg_id']:
                                new_caption = self.build_tg_caption(symbol, trade['type'], entry, trade['tp'], trade['sl'], pnl_pct)
                                edit_telegram_caption_async(trade['tg_msg_id'], new_caption)
                                trade['last_tg_update'] = time.time()

                        if is_win or is_loss:
                            if is_loss and trade['be_set']:
                                status = 'BREAK EVEN' 
                            else:
                                status = 'WIN' if is_win else 'LOSS'
                                
                            update_signal_status(self.conn, trade['id'], status)
                            
                            if status == 'LOSS':
                                if trade['tg_msg_id']:
                                    delete_telegram_message(trade['tg_msg_id'])
                            else:
                                if trade['tg_msg_id']:
                                    if status == 'WIN':
                                        reply_msg = f"🚀💸🎉 BOOM! {symbol} SMC Target Hit! Beautiful execution! Secure your profits. 🥂🔥"
                                    elif status == 'BREAK EVEN':
                                        reply_msg = f"🛡️ Trade for {symbol} closed at Break Even (BE). Capital completely protected. 🤝"
                                    reply_telegram_message_async(trade['tg_msg_id'], reply_msg)

                            del self.active_trades[symbol]
                            
                            report_str = get_daily_report_string(self.conn)
                            update_daily_report_telegram_async(report_str)

                time.sleep(2)

            except Exception as e:
                print(f"Error in scanning loop: {e}")
                time.sleep(5)

# ==========================================
# ටෙලිග්‍රෑම් විධානයන් (TELEGRAM COMMAND HANDLERS)
# ==========================================
scalper = HeadlessScalper()

@bot.message_handler(commands=['help', 'start'])
def send_help(message):
    help_text = (
        "🤖 *Premium Crypto Scalper Control Panel*\n\n"
        "Here are your available commands:\n"
        "▶️ /start_scanner - Start scanning the market\n"
        "⏹ /stop_scanner - Stop scanning\n"
        "📊 /stats - Show the current daily report\n"
        "🗑 /reset_stats - Delete all trade history & stats\n"
        "🧹 /reset_group - Delete all bot messages from the group\n"
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['start_scanner'])
def handle_start_scanner(message):
    if scalper.start_scanner():
        bot.reply_to(message, "✅ *Scanner Started!* Searching for 15m SMC setups...", parse_mode='Markdown')
    else:
        bot.reply_to(message, "⚠️ Scanner is already running.")

@bot.message_handler(commands=['stop_scanner'])
def handle_stop_scanner(message):
    if scalper.stop_scanner():
        bot.reply_to(message, "🛑 *Scanner Stopped.*", parse_mode='Markdown')
    else:
        bot.reply_to(message, "⚠️ Scanner is not running.")

@bot.message_handler(commands=['stats'])
def handle_stats(message):
    report = get_daily_report_string(scalper.conn)
    bot.reply_to(message, report, parse_mode='Markdown')

@bot.message_handler(commands=['reset_stats'])
def handle_reset_stats(message):
    reset_all_stats(scalper.conn)
    scalper.active_trades.clear()
    bot.reply_to(message, "🗑 *All trade stats and history have been completely reset!*", parse_mode='Markdown')

@bot.message_handler(commands=['reset_group'])
def handle_reset_group(message):
    bot.reply_to(message, "🧹 *Deleting all bot messages from the Telegram group...* Please wait.", parse_mode='Markdown')
    threading.Thread(target=lambda: reset_telegram_history(scalper.conn)).start()


if __name__ == "__main__":
    print("Bot is running in Headless Mode (Cloud Ready)...")
    print("Send /help to the bot on Telegram to view commands.")
    # Telegram polling අඛණ්ඩව ක්‍රියාත්මක කිරීම (Start Telegram polling)
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Telegram polling error: {e}")
            time.sleep(5)