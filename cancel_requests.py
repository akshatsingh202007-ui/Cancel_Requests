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
PROFILE_WAIT = 5
CANCEL_LIMIT = 50
BATCH_SIZE = 25
BATCH_PAUSE_MIN = 20
BATCH_PAUSE_MAX = 45
DELAY_MIN = 2
DELAY_MAX = 4
PROFILE_PATH = r"C:\insta_selenium_profile"
# ==========================================

skip_flag = False


# -------- THREAD SAFE LOGGER --------
def log(msg):
    log_widget.after(0, lambda: (
        log_widget.insert(tk.END, msg),
        log_widget.see(tk.END)
    ))


# -------- SAFE SINGLE-LINE COUNTDOWN --------
def countdown(seconds, label, allow_skip=False):
    global skip_flag
    skip_flag = False
    timer_index = None

    def start_timer():
        nonlocal timer_index
        log_widget.insert(tk.END, "\n")
        timer_index = log_widget.index("end-1c linestart")
        log_widget.insert(tk.END, f"⏳ {label}: {seconds}s remaining")
        log_widget.see(tk.END)

    log_widget.after(0, start_timer)

    for remaining in range(seconds - 1, -1, -1):
        if allow_skip and skip_flag:
            def skip_line():
                log_widget.delete(timer_index, f"{timer_index} lineend")
                log_widget.insert(timer_index, f"⏭ Skipped during {label}")
                log_widget.insert(tk.END, "\n")
            log_widget.after(0, skip_line)
            return False

        time.sleep(1)

        def update(r=remaining):
            log_widget.delete(timer_index, f"{timer_index} lineend")
            log_widget.insert(timer_index, f"⏳ {label}: {r}s remaining")
        log_widget.after(0, update)

    log_widget.after(0, lambda: log_widget.insert(tk.END, "\n"))
    return True


def human_sleep():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


# -------- CANCEL REQUEST --------
def cancel_request_on_profile(driver):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "button"))
        )

        driver.execute_script("window.scrollTo(0, 300)")
        time.sleep(1)

        requested_btn = None
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            text = (btn.text or "").lower()
            aria = (btn.get_attribute("aria-label") or "").lower()
            if "requested" in text or "requested" in aria:
                requested_btn = btn
                break

        if not requested_btn:
            log("  ⚠️ Requested button not found\n")
            return False

        driver.execute_script("arguments[0].click();", requested_btn)
        time.sleep(2)

        dialog = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
        )

        actions = dialog.find_elements(
            By.XPATH, ".//button | .//div[@role='button']"
        )

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

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )

        driver.get("https://www.instagram.com/")

        log("🌐 Instagram opened\n")
        log("👉 Login manually if required\n")
        log("⏱ Waiting for login...\n")

        if not countdown(LOGIN_WAIT, "Login wait"):
            return

        if "login" in driver.current_url:
            log("❌ Login not detected. Aborting.\n")
            return

        log("✅ Login detected\n")

        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        if "relationships_follow_requests_sent" in data:
            requests = data["relationships_follow_requests_sent"]
            root_key = "relationships_follow_requests_sent"
        else:
            requests = data["relationships"]["relationships_follow_requests_sent"]
            root_key = "relationships"

        remaining_requests = requests.copy()

        profiles = []
        for r in remaining_requests:
            try:
                s = r["string_list_data"][0]
                if s.get("href"):
                    profiles.append((s["href"], r))
                elif s.get("value"):
                    profiles.append((f"https://www.instagram.com/{s['value']}/", r))
            except:
                pass

        log(f"📄 Total pending requests: {len(profiles)}\n")

        cancelled = 0

        for i, (link, req_obj) in enumerate(reversed(profiles), 1):
            if cancelled >= CANCEL_LIMIT:
                log("\n🛑 Cancel limit reached\n")
                break

            driver.get(link)
            log(f"[{i}] Visiting {link}\n")

            if not countdown(PROFILE_WAIT, "Profile wait", allow_skip=True):
                continue

            if cancel_request_on_profile(driver):
                cancelled += 1
                remaining_requests.remove(req_obj)

                if root_key == "relationships_follow_requests_sent":
                    data[root_key] = remaining_requests
                else:
                    data[root_key]["relationships_follow_requests_sent"] = remaining_requests

                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                log(f"📊 Cancelled: {cancelled} | Remaining: {len(remaining_requests)}\n")

            human_sleep()

            if cancelled and cancelled % BATCH_SIZE == 0:
                pause = random.randint(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                countdown(pause, "Batch pause")

        log(f"\n🎉 Done! Cancelled {cancelled} requests\n")
        countdown(3, "Closing Chrome")

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


def skip_current():
    global skip_flag
    skip_flag = True


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
root.title("🚀 Instagram Request Manager")
root.geometry("900x650")
root.configure(bg="#0b0f1a")

tk.Label(
    root,
    text="🚀 Instagram Request Manager",
    font=("Segoe UI", 20, "bold"),
    fg="#6aff9d",
    bg="#0b0f1a"
).pack(pady=15)

card = tk.Frame(root, bg="#12172a")
card.pack(padx=20, pady=10, fill="x")

tk.Label(card, text="JSON File", fg="#9aa4ff", bg="#12172a").grid(row=0, column=0, padx=10, pady=10)
json_entry = tk.Entry(card, bg="#0b0f1a", fg="#6aff9d", insertbackground="#6aff9d")
json_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

tk.Button(card, text="Browse", command=lambda: browse_json(json_entry),
          bg="#6aff9d", fg="#000", relief="flat").grid(row=0, column=2, padx=10)

tk.Button(card, text="▶ Start", command=start_thread,
          bg="#4da3ff", fg="white", relief="flat", width=12).grid(row=1, column=1, pady=10)

tk.Button(card, text="⏭ Skip", command=skip_current,
          bg="#ff5c5c", fg="white", relief="flat", width=12).grid(row=1, column=2)

card.columnconfigure(1, weight=1)

log_widget = scrolledtext.ScrolledText(
    root,
    bg="#050812",
    fg="#6aff9d",
    insertbackground="#6aff9d",
    font=("Consolas", 10),
    relief="flat"
)
log_widget.pack(padx=20, pady=15, fill="both", expand=True)

root.mainloop()
