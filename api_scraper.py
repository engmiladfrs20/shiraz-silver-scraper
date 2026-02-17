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
            print(f"📦 Payload: {payload}")
            
            response = self.session.post(url, json=payload, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            print(f"📄 Response: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    print(f"✅ ورود موفق!")
                    
                    # ذخیره token
                    self.token = data.get('data', {}).get('token')
                    if self.token:
                        self.session.headers['Authorization'] = f"Bearer {self.token}"
                        print(f"🔑 Token ذخیره شد: {self.token[:50]}...")
                    
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
            # endpoint های احتمالی
            endpoints = [
                "/products",
                "/products/list",
                "/items",
                "/gold-silver/prices",
                "/price/list"
            ]
            
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"
                    print(f"🔄 تلاش دریافت قیمت‌ها از: {endpoint}")
                    
                    response = self.session.get(url, timeout=30)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # بررسی ساختار response
                        prices_data = None
                        if isinstance(data, dict):
                            if data.get('success') and data.get('data'):
                                prices_data = data['data']
                            elif 'products' in data:
                                prices_data = data['products']
                            elif 'items' in data:
                                prices_data = data['items']
                        elif isinstance(data, list):
                            prices_data = data
                        
                        if prices_data:
                            print(f"✅ قیمت‌ها دریافت شد: {len(prices_data)} محصول")
                            return {
                                'success': True,
                                'prices': prices_data,
                                'message': 'قیمت‌ها با موفقیت دریافت شد'
                            }
                except Exception as e:
                    print(f"⚠️ خطا در endpoint {endpoint}: {str(e)[:50]}")
                    continue
            
            print("❌ هیچ endpoint برای قیمت‌ها کار نکرد")
            return {
                'success': False,
                'prices': [],
                'message': 'خطا در دریافت قیمت‌ها - endpoint پیدا نشد'
            }
                
        except Exception as e:
            print(f"❌ خطا در دریافت قیمت‌ها: {e}")
            return {
                'success': False,
                'prices': [],
                'message': f'خطا: {str(e)}'
            }


# تست
if __name__ == "__main__":
    api = ShirazSilverAPI()
    
    # تست ارسال OTP
    mobile = "09017812729"
    result = api.send_otp(mobile)
    print(f"\n📋 نتیجه send_otp: {result}")
    
    if result['success']:
        code = input("\n🔢 کد دریافتی را وارد کنید: ")
        
        verify_result = api.verify_otp(mobile, code)
        print(f"\n📋 نتیجه verify: {verify_result}")
        
        if verify_result['success']:
            print("\n🎉 ورود موفق! حال دریافت قیمت‌ها...")
            prices = api.get_silver_prices()
            print(f"\n📊 قیمت‌ها: {prices}")
