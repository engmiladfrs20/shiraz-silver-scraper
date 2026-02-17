import requests
import time
import json
from datetime import datetime

class ShirazSilverAPI:
    """اسکریپر با استفاده مستقیم از API"""
    
    def __init__(self):
        self.base_url = "https://api.shirazgoldandsilver.ir/api/v1"
        self.website_url = "https://shirazgoldandsilver.ir"
        self.session = requests.Session()
        self.is_logged_in = False
        self.token = None
        
        # Headers مطابق با مرورگر
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
            'Content-Type': 'application/json',
            'Origin': self.website_url,
            'Referer': f'{self.website_url}/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        })
    
    def send_otp(self, mobile):
        """ارسال کد OTP به شماره موبایل"""
        try:
            url = f"{self.base_url}/auth/check-mobile-exists"
            payload = {"mobile": mobile}
            
            print(f"📱 ارسال درخواست OTP به شماره: {mobile}")
            
            response = self.session.post(url, json=payload, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    print(f"✅ {data.get('message')}")
                    
                    if data.get('data', {}).get('exists'):
                        expiration = data['data'].get('expiration_time', 120)
                        print(f"📧 SMS ارسال شد! (اعتبار: {expiration} ثانیه)")
                        return {
                            'success': True,
                            'message': f'کد تایید به شماره {mobile} ارسال شد',
                            'expiration_time': expiration
                        }
                    else:
                        return {
                            'success': False,
                            'message': 'شماره موبایل موجود نیست'
                        }
                else:
                    return {
                        'success': False,
                        'message': data.get('message', 'خطای نامشخص')
                    }
            else:
                return {
                    'success': False,
                    'message': f'خطای HTTP {response.status_code}'
                }
                
        except Exception as e:
            print(f"❌ خطا در ارسال OTP: {e}")
            return {
                'success': False,
                'message': f'خطا: {str(e)}'
            }
    
    def verify_otp(self, mobile, code):
        """تایید کد OTP و ورود"""
        try:
            url = f"{self.base_url}/auth/login"
            
            payload = {
                "mobile": mobile,
                "otp": code,
                "password": None,
                "type": "otp"
            }
            
            print(f"🔐 ارسال درخواست verify به: {url}")
            
            response = self.session.post(url, json=payload, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    print(f"✅ ورود موفق!")
                    
                    # ذخیره token
                    self.token = data.get('data', {}).get('token')
                    if self.token:
                        self.session.headers['Authorization'] = f"Bearer {self.token}"
                        print(f"🔑 Token ذخیره شد")
                    
                    self.is_logged_in = True
                    
                    return {
                        'success': True,
                        'message': 'ورود موفقیت‌آمیز',
                        'data': data
                    }
                else:
                    return {
                        'success': False,
                        'message': data.get('message', 'کد نادرست یا منقضی شده')
                    }
            else:
                return {
                    'success': False,
                    'message': f'خطای HTTP {response.status_code}'
                }
                
        except Exception as e:
            print(f"❌ خطا در verify: {e}")
            return {
                'success': False,
                'message': f'خطا: {str(e)}'
            }
    
    def get_silver_prices(self):
        """دریافت قیمت‌های نقره"""
        try:
            url = f"{self.base_url}/profile/homepage"
            
            print(f"🔄 دریافت قیمت‌ها از: {url}")
            
            response = self.session.get(url, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    main_data = data.get('data', {})
                    
                    # دریافت user_category_id
                    user_category_id = main_data.get('user_category_id')
                    user_categories = main_data.get('user_categories', [])
                    
                    # پیدا کردن دسته کاربر
                    user_category = None
                    for cat in user_categories:
                        if cat.get('id') == user_category_id:
                            user_category = cat
                            break
                    
                    if not user_category:
                        print(f"⚠️ دسته کاربر پیدا نشد")
                        return {'success': False, 'prices': [], 'message': 'دسته کاربر پیدا نشد'}
                    
                    # قیمت‌های نقره از دسته کاربر
                    user_silver_prices = user_category.get('silvers', [])
                    
                    # اطلاعات تکمیلی
                    silver_info = {}
                    for item in main_data.get('features_data', {}).get('silver', []):
                        silver_info[item.get('id')] = item
                    
                    # وضعیت معاملات
                    silver_trade_status = main_data.get('silver_trade_status', 0)
                    buy_status = main_data.get('buy_status', 1)
                    sell_status = main_data.get('sell_status', 1)
                    
                    if user_silver_prices:
                        print(f"✅ قیمت‌ها دریافت شد: {len(user_silver_prices)} محصول")
                        
                        formatted_prices = []
                        for item in user_silver_prices:
                            silver_id = item.get('id')
                            info = silver_info.get(silver_id, {})
                            
                            # قیمت‌ها به ریال (از user_category)
                            buy_price_rial = int(item.get('buy_price', 0))
                            sell_price_rial = int(item.get('sell_price', 0))
                            
                            # تبدیل به تومان (بدون درصد افزایش)
                            buy_price_toman = buy_price_rial // 10
                            sell_price_toman = sell_price_rial // 10
                            
                            # وضعیت
                            item_buy_status = info.get('buy_status', 1) and buy_status
                            item_sell_status = info.get('sell_status', 1) and sell_status
                            is_active = (item_buy_status == 1 or item_sell_status == 1)
                            
                            print(f"💰 {info.get('title', 'نامشخص')}: خرید={buy_price_toman:,} تومان، فروش={sell_price_toman:,} تومان")
                            
                            formatted_item = {
                                'id': silver_id,
                                'title': info.get('title', 'محصول نقره'),
                                'name': info.get('title', 'محصول نقره'),
                                'buy_price': buy_price_toman,
                                'sell_price': sell_price_toman,
                                'buy_status': item_buy_status,
                                'sell_status': item_sell_status,
                                'is_active': is_active,
                                'status_text': 'فعال' if is_active else 'غیرفعال'
                            }
                            
                            if not is_active:
                                print(f"⚠️ محصول غیرفعال: {info.get('title')}")
                            
                            formatted_prices.append(formatted_item)
                        
                        return {
                            'success': True,
                            'prices': formatted_prices,
                            'silver_trade_status': silver_trade_status,
                            'message': 'قیمت‌ها با موفقیت دریافت شد'
                        }
                    else:
                        return {'success': False, 'prices': [], 'message': 'قیمت‌ها یافت نشد'}
                else:
                    return {'success': False, 'prices': [], 'message': data.get('message', 'خطا')}
            else:
                return {'success': False, 'prices': [], 'message': f'خطای HTTP {response.status_code}'}
                
        except Exception as e:
            print(f"❌ خطا در دریافت قیمت‌ها: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'prices': [], 'message': f'خطا: {str(e)}'}
