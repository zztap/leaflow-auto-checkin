import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

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
        """深度优化版驱动，专门对付渲染器超时"""
        chrome_options = Options()
        if os.getenv('GITHUB_ACTIONS'):
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

        # 针对 renderer timeout 的专项优化
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-site-isolation-trials')
        
        # 策略改为 none，防止 Selenium 死等不响应的渲染器
        chrome_options.page_load_strategy = 'none' 
        
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)

    def checkin(self):
        """执行签到 (带强制刷新和截图调试)"""
        max_page_retries = 3
        for attempt in range(max_page_retries):
            try:
                logger.info(f"[{self.email}] 尝试访问签到页 (第 {attempt + 1} 次)...")
                self.driver.set_page_load_timeout(45)
                self.driver.get("https://checkin.leaflow.net")
                
                # 因为用了 strategy='none'，必须手动等待
                time.sleep(15) 
                
                # 检查是否成功加载按钮
                if self.wait_for_element():
                    result = self.do_click()
                    if result: return result
                
                # 如果没找到按钮，保存截图看看到底加载了什么
                shot_name = f"debug_{self.email.split('@')[0]}_retry_{attempt+1}.png"
                self.driver.save_screenshot(shot_name)
                logger.warning(f"[{self.email}] 页面未就绪，截图已保存为 {shot_name}")
                
            except Exception as e:
                logger.error(f"[{self.email}] 访问出错: {str(e)}")
            
            time.sleep(5)
        return "多次加载失败"

    def wait_for_element(self):
        """尝试多种方式寻找签到按钮"""
        for selector in ["button.checkin-btn", "//button[contains(text(), '签到')]", "//*[contains(text(), '已签到')]"]:
            try:
                by = By.XPATH if selector.startswith("/") else By.CSS_SELECTOR
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((by, selector)))
                return True
            except: continue
        return False

    def do_click(self):
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "button.checkin-btn")
            if "已签到" in btn.text or btn.get_attribute("disabled"):
                return "今日已签到"
            btn.click()
            time.sleep(5)
            return "签到成功"
        except: return None

    def login(self):
        try:
            self.driver.get("https://leaflow.net/login")
            time.sleep(10) # 给登录页一点时间
            email_input = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[type='text']")))
            email_input.send_keys(self.email)
            self.driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(self.password)
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"登录失败: {e}")
            return False

    def run(self):
        try:
            if self.login():
                return True, self.checkin(), "N/A"
            return False, "登录失败", "N/A"
        finally:
            if self.driver: self.driver.quit()

class MultiAccountManager:
    def __init__(self):
        self.accounts = self.load_accounts()

    def load_accounts(self):
        # 兼容两种变量名
        accs = os.getenv('LEAFLOW_ACCOUNTS') or f"{os.getenv('LEAFLOW_EMAIL')}:{os.getenv('LEAFLOW_PASSWORD')}"
        if not accs or ":" not in accs: return []
        return [p.split(':', 1) for p in accs.split(',') if ':' in p]

    def run_all(self):
        print("🚀 开始执行签到任务")
        for email, pwd in self.accounts:
            success, msg, _ = LeaflowAutoCheckin(email, pwd).run()
            print(f"👤 {email[:3]}***: {'✅' if success else '❌'} {msg}")
        print("🏁 任务结束")

if __name__ == "__main__":
    MultiAccountManager().run_all()
