from flask import Flask, render_template, request, jsonify, redirect, url_for
from scraper import ShirazSilverScraper
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
import os
import threading

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production-12345')

# داده‌های global
data_store = {
    'prices': [],
    'last_update': None,
    'increase_percentage': 0,
    'mobile_number': None,
    'is_configured': False,
    'is_updating': False
}

scraper = ShirazSilverScraper()
update_lock = threading.Lock()

def update_prices_job():
    """بروزرسانی قیمت‌ها"""
    global data_store
    
    with update_lock:
        if data_store['is_updating']:
            print("⏳ بروزرسانی قبلی هنوز در حال اجراست")
            return
        
        data_store['is_updating'] = True
    
    try:
        print(f"[{datetime.now()}] 🔄 شروع بروزرسانی قیمت‌ها...")
        
        result = scraper.get_silver_prices()
        
        if result['success'] and result['prices']:
            # اعمال درصد افزایش
            updated_prices = []
            for item in result['prices']:
                updated_item = item.copy()
                updated_item['buy_price_original'] = item['buy_price']
                updated_item['sell_price_original'] = item['sell_price']
                
                increase = data_store['increase_percentage']
                updated_item['buy_price'] = int(item['buy_price'] * (1 + increase / 100))
                updated_item['sell_price'] = int(item['sell_price'] * (1 + increase / 100))
                updated_item['increase_percentage'] = increase
                
                updated_prices.append(updated_item)
            
            data_store['prices'] = updated_prices
            data_store['last_update'] = datetime.now().isoformat()
            print(f"✅ قیمت‌ها بروزرسانی شد: {len(updated_prices)} محصول")
        else:
            print(f"⚠️ خطا در بروزرسانی: {result.get('message', 'نامشخص')}")
            
    except Exception as e:
        print(f"❌ خطا در بروزرسانی: {e}")
    finally:
        data_store['is_updating'] = False

# Scheduler برای بروزرسانی خودکار هر 30 دقیقه
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=update_prices_job, trigger="interval", minutes=30, id='update_prices')
scheduler.start()

@app.route('/')
def index():
    """صفحه اصلی"""
    return render_template('index.html', 
                         prices=data_store['prices'],
                         last_update=data_store['last_update'],
                         increase_percentage=data_store['increase_percentage'],
                         is_configured=data_store['is_configured'])

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """صفحه تنظیمات اولیه"""
    if request.method == 'POST':
        try:
            mobile = request.form.get('mobile')
            increase_pct = float(request.form.get('increase_percentage', 0))
            
            data_store['mobile_number'] = mobile
            data_store['increase_percentage'] = increase_pct
            
            return redirect(url_for('verify'))
        except Exception as e:
            return render_template('setup.html', error=str(e))
    
    return render_template('setup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    """صفحه تایید کد SMS"""
    if request.method == 'POST':
        try:
            verification_code = request.form.get('code')
            mobile = data_store.get('mobile_number')
            
            if not mobile:
                return redirect(url_for('setup'))
            
            # ورود با کد
            success = scraper.login_with_code(mobile, verification_code)
            
            if success:
                data_store['is_configured'] = True
                # اولین بروزرسانی
                update_prices_job()
                return redirect(url_for('index'))
            else:
                return render_template('verify.html', 
                                     mobile=mobile, 
                                     error='کد نادرست است یا منقضی شده')
        except Exception as e:
            return render_template('verify.html', 
                                 mobile=data_store.get('mobile_number'), 
                                 error=str(e))
    
    return render_template('verify.html', mobile=data_store.get('mobile_number'))

@app.route('/api/prices')
def get_prices():
    """API برای دریافت قیمت‌ها"""
    return jsonify({
        'success': True,
        'prices': data_store['prices'],
        'last_update': data_store['last_update'],
        'increase_percentage': data_store['increase_percentage'],
        'is_configured': data_store['is_configured']
    })

@app.route('/api/refresh')
def refresh_prices():
    """بروزرسانی دستی"""
    try:
        update_prices_job()
        return jsonify({'success': True, 'message': 'بروزرسانی شروع شد'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/health')
def health():
    """بررسی سلامت"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'is_configured': data_store['is_configured']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
