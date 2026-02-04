#!/usr/bin/env python3
"""
Leaflow 多账号自动签到脚本 (增强重试版)
变量名：LEAFLOW_ACCOUNTS
变量值：邮箱1:密码1,邮箱2:密码2
"""

import os
import time
import logging
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LeaflowAutoCheckin:
    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.driver = None
        self.setup_driver()

    def setup_driver(self):
        """深度优化版的驱动配置，专门解决渲染器超时问题"""
        chrome_options = Options()
        
        # 1. 基础无头模式配置
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless=new') # 使用较新的无头模式
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

        # 2. 针对 "Timed out receiving message from renderer" 的专项优化
        # 屏蔽一些可能导致渲染卡顿的特性
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        # 3. 策略调整：将 eager 改回 normal，有时候 eager 会导致渲染器通讯步调不一致
        chrome_options.page_load_strategy = 'normal' 

        # 4. 伪装升级
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # 5. 设置脚本超时，防止死等
        self.driver.set_script_timeout(20)

    def checkin(self):
        """执行签到流程 (带自动刷新重试)"""
        max_page_retries = 3  # 如果页面加载失败，最多尝试3次
        
        for attempt in range(max_page_retries):
            try:
                logger.info(f"[{self.email}] 正在尝试打开签到页 (第 {attempt + 1} 次)...")
                # 设置超时限制，30秒不响应就强制停止并重试
                self.driver.set_page_load_timeout(35)
                self.driver.get("https://checkin.leaflow.net")
                
                # 检查页面是否加载出签到相关元素
                if self.wait_for_checkin_ready():
                    result = self.do_click_checkin()
                    if result:
                        return result
                
                logger.warning(f"[{self.email}] 页面未加载出签到按钮，准备刷新重试...")
            except Exception as e:
                logger.error(f"[{self.email}] 访问出错: {str(e)}")
            
            time.sleep(5) # 刷新前缓冲
            
        return "页面加载多次超时失败"

    def wait_for_checkin_ready(self):
        """等待签到按钮出现"""
        indicators = ["button.checkin-btn", "//button[contains(text(), '签到')]", "//*[contains(text(), '已签到')]"]
        for ind in indicators:
            try:
                by = By.XPATH if ind.startswith("//") or ind.startswith("//*") else By.CSS_SELECTOR
                WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((by, ind)))
                return True
            except:
                continue
        return False

    def do_click_checkin(self):
        """核心点击逻辑"""
        try:
            # 尝试定位按钮
            btn = self.driver.find_element(By.CSS_SELECTOR, "button.checkin-btn")
            text = btn.text
            
            if "已签到" in text or btn.get_attribute("disabled"):
                return "今日已签到"
            
            btn.click()
            logger.info("已点击签到按钮")
            time.sleep(5)
            return "签到成功"
        except:
            return None

    def login(self):
        """登录流程 (简化版)"""
        try:
            self.driver.get("https://leaflow.net/login")
            time.sleep(3)
            # 简单的登录表单填写
            email_input = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='email']")))
            email_input.clear()
            email_input.send_keys(self.email)
            
            pass_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            pass_input.clear()
            pass_input.send_keys(self.password)
            
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            # 等待跳转
            WebDriverWait(self.driver, 20).until(lambda d: "login" not in d.current_url)
            return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False

    def run(self):
        """账号执行入口"""
        try:
            if self.login():
                res = self.checkin()
                # 顺便获取下余额 (可选)
                return True, res, "已完成"
            return False, "登录失败", "N/A"
        finally:
            if self.driver:
                self.driver.quit()

# --- 多账号管理部分 ---
class MultiAccountManager:
    def __init__(self):
        self.accounts = self.load_accounts()

    def load_accounts(self):
        accounts_str = os.getenv('LEAFLOW_ACCOUNTS', '').strip()
        if not accounts_str:
            raise ValueError("未配置 LEAFLOW_ACCOUNTS 变量")
        
        pairs = [p.strip() for p in accounts_str.split(',')]
        return [p.split(':', 1) for p in pairs if ':' in p]

    def run_all(self):
        results = []
        for email, pwd in self.accounts:
            bot = LeaflowAutoCheckin(email, pwd)
            success, msg, bal = bot.run()
            results.append((email, success, msg))
            time.sleep(5) # 账号间间隔
        return results

if __name__ == "__main__":
    manager = MultiAccountManager()
    manager.run_all()
    print("任务执行完毕")

