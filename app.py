from flask import Flask, render_template, request, jsonify, redirect, url_for, session
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
            
            print(f"\n{'='*60}")
            print(f"📱 درخواست ارسال کد SMS")
            print(f"{'='*60}")
            print(f"شماره: {mobile}")
            print(f"درصد افزایش: {increase_pct}%")
            print(f"{'='*60}\n")
            
            # اجرای Selenium برای درخواست کد
            try:
                scraper.setup_driver()
                scraper.driver.get(scraper.base_url)
                print(f"✅ سایت بارگذاری شد: {scraper.driver.current_url}")
                
                # پیدا کردن فیلد موبایل و ارسال
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                import time
                
                time.sleep(3)
                
                # تلاش برای پیدا کردن input موبایل
                mobile_selectors = [
                    "//input[@type='tel']",
                    "//input[@name='mobile']",
                    "//input[contains(@placeholder, 'موبایل')]",
                ]
                
                mobile_input = None
                for selector in mobile_selectors:
                    try:
                        mobile_input = WebDriverWait(scraper.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        print(f"✅ فیلد موبایل پیدا شد")
                        break
                    except:
                        continue
                
                if mobile_input:
                    mobile_input.clear()
                    mobile_input.send_keys(mobile)
                    print(f"✅ شماره {mobile} وارد شد")
                    
                    time.sleep(2)
                    
                    # کلیک روی دکمه ارسال
                    try:
                        submit_btn = scraper.driver.find_element(By.XPATH, "//button[@type='submit']")
                        submit_btn.click()
                        print(f"✅ دکمه ارسال کلیک شد")
                        print(f"📧 کد SMS به شماره {mobile} ارسال شد!")
                        data_store['sms_requested'] = True
                    except Exception as e:
                        print(f"⚠️ خطا در کلیک دکمه: {e}")
                else:
                    print(f"❌ فیلد موبایل پیدا نشد")
                    print(f"HTML صفحه:\n{scraper.driver.page_source[:500]}")
                
                time.sleep(3)
                
            except Exception as e:
                print(f"❌ خطا در Selenium: {e}")
                import traceback
                print(traceback.format_exc())
            
            return redirect(url_for('verify'))
            
        except Exception as e:
            print(f"❌ خطای کلی: {e}")
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
            
            print(f"\n{'='*60}")
            print(f"🔢 تایید کد SMS")
            print(f"{'='*60}")
            print(f"کد وارد شده: {verification_code}")
            print(f"{'='*60}\n")
            
            # وارد کردن کد در Selenium
            try:
                from selenium.webdriver.common.by import By
                import time
                
                # پیدا کردن فیلد کد
                code_inputs = scraper.driver.find_elements(By.XPATH, "//input[@type='text' or @type='tel']")
                
                if len(code_inputs) >= 6:
                    # 6 فیلد جداگانه
                    print(f"📝 وارد کردن کد در 6 فیلد جداگانه")
                    for i, digit in enumerate(verification_code[:6]):
                        code_inputs[i].clear()
                        code_inputs[i].send_keys(digit)
                        time.sleep(0.2)
                else:
                    # یک فیلد
                    print(f"📝 وارد کردن کد در یک فیلد")
                    code_inputs[-1].clear()  # آخرین input
                    code_inputs[-1].send_keys(verification_code)
                
                time.sleep(2)
                
                # کلیک دکمه تایید
                try:
                    confirm_btn = scraper.driver.find_element(By.XPATH, "//button[contains(text(), 'تایید')]")
                    confirm_btn.click()
                    print(f"✅ دکمه تایید کلیک شد")
                except:
                    print(f"⚠️ دکمه تایید پیدا نشد - ممکن است خودکار ارسال شود")
                
                time.sleep(5)
                
                # بررسی موفقیت
                if 'login' not in scraper.driver.current_url.lower():
                    scraper.save_session()
                    scraper.is_logged_in = True
                    data_store['is_configured'] = True
                    print(f"✅✅✅ ورود موفق!")
                    
                    # بستن driver
                    scraper.close()
                    
                    # اولین بروزرسانی
                    update_prices_job()
                    
                    return redirect(url_for('index'))
                else:
                    print(f"❌ کد نادرست یا منقضی شده")
                    return render_template('verify.html', 
                                         mobile=mobile, 
                                         error='کد نادرست است یا منقضی شده')
                    
            except Exception as e:
                print(f"❌ خطا در تایید کد: {e}")
                import traceback
                print(traceback.format_exc())
                return render_template('verify.html', 
                                     mobile=mobile, 
                                     error=f'خطا: {str(e)}')
                
        except Exception as e:
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
    app.run(host='0.0.0.0', port=port, debug=False)
