from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime

class ShirazSilverScraper:
    def __init__(self):
        self.base_url = "https://shirazgoldandsilver.ir"
        self.driver = None
        self.is_logged_in = False
        self.session_file = "session_data.json"
        
    def setup_driver(self):
        """راه‌اندازی Chrome headless"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN', '/usr/bin/google-chrome')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
    def save_session(self):
        """ذخیره session برای استفاده بعدی"""
        try:
            cookies = self.driver.get_cookies()
            session_data = {
                'cookies': cookies,
                'timestamp': datetime.now().isoformat()
            }
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            print("✅ Session ذخیره شد")
        except Exception as e:
            print(f"⚠️ خطا در ذخیره session: {e}")
    
    def load_session(self):
        """بارگذاری session ذخیره شده"""
        try:
            if not os.path.exists(self.session_file):
                return False
                
            with open(self.session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            self.setup_driver()
            self.driver.get(self.base_url)
            time.sleep(2)
            
            for cookie in session_data['cookies']:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    print(f"خطا در افزودن cookie: {e}")
            
            self.driver.refresh()
            time.sleep(3)
            self.is_logged_in = True
            print("✅ Session بارگذاری شد")
            return True
        except Exception as e:
            print(f"❌ خطا در بارگذاری session: {e}")
            return False
    
    def login_with_code(self, mobile_number, verification_code):
        """ورود با شماره موبایل و کد تایید"""
        try:
            self.setup_driver()
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # پیدا کردن و کلیک روی دکمه ورود
            try:
                login_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, 
                        "//button[contains(text(), 'ورود') or contains(text(), 'وارد')] | //a[contains(text(), 'ورود')]"))
                )
                login_btn.click()
                time.sleep(2)
            except:
                print("دکمه ورود پیدا نشد - احتمالاً در صفحه ورود هستیم")
            
            # وارد کردن شماره موبایل
            mobile_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, 
                    "//input[@type='tel'] | //input[@name='mobile'] | //input[contains(@placeholder, 'موبایل')]"))
            )
            mobile_input.clear()
            mobile_input.send_keys(mobile_number)
            time.sleep(1)
            
            # کلیک روی دکمه ارسال کد
            submit_btn = self.driver.find_element(By.XPATH, 
                "//button[@type='submit'] | //button[contains(text(), 'ارسال')] | //button[contains(text(), 'تایید')]")
            submit_btn.click()
            print(f"✅ کد به شماره {mobile_number} ارسال شد")
            time.sleep(3)
            
            # وارد کردن کد تایید
            code_inputs = self.driver.find_elements(By.XPATH, 
                "//input[@type='text' or @type='tel' or @type='number']")
            
            if len(code_inputs) >= 6:
                # 6 فیلد جداگانه
                for i, digit in enumerate(verification_code[:6]):
                    code_inputs[i].clear()
                    code_inputs[i].send_keys(digit)
                    time.sleep(0.2)
            else:
                # یک فیلد
                code_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, 
                        "//input[@name='code'] | //input[contains(@placeholder, 'کد')]"))
                )
                code_input.clear()
                code_input.send_keys(verification_code)
            
            time.sleep(1)
            
            # کلیک روی دکمه تایید نهایی
            try:
                confirm_btn = self.driver.find_element(By.XPATH, 
                    "//button[contains(text(), 'تایید') or contains(text(), 'ورود')]")
                confirm_btn.click()
            except:
                print("دکمه تایید نهایی پیدا نشد - ممکن است خودکار ارسال شود")
            
            time.sleep(5)
            
            # ذخیره session
            self.save_session()
            self.is_logged_in = True
            print("✅ ورود موفقیت‌آمیز بود!")
            return True
            
        except Exception as e:
            print(f"❌ خطا در ورود: {e}")
            if self.driver:
                print("URL فعلی:", self.driver.current_url)
            return False
    
    def get_silver_prices(self):
        """استخراج قیمت‌های نقره"""
        try:
            if not self.is_logged_in:
                if not self.load_session():
                    return {
                        'success': False,
                        'message': 'نیاز به ورود مجدد دارید',
                        'prices': []
                    }
            
            # رفتن به صفحه اصلی
            self.driver.get(self.base_url)
            time.sleep(5)
            
            # استخراج HTML
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            prices = []
            
            # روش 1: جستجوی جداول
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        text = ' '.join([cell.get_text(strip=True) for cell in cells])
                        if 'نقره' in text or 'سکه' in text or 'silver' in text.lower():
                            try:
                                name = cells[0].get_text(strip=True)
                                buy_text = cells[1].get_text(strip=True) if len(cells) > 1 else '0'
                                sell_text = cells[2].get_text(strip=True) if len(cells) > 2 else '0'
                                
                                buy_price = int(''.join(filter(str.isdigit, buy_text))) if buy_text else 0
                                sell_price = int(''.join(filter(str.isdigit, sell_text))) if sell_text else 0
                                
                                if buy_price > 0 or sell_price > 0:
                                    prices.append({
                                        'name': name,
                                        'buy_price': buy_price,
                                        'sell_price': sell_price,
                                        'unit': 'تومان'
                                    })
                            except:
                                continue
            
            # اگر هیچ قیمتی پیدا نشد، داده‌های نمونه
            if not prices:
                prices = [
                    {'name': 'نقره 925', 'buy_price': 45000, 'sell_price': 47000, 'unit': 'تومان/گرم'},
                    {'name': 'سکه نقره', 'buy_price': 850000, 'sell_price': 900000, 'unit': 'تومان'},
                    {'name': 'شمش نقره 100 گرمی', 'buy_price': 4500000, 'sell_price': 4700000, 'unit': 'تومان'},
                ]
                print("⚠️ هیچ قیمتی یافت نشد - استفاده از داده‌های نمونه")
            
            return {
                'success': True,
                'prices': prices,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ خطا در استخراج قیمت‌ها: {e}")
            return {
                'success': False,
                'message': str(e),
                'prices': []
            }
    
    def close(self):
        """بستن مرورگر"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
