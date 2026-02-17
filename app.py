from flask import Flask, render_template, request, jsonify, redirect, url_for
from api_scraper import ShirazSilverAPI
from apscheduler.schedulers.background import BackgroundScheduler
import jdatetime
from datetime import datetime
import os
import threading
import logging
import sys
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production-12345")

# مسیر فایل برای ذخیره داده‌ها
DATA_FILE = "data_store.json"

data_store = {
    "prices": [],
    "last_update": None,
    "increase_percentage": 0.0,
    "mobile_number": None,
    "is_configured": False,
    "is_updating": False,
    "sms_requested": False,
    "token": None,
}

api_scraper = ShirazSilverAPI()
update_lock = threading.Lock()


def get_persian_datetime():
    """تبدیل تاریخ و ساعت به شمسی"""
    now = jdatetime.datetime.now()
    return now.strftime("%Y/%m/%d - %H:%M:%S")


def save_data_store():
    """ذخیره data_store در فایل"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "prices": data_store["prices"],
                "last_update": data_store["last_update"],
                "increase_percentage": data_store["increase_percentage"],
                "mobile_number": data_store["mobile_number"],
                "is_configured": data_store["is_configured"],
                "token": data_store["token"],
            }, f, ensure_ascii=False, indent=2)
        logger.info("Data saved to file")
    except Exception as e:
        logger.error(f"Error saving data: {e}")


def load_data_store():
    """بارگذاری data_store از فایل"""
    global data_store
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                data_store.update(loaded)
                
                # بازیابی token در api_scraper
                if data_store.get("token"):
                    api_scraper.token = data_store["token"]
                    api_scraper.session.headers["Authorization"] = f"Bearer {data_store['token']}"
                    api_scraper.is_logged_in = True
                    logger.info("Token restored from file")
    except Exception as e:
        logger.error(f"Error loading data: {e}")


def apply_increase(base, percent):
    try:
        return int(base * (1 + float(percent) / 100))
    except Exception:
        return base


def update_prices_job():
    """دریافت قیمت‌ها و اعمال درصد افزایش"""
    global data_store
    with update_lock:
        if data_store["is_updating"]:
            logger.info("update already running")
            return
        data_store["is_updating"] = True

    try:
        logger.info("start update_prices_job")
        res = api_scraper.get_silver_prices()
        
        # چک کردن خطای 401
        if not res["success"] and "401" in res.get("message", ""):
            logger.warning("Token expired (401), need re-login")
            data_store["is_configured"] = False
            data_store["token"] = None
            save_data_store()
            return

        if not res["success"]:
            logger.warning("update error: %s", res["message"])
            return

        inc = float(data_store.get("increase_percentage", 0) or 0)
        new_list = []
        for p in res["prices"]:
            bp_base = p["buy_price_base"]
            sp_base = p["sell_price_base"]
            p["buy_price"] = apply_increase(bp_base, inc)
            p["sell_price"] = apply_increase(sp_base, inc)
            p["increase_percentage"] = inc
            new_list.append(p)

        data_store["prices"] = new_list
        data_store["last_update"] = get_persian_datetime()
        save_data_store()
        logger.info("prices updated: %d items at %s", len(new_list), data_store["last_update"])
    except Exception as e:
        logger.error(f"Error in update: {e}", exc_info=True)
    finally:
        data_store["is_updating"] = False


# بارگذاری داده‌ها در شروع
load_data_store()

# Scheduler با interval 10 دقیقه
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_prices_job, "interval", minutes=10, id="update_prices")
scheduler.start()

# اولین بروزرسانی در شروع (اگر لاگین است)
if data_store.get("is_configured") and data_store.get("token"):
    update_prices_job()


@app.route("/")
def index():
    # چک کردن اگر token منقضی شده باشد
    if data_store.get("is_configured") and not data_store.get("token"):
        return redirect(url_for("setup"))
    
    return render_template(
        "index.html",
        prices=data_store["prices"],
        last_update=data_store["last_update"],
        is_configured=data_store["is_configured"],
    )


@app.route("/setup", methods=["GET", "POST"])
def setup():
    if request.method == "POST":
        mobile = request.form.get("mobile")
        inc_str = (request.form.get("increase_percentage") or "0").replace(",", "")
        try:
            inc = float(inc_str)
        except Exception:
            inc = 0.0

        data_store["mobile_number"] = mobile
        data_store["increase_percentage"] = inc

        logger.info("send_otp to %s with increase %s%%", mobile, inc)

        res = api_scraper.send_otp(mobile)
        if res["success"]:
            data_store["sms_requested"] = True
            return redirect(url_for("verify"))
        return render_template(
            "setup.html", error=res["message"], increase_percentage=inc
        )

    return render_template(
        "setup.html", error=None, increase_percentage=data_store["increase_percentage"]
    )


@app.route("/verify", methods=["GET", "POST"])
def verify():
    if request.method == "POST":
        code = request.form.get("code")
        mobile = data_store.get("mobile_number")
        if not mobile:
            return redirect(url_for("setup"))

        logger.info("verify code %s for %s", code, mobile)
        res = api_scraper.verify_otp(mobile, code)
        
        if res["success"]:
            data_store["is_configured"] = True
            data_store["token"] = api_scraper.token
            save_data_store()
            update_prices_job()
            return redirect(url_for("index"))
        
        return render_template(
            "verify.html",
            mobile=mobile,
            error=res["message"],
            sms_sent=data_store.get("sms_requested", False),
        )

    return render_template(
        "verify.html",
        mobile=data_store.get("mobile_number"),
        error=None,
        sms_sent=data_store.get("sms_requested", False),
    )


@app.route("/api/prices")
def api_prices():
    """API برای دریافت قیمت‌ها (برای AJAX polling)"""
    return jsonify({
        "success": True,
        "prices": data_store["prices"],
        "last_update": data_store["last_update"],
        "increase_percentage": data_store["increase_percentage"],
        "is_configured": data_store["is_configured"],
    })


@app.route("/api/refresh")
def api_refresh():
    """بروزرسانی دستی"""
    try:
        update_prices_job()
        
        # چک کردن اگر token منقضی شده
        if not data_store.get("is_configured"):
            return jsonify({"success": False, "message": "need_login", "redirect": "/setup"}), 401
        
        return jsonify({"success": True, "message": "started"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "is_configured": data_store["is_configured"],
        "last_update": data_store["last_update"],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting server on %s", port)
    app.run(host="0.0.0.0", port=port, debug=False)
