from flask import Flask, render_template, request, jsonify, redirect, url_for
from scraper import ShirazSilverScraper
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import json
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

scraper = ShirazSilverScraper()
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
        
        result = scraper.get_silver_prices()
        
        if result['success'] and result['prices']:
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
            
            # تست: آیا Selenium کار می‌کند؟
            try:
                logger.info("🔧 شروع راه‌اندازی Selenium...")
                scraper.setup_driver()
                logger.info("✅ Selenium driver ساخته شد")
                
                logger.info(f"🌐 در حال باز کردن سایت: {scraper.base_url}")
                scraper.driver.get(scraper.base_url)
                logger.info(f"✅ سایت بارگذاری شد: {scraper.driver.current_url}")
                
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                import time
                
                time.sleep(5)
                
                # گرفتن screenshot صفحه برای دیباگ
                logger.info(f"📸 Title صفحه: {scraper.driver.title}")
                
                # تلاش برای پیدا کردن input موبایل
                mobile_selectors = [
                    "//input[@type='tel']",
                    "//input[@name='mobile']",
                    "//input[@name='phone']",
                    "//input[contains(@placeholder, 'موبایل')]",
                    "//input[contains(@placeholder, 'شماره')]",
                ]
                
                mobile_input = None
                for idx, selector in enumerate(mobile_selectors):
                    try:
                        logger.info(f"🔍 تلاش selector {idx+1}: {selector}")
                        mobile_input = WebDriverWait(scraper.driver, 3).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        logger.info(f"✅ فیلد موبایل پیدا شد با selector: {selector}")
                        break
                    except Exception as e:
                        logger.warning(f"❌ Selector {idx+1} کار نکرد: {str(e)[:100]}")
                        continue
                
                if mobile_input:
                    mobile_input.clear()
                    mobile_input.send_keys(mobile)
                    logger.info(f"✅ شماره {mobile} وارد شد")
                    
                    time.sleep(2)
                    
                    # کلیک روی دکمه ارسال
                    submit_selectors = [
                        "//button[@type='submit']",
                        "//button[contains(text(), 'ارسال')]",
                        "//input[@type='submit']",
                    ]
                    
                    submitted = False
                    for idx, selector in enumerate(submit_selectors):
                        try:
                            logger.info(f"🔍 تلاش کلیک دکمه {idx+1}: {selector}")
                            submit_btn = scraper.driver.find_element(By.XPATH, selector)
                            submit_btn.click()
                            logger.info(f"✅ دکمه ارسال کلیک شد")
                            submitted = True
                            break
                        except Exception as e:
                            logger.warning(f"❌ دکمه {idx+1} کار نکرد: {str(e)[:100]}")
                            continue
                    
                    if submitted:
                        logger.info(f"📧 درخواست کد SMS به شماره {mobile} ارسال شد!")
                        data_store['sms_requested'] = True
                        time.sleep(3)
                    else:
                        logger.error("❌ هیچ دکمه ارسالی پیدا نشد")
                        logger.info("📄 HTML صفحه (اول 1000 کاراکتر):")
                        logger.info(scraper.driver.page_source[:1000])
                else:
                    logger.error("❌ فیلد موبایل پیدا نشد")
                    logger.info("📄 HTML صفحه (اول 1000 کاراکتر):")
                    logger.info(scraper.driver.page_source[:1000])
                
            except Exception as e:
                logger.error(f"❌ خطای Selenium: {e}", exc_info=True)
            
            return redirect(url_for('verify'))
            
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
            
            try:
                from selenium.webdriver.common.by import By
                import time
                
                # پیدا کردن فیلد کد
                code_inputs = scraper.driver.find_elements(By.XPATH, "//input")
                logger.info(f"📝 تعداد input پیدا شده: {len(code_inputs)}")
                
                if len(code_inputs) >= 6:
                    logger.info(f"📝 وارد کردن کد در 6 فیلد جداگانه")
                    for i, digit in enumerate(verification_code[:6]):
                        code_inputs[i].clear()
                        code_inputs[i].send_keys(digit)
                        time.sleep(0.2)
                elif len(code_inputs) > 0:
                    logger.info(f"📝 وارد کردن کد در آخرین فیلد")
                    code_inputs[-1].clear()
                    code_inputs[-1].send_keys(verification_code)
                else:
                    logger.error("❌ هیچ input پیدا نشد!")
                
                time.sleep(3)
                
                # کلیک دکمه تایید
                try:
                    confirm_btn = scraper.driver.find_element(By.XPATH, "//button[contains(text(), 'تایید') or contains(text(), 'ورود')]")
                    confirm_btn.click()
                    logger.info(f"✅ دکمه تایید کلیک شد")
                except Exception as e:
                    logger.warning(f"⚠️ دکمه تایید پیدا نشد: {e}")
                
                time.sleep(5)
                
                # بررسی موفقیت
                current_url = scraper.driver.current_url
                logger.info(f"🌐 URL فعلی بعد از تایید: {current_url}")
                
                if 'login' not in current_url.lower():
                    scraper.save_session()
                    scraper.is_logged_in = True
                    data_store['is_configured'] = True
                    logger.info(f"✅✅✅ ورود موفق!")
                    
                    scraper.close()
                    update_prices_job()
                    
                    return redirect(url_for('index'))
                else:
                    logger.error(f"❌ ورود ناموفق - هنوز در صفحه login")
                    return render_template('verify.html', 
                                         mobile=mobile, 
                                         error='کد نادرست است یا منقضی شده')
                    
            except Exception as e:
                logger.error(f"❌ خطا در تایید کد: {e}", exc_info=True)
                return render_template('verify.html', 
                                     mobile=mobile, 
                                     error=f'خطا: {str(e)}')
                
        except Exception as e:
            logger.error(f"❌ خطای کلی در verify: {e}", exc_info=True)
            return render_template('verify.html', 
                                 mobile=data_store.get('mobile_number'), 
                                 error=str(e))
    
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
