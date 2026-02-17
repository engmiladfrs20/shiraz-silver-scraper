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
                
                logger.info(f"📸 Title صفحه: {scraper.driver.title}")
                
                # ========== اضافه شده: بستن popup نصب اپلیکیشن ==========
                try:
                    logger.info("🚫 تلاش برای بستن popup نصب اپلیکیشن...")
                    
                    # روش 1: کلیک روی دکمه بستن (X)
                    close_selectors = [
                        "//button[contains(@class, 'close')]",
                        "//button[@aria-label='Close']",
                        "//button[contains(@class, 'modal-close')]",
                        "//div[contains(@class, 'modal')]//button",
                        "//button[contains(@onclick, 'close')]"
                    ]
                    
                    popup_closed = False
                    for selector in close_selectors:
                        try:
                            close_btn = WebDriverWait(scraper.driver, 2).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            close_btn.click()
                            logger.info(f"✅ Popup بسته شد با selector: {selector}")
                            popup_closed = True
                            time.sleep(1)
                            break
                        except:
                            continue
                    
                    # روش 2: کلیک بیرون از modal
                    if not popup_closed:
                        logger.info("🔄 تلاش روش دیگر: کلیک بیرون از modal")
                        try:
                            backdrop = scraper.driver.find_element(By.XPATH, "//div[contains(@class, 'modal-backdrop') or contains(@class, 'overlay')]")
                            backdrop.click()
                            logger.info("✅ کلیک روی backdrop انجام شد")
                            popup_closed = True
                            time.sleep(1)
                        except:
                            pass
                    
                    # روش 3: فشردن ESC
                    if not popup_closed:
                        logger.info("🔄 فشردن کلید ESC")
                        from selenium.webdriver.common.keys import Keys
                        scraper.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        time.sleep(1)
                        logger.info("✅ ESC فشرده شد")
                        popup_closed = True
                    
                    if popup_closed:
                        logger.info("✅ Popup بسته شد")
                    
                except Exception as e:
                    logger.warning(f"⚠️ خطا در بستن popup (ممکن است وجود نداشته باشد): {e}")
                # ========== پایان بخش جدید ==========
                
                time.sleep(2)
                
                # پیدا کردن input موبایل
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
                        logger.warning(f"❌ Selector {idx+1} کار نکرد")
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
                    
                    # روش 1: کلیک عادی
                    for idx, selector in enumerate(submit_selectors):
                        try:
                            logger.info(f"🔍 تلاش کلیک دکمه {idx+1}: {selector}")
                            submit_btn = WebDriverWait(scraper.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                            submit_btn.click()
                            logger.info(f"✅ دکمه ارسال کلیک شد")
                            submitted = True
                            break
                        except Exception as e:
                            logger.warning(f"❌ دکمه {idx+1} کار نکرد: {str(e)[:100]}")
                            continue
                    
                    # روش 2: اگر کلیک عادی کار نکرد، از JavaScript استفاده کن
                    if not submitted:
                        logger.info("🔄 تلاش با JavaScript click...")
                        try:
                            submit_btn = scraper.driver.find_element(By.XPATH, "//button[@type='submit']")
                            scraper.driver.execute_script("arguments[0].click();", submit_btn)
                            logger.info("✅ دکمه با JavaScript کلیک شد")
                            submitted = True
                        except Exception as e:
                            logger.error(f"❌ JavaScript click هم کار نکرد: {e}")
                    
                    # روش 3: فشردن Enter
                    if not submitted:
                        logger.info("🔄 فشردن Enter...")
                        try:
                            from selenium.webdriver.common.keys import Keys
                            mobile_input.send_keys(Keys.RETURN)
                            logger.info("✅ Enter فشرده شد")
                            submitted = True
                        except Exception as e:
                            logger.error(f"❌ Enter هم کار نکرد: {e}")
                    
                    if submitted:
                        logger.info(f"📧 درخواست کد SMS به شماره {mobile} ارسال شد!")
                        data_store['sms_requested'] = True
                        time.sleep(3)
                    else:
                        logger.error("❌ هیچ روشی برای submit کار نکرد")
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
