import json
import time
import random
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= CONFIG =================
LOGIN_WAIT = 60
CANCEL_LIMIT = 50
BATCH_SIZE = 25
BATCH_PAUSE_MIN = 20
BATCH_PAUSE_MAX = 45
DELAY_MIN = 2
DELAY_MAX = 4
PROFILE_PATH = r"C:\insta_selenium_profile"
# ==========================================


# -------- THREAD-SAFE LOGGER --------
def log(msg):
    log_widget.after(0, lambda: (
        log_widget.insert(tk.END, msg),
        log_widget.see(tk.END)
    ))


# -------- COUNTDOWN TIMER --------
def countdown(seconds, label):
    for remaining in range(seconds, 0, -1):
        log(f"⏳ {label}: {remaining}s remaining\n")
        time.sleep(1)


def human_sleep():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# -------- CANCEL REQUEST LOGIC --------
def cancel_request_on_profile(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "button"))
        )

        driver.execute_script("window.scrollTo(0, 300)")
        time.sleep(1)

        requested_btn = None
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            try:
                text = btn.text.lower()
                aria = (btn.get_attribute("aria-label") or "").lower()
                if "requested" in text or "requested" in aria:
                    requested_btn = btn
                    break
            except:
                continue

        if not requested_btn:
            log("  ⚠️ Requested button not found\n")
            return False

        driver.execute_script("arguments[0].click();", requested_btn)
        time.sleep(2)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
        )

        dialog = driver.find_element(By.XPATH, "//div[@role='dialog']")
        actions = dialog.find_elements(
            By.XPATH, ".//button | .//div[@role='button']"
        )

        if not actions:
            log("  ⚠️ No cancel option found\n")
            return False

        driver.execute_script("arguments[0].click();", actions[0])
        time.sleep(1)

        log("  ✅ Request cancelled\n")
        return True

    except Exception as e:
        log(f"  ❌ Cancel failed: {e}\n")
        return False


# -------- MAIN WORKER --------
def start_cancelling(json_file):
    driver = None

    try:
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument(f"--user-data-dir={PROFILE_PATH}")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        driver.get("https://www.instagram.com/")
        log("🌐 Instagram opened\n")
        log("👉 Login manually if required\n")

        countdown(LOGIN_WAIT, "Login wait")

        if "login" in driver.current_url:
            log("❌ Login not detected. Aborting.\n")
            return

        log("✅ Login detected\n")

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        requests = (
            data.get("relationships_follow_requests_sent") or
            data.get("relationships", {}).get("relationships_follow_requests_sent", [])
        )

        if not requests:
            log("⚠️ No follow requests found\n")
            return

        profiles = []
        for r in requests:
            try:
                s = r["string_list_data"][0]
                if s.get("href"):
                    profiles.append((s["href"], r))
                elif s.get("value"):
                    profiles.append((f"https://www.instagram.com/{s['value']}/", r))
            except:
                pass

        log(f"📄 Found {len(profiles)} pending requests\n")

        cancelled = []
        count = 0

        for i, (link, obj) in enumerate(reversed(profiles), 1):
            if count >= CANCEL_LIMIT:
                log("\n🛑 Cancel limit reached\n")
                break

            driver.get(link)
            log(f"[{i}] Visiting {link}\n")

            if cancel_request_on_profile(driver):
                cancelled.append(obj)
                count += 1

            human_sleep()

            if count and count % BATCH_SIZE == 0:
                pause = random.randint(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                countdown(pause, "Batch pause")

        if cancelled:
            remaining = [r for r in requests if r not in cancelled]

            if "relationships_follow_requests_sent" in data:
                data["relationships_follow_requests_sent"] = remaining
            else:
                data["relationships"]["relationships_follow_requests_sent"] = remaining

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            log(f"🧹 Removed {len(cancelled)} entries from JSON\n")

        log(f"\n🎉 Done! Cancelled {count} requests\n")
        log("🧹 Closing Chrome in 3s...\n")
        countdown(3, "Closing Chrome")

    except Exception as e:
        log(f"❌ Error: {e}\n")

    finally:
        if driver:
            driver.quit()
            log("✅ Chrome closed\n")


# -------- UI HELPERS --------
def browse_json(entry):
    path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if path:
        entry.delete(0, tk.END)
        entry.insert(0, path)


def start_thread():
    if not json_entry.get():
        messagebox.showwarning("Missing File", "Select JSON file first")
        return

    threading.Thread(
        target=start_cancelling,
        args=(json_entry.get(),),
        daemon=True
    ).start()


# -------- UI --------
root = tk.Tk()
root.title("🚀 Instagram Auto Cancel (Countdown Edition) 🚀")
root.geometry("820x600")
root.configure(bg="#0f0f1a")

tk.Label(root, text="JSON File:", fg="#39ff14", bg="#0f0f1a").place(x=20, y=20)
json_entry = tk.Entry(root, fg="#39ff14", bg="#0f0f1a", insertbackground="#39ff14")
json_entry.place(x=120, y=20, width=500)

tk.Button(root, text="Browse", command=lambda: browse_json(json_entry),
          bg="#39ff14").place(x=640, y=17)

tk.Button(root, text="Start Canceling 🚀",
          command=start_thread, bg="#39ff14").place(x=300, y=60)

log_widget = scrolledtext.ScrolledText(
    root, width=95, height=30, bg="#1a1a2e", fg="#39ff14"
)
log_widget.place(x=20, y=110)

root.mainloop()
