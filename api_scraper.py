import requests
from datetime import datetime

class ShirazSilverAPI:
    """دریافت قیمت نقره از API ساچمه‌خانه شیراز"""

    def __init__(self):
        self.base_url = "https://api.shirazgoldandsilver.ir/api/v1"
        self.website_url = "https://shirazgoldandsilver.ir"
        self.session = requests.Session()
        self.is_logged_in = False
        self.token = None

        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json",
            "Origin": self.website_url,
            "Referer": f"{self.website_url}/",
        })

    def send_otp(self, mobile):
        """ارسال کد تایید به شماره موبایل"""
        try:
            url = f"{self.base_url}/auth/check-mobile-exists"
            r = self.session.post(url, json={"mobile": mobile}, timeout=30)
            print("send_otp status:", r.status_code)
            if r.status_code != 200:
                return {"success": False, "message": f"HTTP {r.status_code}"}
            data = r.json()
            if not data.get("success"):
                return {"success": False, "message": data.get("message", "خطا")}
            if not data.get("data", {}).get("exists"):
                return {"success": False, "message": "شماره موبایل موجود نیست"}
            return {"success": True, "message": "کد ارسال شد"}
        except Exception as e:
            print("send_otp error:", e)
            return {"success": False, "message": str(e)}

    def verify_otp(self, mobile, code):
        """تایید کد تایید و ورود"""
        try:
            url = f"{self.base_url}/auth/login"
            payload = {"mobile": mobile, "otp": code, "password": None, "type": "otp"}
            print("verify_otp →", url, payload)
            r = self.session.post(url, json=payload, timeout=30)
            print("verify_otp status:", r.status_code)
            if r.status_code != 200:
                return {"success": False, "message": f"HTTP {r.status_code}"}
            data = r.json()
            if not data.get("success"):
                return {"success": False, "message": data.get("message", "کد اشتباه")}
            token = data.get("data", {}).get("token")
            if token:
                self.token = token
                self.session.headers["Authorization"] = f"Bearer {token}"
                self.is_logged_in = True
                print("Token set")
            return {"success": True, "message": "ورود موفق"}
        except Exception as e:
            print("verify_otp error:", e)
            return {"success": False, "message": str(e)}

    def get_silver_prices(self):
        """
        دریافت لیست نقره (فقط ۹ ردیف)
        
        منطق قیمت‌گذاری (همه قیمت‌ها به تومان هستند):
        - سه ردیف: ساچمه عیار 999.9، ساچمه عیار 999، ساچمه عیار 995
          buy_price_base  → از buy_price_gheram
          sell_price_base → از sell_price_gheram
        
        - بقیه ردیف‌ها:
          buy_price_base  → از buy_price
          sell_price_base → از sell_price
        """
        try:
            url = f"{self.base_url}/profile/homepage"
            print("get_silver_prices →", url)
            r = self.session.get(url, timeout=30)
            print("prices status:", r.status_code)
            if r.status_code != 200:
                return {"success": False, "prices": [], "message": f"HTTP {r.status_code}"}

            data = r.json()
            if not data.get("success"):
                return {"success": False, "prices": [], "message": data.get("message", "خطا")}

            main = data.get("data", {})

            # پیدا کردن دسته‌بندی کاربر
            user_category_id = main.get("user_category_id")
            user_category = None
            for cat in main.get("user_categories", []):
                if cat.get("id") == user_category_id:
                    user_category = cat
                    break
            if not user_category:
                print("user_category not found")
                return {"success": False, "prices": [], "message": "دسته کاربر پیدا نشد"}

            user_silvers = user_category.get("silvers", [])

            # map اطلاعات تکمیلی
            info_map = {}
            for it in main.get("features_data", {}).get("silver", []):
                info_map[it.get("id")] = it

            buy_status_global = main.get("buy_status", 1)
            sell_status_global = main.get("sell_status", 1)

            # سه ردیف خاص که باید از gheram استفاده کنند
            special_titles = {
                "ساچمه عیار 999.9",
                "ساچمه عیار 999",
                "ساچمه عیار 995",
            }

            prices = []
            for it in user_silvers:
                sid = it.get("id")
                info = info_map.get(sid, {})

                title = info.get("title", "محصول نقره")

                # تشخیص اینکه از کدام فیلد استفاده کنیم
                if title in special_titles:
                    # برای سه ردیف خاص: از gheram (تومان)
                    buy_base = int(it.get("buy_price_gheram", 0))
                    sell_base = int(it.get("sell_price_gheram", 0))
                    print(f"✅ {title} (gheram) → buy={buy_base:,}, sell={sell_base:,}")
                else:
                    # برای بقیه: از buy_price و sell_price (تومان)
                    buy_base = int(it.get("buy_price", 0))
                    sell_base = int(it.get("sell_price", 0))
                    print(f"📊 {title} (standard) → buy={buy_base:,}, sell={sell_base:,}")

                b_status = 1 if info.get("buy_status", 1) and buy_status_global else 0
                s_status = 1 if info.get("sell_status", 1) and sell_status_global else 0
                is_active = bool(b_status or s_status)

                prices.append({
                    "id": sid,
                    "name": title,
                    "buy_price_base": buy_base,   # قیمت اصلی (تومان)
                    "sell_price_base": sell_base,
                    "buy_price": buy_base,        # بعداً در app.py درصد روی این اعمال می‌شود
                    "sell_price": sell_base,
                    "buy_status": b_status,
                    "sell_status": s_status,
                    "is_active": is_active,
                    "status_text": "فعال" if is_active else "غیرفعال",
                })

            prices = prices[:9]  # فقط ۹ ردیف

            return {"success": True, "prices": prices, "message": "ok"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "prices": [], "message": str(e)}


if __name__ == "__main__":
    api = ShirazSilverAPI()
    mobile = input("Mobile: ")
    r = api.send_otp(mobile)
    print(r)
    if r["success"]:
        code = input("Code: ")
        v = api.verify_otp(mobile, code)
        print(v)
        if v["success"]:
            prices = api.get_silver_prices()
            print(prices)
