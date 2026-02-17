from flask import Flask, render_template, request, jsonify, redirect, url_for
from api_scraper import ShirazSilverAPI
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os
import threading
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production-12345")

data_store = {
    "prices": [],
    "last_update": None,
    "increase_percentage": 0.0,
    "mobile_number": None,
    "is_configured": False,
    "is_updating": False,
    "sms_requested": False,
}

api_scraper = ShirazSilverAPI()
update_lock = threading.Lock()


def apply_increase(base, percent):
    try:
        return int(base * (1 + float(percent) / 100))
    except Exception:
        return base


def update_prices_job():
    """دریافت قیمت‌ها و اعمال درصد افزایش روی gheram (تومان)"""
    global data_store
    with update_lock:
        if data_store["is_updating"]:
            logger.info("update already running")
            return
        data_store["is_updating"] = True

    try:
        logger.info("start update_prices_job")
        res = api_scraper.get_silver_prices()
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
        data_store["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logger.info("prices updated: %d items", len(new_list))
    finally:
        data_store["is_updating"] = False


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_prices_job, "interval", minutes=30, id="update_prices")
scheduler.start()


@app.route("/")
def index():
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
    return jsonify(
        {
            "success": True,
            "prices": data_store["prices"],
            "last_update": data_store["last_update"],
            "increase_percentage": data_store["increase_percentage"],
            "is_configured": data_store["is_configured"],
        }
    )


@app.route("/api/refresh")
def api_refresh():
    try:
        update_prices_job()
        return jsonify({"success": True, "message": "started"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "is_configured": data_store["is_configured"],
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("Starting server on %s", port)
    app.run(host="0.0.0.0", port=port, debug=False)
