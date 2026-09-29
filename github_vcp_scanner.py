#!/usr/bin/env python3
"""
VCP DAILY SCANNER - GITHUB ACTIONS VERSION
Production-grade daily screening deployed on GitHub
Runs every day at 4 PM IST via GitHub Actions - no server needed!

Features:
- Scans 105 NSE stocks (Nifty-50 + Midcap)
- Calculates VCP scores 0-10
- Generates beautiful HTML email reports
- Saves results to GitHub
- Uses GitHub secrets for secure credentials
"""

import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import json
import os
import warnings
warnings.filterwarnings('ignore')

class GitHubVCPScanner:
    """VCP Scanner designed for GitHub Actions environment"""

    def __init__(self):
        self.today = datetime.now()
        self.report_date = self.today.strftime('%Y-%m-%d')

        # Get credentials from GitHub secrets
        self.sender_email = os.getenv('SENDER_EMAIL', '')
        self.app_password = os.getenv('APP_PASSWORD', '')
        self.recipient_email = os.getenv('RECIPIENT_EMAIL', self.sender_email)

        # NSE Stock Universe (105 stocks)
        self.nifty_50 = [
            'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS',
            'ICICIBANK.NS', 'SBIN.NS', 'WIPRO.NS', 'MARUTI.NS', 'BAJAJFINSV.NS',
            'LT.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'SUNPHARMA.NS', 'KOTAKBANK.NS',
            'TECHM.NS', 'NTPC.NS', 'ONGC.NS', 'JSWSTEEL.NS', 'INDUSINDBK.NS',
            'POWERGRID.NS', 'HCLTECH.NS', 'BHARTIARTL.NS', 'BPCL.NS', 'DRREDDY.NS',
            'CIPLA.NS', 'SBILIFE.NS', 'TITAN.NS', 'M&M.NS', 'BAJAJ-AUTO.NS',
            'HDFCLIFE.NS', 'GRASIM.NS', 'IDFCFIRSTB.NS', 'APOLLOHOSP.NS', 'HEROMOTOCO.NS',
            'TATACONSUM.NS', 'UPL.NS', 'LTIM.NS', 'TATAMOTORS.NS', 'BOSCHLTD.NS',
            'DIVISLAB.NS', 'LUPIN.NS', 'ALKEM.NS', 'EICHERMOT.NS', 'BRITANNIA.NS',
            'NESTLEIND.NS', 'BERGEPAINT.NS', 'PAGEIND.NS', 'PIDILITIND.NS', 'SIEMENSIND.NS'
        ]

        self.midcap_100 = [
            'MEESHO.NS', 'NYKAA.NS', 'ZOMATO.NS', 'PAYTM.NS', 'POLICYBAZAAR.NS',
            'CREDACCESS.NS', 'MUTHOOTFIN.NS', 'MANAPPURAM.NS', 'MINDTREE.NS', 'KPIT.NS',
            'POLYCAB.NS', 'HAVELLS.NS', 'CROMPTON.NS', 'THERMAX.NS', 'RATNAMANI.NS',
            'NATIONALUM.NS', 'JINDALSTEL.NS', 'SAIL.NS', 'VEDANTA.NS', 'COALINDIA.NS',
            'GAIL.NS', 'IOC.NS', 'INDIGO.NS', 'SPICEJET.NS', 'GODREJCP.NS',
            'GODREJPROP.NS', 'MAHLOG.NS', 'IBREALEST.NS', 'DLF.NS', 'SUNTV.NS',
            'AUBANK.NS', 'BANDHANBNK.NS', 'FEDERALBNK.NS', 'IDBI.NS', 'ICICIPRULI.NS',
            'MAXHEALTH.NS', 'APOLLOTYRE.NS', 'CRISIL.NS', 'NAUKRI.NS', 'JUST.NS',
            'ABCAPITAL.NS', 'PFC.NS', 'REC.NS', 'IRCTC.NS', 'GMRINFRA.NS',
            'ADANIGREEN.NS', 'ADANIPOWER.NS', 'ADANIPORTS.NS', 'TATASTEEL.NS', 'ULTRACEMCO.NS',
            'AMBUJACEM.NS', 'SHREECEM.NS', 'GLAND.NS', 'INFIBEAM.NS', 'KPITTECH.NS',
            'LTTS.NS', 'JKPAPER.NS', 'PAGEINDUST.NS', 'STARCEMSEC.NS', 'MAHABANK.NS',
            'HSCL.NS', 'CASTROLIND.NS', 'ECLERX.NS', 'VIPINDUSTRI.NS', 'CARERATING.NS'
        ]

        self.stock_list = self.nifty_50 + self.midcap_100
        self.results = []

    def fetch_stock_data(self, symbol, periods=26):
        """Fetch 26 weeks of weekly data"""
        try:
            end_date = self.today
            start_date = end_date - timedelta(weeks=periods)

            df = yf.download(symbol, start=start_date, end=end_date,
                           interval='1wk', progress=False)

            if df.empty or len(df) < 12:
                return None

            return df
        except Exception as e:
            return None

    def calculate_vcp_metrics(self, df):
        """Calculate all VCP metrics from price data"""
        if len(df) < 12:
            return None

        try:
            # Uptrend strength
            price_12w_ago = df.iloc[-12]['Close']
            price_6w_ago = df.iloc[-6]['Close']
            price_now = df.iloc[-1]['Close']

            uptrend_gain = ((price_6w_ago - price_12w_ago) / price_12w_ago * 100) \
                          if price_12w_ago > 0 else 0
            current_pullback = ((price_now - price_6w_ago) / price_6w_ago * 100) \
                             if price_6w_ago > 0 else 0

            # Consolidation tightness
            recent_high = df.iloc[-4:]['High'].max()
            recent_low = df.iloc[-4:]['Low'].min()
            recent_range = ((recent_high - recent_low) / recent_low * 100)

            full_ranges = df['High'] - df['Low']
            avg_range = (full_ranges.mean() / df['Close'].mean() * 100)
            compression_ratio = recent_range / avg_range if avg_range > 0 else 0

            # Volume contraction
            recent_volumes = df.iloc[-8:]['Volume'].values
            vol_changes = []
            for i in range(1, len(recent_volumes)):
                if recent_volumes[i-1] > 0:
                    change = ((recent_volumes[i] - recent_volumes[i-1]) /
                            recent_volumes[i-1] * 100)
                    vol_changes.append(change)

            avg_contraction = np.mean(vol_changes) if vol_changes else 0

            # Candle compression
            recent_ranges = df.iloc[-6:]['High'] - df.iloc[-6:]['Low']
            older_ranges = df.iloc[-12:-6]['High'] - df.iloc[-12:-6]['Low']

            recent_avg = recent_ranges.mean()
            older_avg = older_ranges.mean()
            candle_compression = ((recent_avg / older_avg - 1) * 100) \
                                if older_avg > 0 else 0

            # ATR compression
            high_low = df['High'] - df['Low']
            high_close = abs(df['High'] - df['Close'].shift())
            low_close = abs(df['Low'] - df['Close'].shift())

            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            atr = true_range.rolling(20).mean()

            recent_atr = atr.iloc[-4:].mean()
            avg_atr = atr.mean()
            atr_compression = ((recent_atr / avg_atr - 1) * 100) if avg_atr > 0 else 0

            return {
                'uptrend_gain': uptrend_gain,
                'current_pullback': current_pullback,
                'compression_ratio': compression_ratio,
                'recent_range': recent_range,
                'vol_contraction': avg_contraction,
                'candle_compression': candle_compression,
                'atr_compression': atr_compression,
                'current_price': df.iloc[-1]['Close'],
                'consolidation_high': recent_high,
                'consolidation_low': recent_low
            }

        except Exception as e:
            return None

    def score_stock(self, symbol):
        """Score stock on VCP criteria (0-10)"""
        df = self.fetch_stock_data(symbol)

        if df is None:
            return None

        metrics = self.calculate_vcp_metrics(df)
        if metrics is None:
            return None

        # Scoring (0-10 scale)
        score = 0

        # Uptrend strength (2 points max)
        if metrics['uptrend_gain'] >= 30:
            score += 2
        elif metrics['uptrend_gain'] >= 20:
            score += 1.5
        elif metrics['uptrend_gain'] >= 10:
            score += 1

        # Consolidation tightness (2 points max)
        if metrics['compression_ratio'] <= 0.5:
            score += 2
        elif metrics['compression_ratio'] <= 0.7:
            score += 1.5
        elif metrics['compression_ratio'] <= 1.0:
            score += 1

        # Volume contraction (3 points max) - CORE SIGNAL
        if metrics['vol_contraction'] < -5:
            score += 3
        elif metrics['vol_contraction'] < -2:
            score += 2
        elif metrics['vol_contraction'] < 0:
            score += 1

        # Candle compression (2 points max)
        if metrics['candle_compression'] < -30:
            score += 2
        elif metrics['candle_compression'] < -15:
            score += 1.5
        elif metrics['candle_compression'] < 0:
            score += 1

        # ATR compression (1 point max)
        if metrics['atr_compression'] < -40:
            score += 1
        elif metrics['atr_compression'] < -30:
            score += 0.5

        # Calculate entry/stop/targets
        entry_price = metrics['consolidation_high'] * 1.005
        stop_loss = metrics['consolidation_low'] * 0.95
        target_1 = entry_price * 1.15
        target_2 = entry_price * 1.30

        risk_amount = entry_price - stop_loss
        reward_amount_1 = target_1 - entry_price
        risk_reward = reward_amount_1 / risk_amount if risk_amount > 0 else 0

        return {
            'stock': symbol.replace('.NS', ''),
            'score': round(score, 2),
            'current_price': round(metrics['current_price'], 2),
            'entry_price': round(entry_price, 2),
            'stop_loss': round(stop_loss, 2),
            'target_1': round(target_1, 2),
            'target_2': round(target_2, 2),
            'uptrend_gain_pct': round(metrics['uptrend_gain'], 2),
            'consolidation_range': round(metrics['recent_range'], 2),
            'volume_contraction_rate_pct': round(metrics['vol_contraction'], 2),
            'consolidation_ratio': round(metrics['compression_ratio'], 2),
            'candle_compression_pct': round(metrics['candle_compression'], 2),
            'atr_compression_pct': round(metrics['atr_compression'], 2),
            'risk_amount': round(risk_amount, 2),
            'reward_amount_1': round(reward_amount_1, 2),
            'risk_reward_ratio': round(risk_reward, 2),
            'recommendation': self.get_recommendation(score),
            'status': self.get_status(score)
        }

    def get_recommendation(self, score):
        """Get action recommendation based on score"""
        if score >= 9:
            return "🚀 BUY IMMEDIATELY"
        elif score >= 7.5:
            return "🔥 STRONG BUY"
        elif score >= 6:
            return "✅ MONITOR"
        elif score >= 4:
            return "🟡 WATCH"
        else:
            return "❌ SKIP"

    def get_status(self, score):
        """Get status emoji"""
        if score >= 7.5:
            return "🔥"
        elif score >= 6:
            return "✅"
        elif score >= 4:
            return "🟡"
        else:
            return "❌"

    def scan_all_stocks(self):
        """Scan all stocks"""
        print(f"\n[VCP Daily Scanner - {self.report_date}]")
        print(f"Scanning {len(self.stock_list)} stocks...\n")

        results = []
        for i, stock in enumerate(self.stock_list, 1):
            print(f"[{i:3d}/{len(self.stock_list)}] {stock}", end='\r')

            result = self.score_stock(stock)
            if result and result['score'] >= 4.0:
                results.append(result)

        print(" " * 80)

        # Sort by score
        results.sort(key=lambda x: x['score'], reverse=True)
        self.results = results

        print(f"\n✅ Found {len(results)} quality candidates (score 4.0+)")
        return results

    def generate_html_report(self):
        """Generate beautiful HTML email"""

        if not self.results:
            return self._generate_empty_html()

        top_5 = self.results[:5]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .summary {{
            padding: 20px 30px;
            background-color: #f9f9f9;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-around;
        }}
        .stat {{
            text-align: center;
        }}
        .stat-value {{
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }}
        .content {{
            padding: 30px;
        }}
        .section-title {{
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin: 30px 0 20px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        .candidate {{
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
            background-color: #fafafa;
        }}
        .candidate-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .candidate-name {{
            font-size: 18px;
            font-weight: bold;
        }}
        .score-badge {{
            background-color: #667eea;
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-weight: bold;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin: 15px 0;
        }}
        .metric {{
            background-color: white;
            padding: 12px;
            border-radius: 4px;
            border-left: 3px solid #667eea;
        }}
        .metric-label {{
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            font-weight: 600;
        }}
        .metric-value {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
            margin-top: 4px;
        }}
        .price-row {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin: 12px 0;
        }}
        .price-item {{
            background-color: white;
            padding: 10px;
            border-radius: 4px;
            text-align: center;
            border-left: 3px solid #667eea;
        }}
        .price-label {{
            font-size: 10px;
            color: #666;
            text-transform: uppercase;
        }}
        .price-value {{
            font-size: 14px;
            font-weight: bold;
            margin-top: 4px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background-color: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        .footer {{
            background-color: #f5f5f5;
            padding: 20px 30px;
            text-align: center;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 VCP Daily Scan Report</h1>
            <p>High-Quality Trading Candidates · {self.report_date}</p>
        </div>

        <div class="summary">
            <div class="stat">
                <div class="stat-value">{len(self.results)}</div>
                <div class="stat-label">Quality Candidates</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len([r for r in self.results if r['score'] >= 7.5])}</div>
                <div class="stat-label">Strong Buy</div>
            </div>
            <div class="stat">
                <div class="stat-value">{len([r for r in self.results if r['score'] >= 6])}</div>
                <div class="stat-label">Monitor</div>
            </div>
        </div>

        <div class="content">
            <div class="section-title">🔥 Top 5 Candidates</div>
"""

        for i, result in enumerate(top_5, 1):
            html += f"""
            <div class="candidate">
                <div class="candidate-header">
                    <div>
                        <div class="candidate-name">#{i} {result['stock']}</div>
                        <div style="color: #667eea; font-size: 14px;">{result['recommendation']}</div>
                    </div>
                    <div class="score-badge">{result['score']}/10</div>
                </div>

                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Current Price</div>
                        <div class="metric-value">₹{result['current_price']}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Uptrend Gain</div>
                        <div class="metric-value">{result['uptrend_gain_pct']}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Volume Contraction</div>
                        <div class="metric-value">{result['volume_contraction_rate_pct']}%/week</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Consolidation</div>
                        <div class="metric-value">{result['consolidation_range']}%</div>
                    </div>
                </div>

                <div style="border-top: 1px solid #ddd; padding-top: 12px;">
                    <div class="price-row">
                        <div class="price-item">
                            <div class="price-label">Entry</div>
                            <div class="price-value">₹{result['entry_price']}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Stop</div>
                            <div class="price-value">₹{result['stop_loss']}</div>
                        </div>
                        <div class="price-item">
                            <div class="price-label">Target 1</div>
                            <div class="price-value">₹{result['target_1']}</div>
                        </div>
                    </div>
                    <div style="text-align: center; margin-top: 10px; font-size: 13px; color: #666;">
                        Risk/Reward: 1:{result['risk_reward_ratio']}
                        {'✅' if result['risk_reward_ratio'] >= 1.5 else '⚠️'}
                    </div>
                </div>
            </div>
"""

        html += f"""
            <div class="section-title">📋 All {len(self.results)} Candidates</div>
            <table>
                <thead>
                    <tr>
                        <th>Stock</th>
                        <th>Score</th>
                        <th>Current</th>
                        <th>Entry</th>
                        <th>Stop</th>
                        <th>Target 1</th>
                        <th>Vol %</th>
                        <th>R/R</th>
                    </tr>
                </thead>
                <tbody>
"""

        for result in self.results:
            html += f"""
                    <tr>
                        <td><strong>{result['stock']}</strong></td>
                        <td>{result['score']}/10</td>
                        <td>₹{result['current_price']}</td>
                        <td>₹{result['entry_price']}</td>
                        <td>₹{result['stop_loss']}</td>
                        <td>₹{result['target_1']}</td>
                        <td>{result['volume_contraction_rate_pct']}%</td>
                        <td>1:{result['risk_reward_ratio']}</td>
                    </tr>
"""

        html += """
                </tbody>
            </table>

            <div class="section-title">📚 How to Use This Report</div>
            <div style="background-color: #f9f9f9; padding: 20px; border-radius: 6px; margin: 20px 0;">
                <p><strong>📌 VCP Strategy:</strong></p>
                <ul>
                    <li><strong>Entry:</strong> Buy at breakout (entry price shown)</li>
                    <li><strong>Stop Loss:</strong> Exit if price closes below stop</li>
                    <li><strong>Target 1:</strong> Take 50% profit at +15%</li>
                    <li><strong>Target 2:</strong> Take 50% profit at +30%</li>
                </ul>
                <p><strong>⚡ Position Sizing:</strong> Risk only 2% per trade</p>
                <p><strong>📊 Volume Contraction:</strong> More negative = stronger signal</p>
            </div>
        </div>

        <div class="footer">
            <p>🤖 VCP Daily Scanner via GitHub Actions | {self.report_date} at {datetime.now().strftime('%H:%M IST')}</p>
            <p style="margin-top: 10px; font-size: 11px;">Always do your own due diligence. Past performance ≠ future results.</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _generate_empty_html(self):
        """Generate email when no candidates"""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; background-color: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; text-align: center; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 VCP Daily Scan</h1>
        </div>
        <div class="content">
            <h2>No Quality Candidates Today</h2>
            <p>The market did not produce any stocks meeting VCP criteria (score 4.0+) on {self.report_date}.</p>
            <p style="color: #999;">This is normal. VCP patterns take 40-75 days to form.</p>
        </div>
    </div>
</body>
</html>
"""

    def send_email(self, html_content):
        """Send email via Gmail"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"📊 VCP Report {self.report_date}: {len(self.results)} candidates"
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email

            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(self.sender_email, self.app_password)
                server.sendmail(self.sender_email, self.recipient_email, msg.as_string())

            print(f"✅ Email sent to {self.recipient_email}")
            return True

        except Exception as e:
            print(f"❌ Email error: {e}")
            return False

    def save_results(self):
        """Save results to CSV for GitHub"""
        if not self.results:
            print("No results to save")
            return

        df = pd.DataFrame(self.results)
        csv_file = f"vcp_results_{self.report_date}.csv"
        df.to_csv(csv_file, index=False)
        print(f"✅ Results saved to {csv_file}")

        # Also save JSON
        json_file = f"vcp_results_{self.report_date}.json"
        with open(json_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✅ Results saved to {json_file}")


def main():
    scanner = GitHubVCPScanner()

    # Scan all stocks
    results = scanner.scan_all_stocks()

    if not results:
        print("⚠️  No quality candidates found")
    else:
        print(f"\n✅ Found {len(results)} quality candidates!")
        for i, r in enumerate(results[:5], 1):
            print(f"  {i}. {r['stock']:15s} - Score: {r['score']}/10 {r['status']}")

    # Generate HTML report
    html_report = scanner.generate_html_report()

    # Send email
    print("\n📧 Sending email...")
    scanner.send_email(html_report)

    # Save results
    print("\n💾 Saving results...")
    scanner.save_results()

    print("\n✨ Done!")


if __name__ == '__main__':
    main()
