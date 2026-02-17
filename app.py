from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from api_scraper import ShirazSilverAPI
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import threading
import logging
import sys

# تنظیم logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production-12345')

# داده‌های global
data_store = {
    'prices': [],
    'last_update': None,
    'increase_percentage': 0,
    'mobile_number': None,
    'is_configured': False,
    'is_updating': False,
    'sms_requested': False
}

api_scraper = ShirazSilverAPI()
update_lock = threading.Lock()

def update_prices_job():
    """بروزرسانی قیمت‌ها"""
    global data_store
    
    with update_lock:
        if data_store['is_updating']:
            logger.info("⏳ بروزرسانی قبلی هنوز در حال اجراست")
            return
        
        data_store['is_updating'] = True
    
    try:
        logger.info(f"🔄 شروع بروزرسانی قیمت‌ها...")
        
        result = api_scraper.get_silver_prices()
        
        if result['success'] and result['prices']:
            updated_prices = []
            for item in result['prices']:
                updated_item = item.copy()
                
                # اعمال درصد افزایش
                buy_price = item.get('buy_price', 0) or item.get('buyPrice', 0) or item.get('price', 0)
                sell_price = item.get('sell_price', 0) or item.get('sellPrice', 0) or item.get('price', 0)
                
                updated_item['buy_price_original'] = buy_price
                updated_item['sell_price_original'] = sell_price
                
                increase = data_store['increase_percentage']
                updated_item['buy_price'] = int(buy_price * (1 + increase / 100))
                updated_item['sell_price'] = int(sell_price * (1 + increase / 100))
                updated_item['increase_percentage'] = increase
                
                updated_prices.append(updated_item)
            
            data_store['prices'] = updated_prices
            data_store['last_update'] = datetime.now().isoformat()
            logger.info(f"✅ قیمت‌ها بروزرسانی شد: {len(updated_prices)} محصول")
        else:
            logger.warning(f"⚠️ خطا در بروزرسانی: {result.get('message', 'نامشخص')}")
            
    except Exception as e:
        logger.error(f"❌ خطا در بروزرسانی: {e}", exc_info=True)
    finally:
        data_store['is_updating'] = False

# Scheduler
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
            
            logger.info("="*60)
            logger.info(f"📱 درخواست ارسال کد SMS")
            logger.info(f"شماره: {mobile}")
            logger.info(f"درصد افزایش: {increase_pct}%")
            logger.info("="*60)
            
            # ارسال OTP با API
            result = api_scraper.send_otp(mobile)
            
            if result['success']:
                logger.info(f"✅✅✅ SMS به شماره {mobile} ارسال شد!")
                data_store['sms_requested'] = True
                return redirect(url_for('verify'))
            else:
                logger.error(f"❌ خطا در ارسال SMS: {result['message']}")
                return render_template('setup.html', error=result['message'])
            
        except Exception as e:
            logger.error(f"❌ خطای کلی در setup: {e}", exc_info=True)
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
            
            logger.info("="*60)
            logger.info(f"🔢 تایید کد SMS")
            logger.info(f"کد وارد شده: {verification_code}")
            logger.info("="*60)
            
            # تایید OTP با API
            result = api_scraper.verify_otp(mobile, verification_code)
            
            if result['success']:
                logger.info(f"✅✅✅ ورود موفق!")
                data_store['is_configured'] = True
                
                # اولین بروزرسانی
                update_prices_job()
                
                return redirect(url_for('index'))
            else:
                logger.error(f"❌ کد نادرست: {result['message']}")
                return render_template('verify.html', 
                                     mobile=mobile, 
                                     error=result['message'],
                                     sms_sent=data_store.get('sms_requested', False))
                
        except Exception as e:
            logger.error(f"❌ خطای کلی در verify: {e}", exc_info=True)
            return render_template('verify.html', 
                                 mobile=data_store.get('mobile_number'), 
                                 error=str(e),
                                 sms_sent=data_store.get('sms_requested', False))
    
    return render_template('verify.html', 
                          mobile=data_store.get('mobile_number'),
                          sms_sent=data_store.get('sms_requested', False))

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
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
