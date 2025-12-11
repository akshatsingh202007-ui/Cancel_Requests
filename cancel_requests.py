import json
import time
import random
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USERNAME = "aaakksshhaattt"
PASSWORD = "*****"

CANCEL_LIMIT = 50
BATCH_SIZE = 25
BATCH_PAUSE_MIN = 20
BATCH_PAUSE_MAX = 45
DELAY_MIN = 2.0
DELAY_MAX = 4.0
LOGIN_WAIT = 30


def human_sleep(min_s=DELAY_MIN, max_s=DELAY_MAX):
    time.sleep(random.uniform(min_s, max_s))


def cancel_request_on_profile(driver, log_widget):
    try:
        requested = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((
                By.XPATH,
                "//div[contains(@aria-label,'Following') or contains(text(),'Requested')]"
            ))
        )
        driver.execute_script("arguments[0].click();", requested)
        human_sleep(1, 2)

        try:
            confirm_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//button[contains(text(),'Cancel') or contains(text(),'Unfollow')]"
                ))
            )
            driver.execute_script("arguments[0].click();", confirm_btn)
            log_widget.insert(tk.END, "  ✅ Request cancelled\n")
        except:
            log_widget.insert(tk.END, "  ✅ Auto-cancelled (no popup)\n")

        log_widget.see(tk.END)
        return True

    except:
        log_widget.insert(tk.END, "  ⚠️ No 'Requested' button found\n")
        log_widget.see(tk.END)
        return False


def start_cancelling(username, password, json_file, log_widget):
    """Main logic for cancelling follow requests"""

    try:
        options = Options()
        options.add_argument("--start-maximized")
        driver = webdriver.Chrome(options=options)

    except Exception as e:
        log_widget.insert(tk.END, f"❌ ChromeDriver error: {e}\n")
        log_widget.see(tk.END)
        return

    cancelled_count = 0
    cancelled_requests = []

    try:
        driver.get("https://www.instagram.com/accounts/login/")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "username")))
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        driver.find_element(By.NAME, "password").send_keys(Keys.RETURN)

        log_widget.insert(tk.END, "Logging in...\n")
        log_widget.see(tk.END)
        time.sleep(LOGIN_WAIT)

        for _ in range(2):
            try:
                not_now = WebDriverWait(driver, 6).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//button[contains(., 'Not Now') or contains(., 'Not now')]"
                    ))
                )
                not_now.click()
                human_sleep(1, 2)
            except:
                break

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        requests = data.get("relationships_follow_requests_sent", [])
        if not requests:
            log_widget.insert(tk.END, "⚠️ No follow requests found in file.\n")
            return

        user_links_with_obj = []
        for req in requests:
            try:
                if req.get("string_list_data"):
                    entry = req["string_list_data"][0]
                    href = entry.get("href")
                    if href:
                        user_links_with_obj.append((href, req))
                    else:
                        uname = entry.get("value")
                        if uname:
                            user_links_with_obj.append((f"https://www.instagram.com/{uname}/", req))
            except Exception:
                continue

        total = len(user_links_with_obj)
        log_widget.insert(tk.END, f"Found {total} pending requests.\n")
        log_widget.see(tk.END)

        for idx, (link, req_obj) in enumerate(reversed(user_links_with_obj), start=1):

            if cancelled_count >= CANCEL_LIMIT:
                log_widget.insert(tk.END, f"\n✅ Reached {CANCEL_LIMIT} cancellations. Stopping...\n")
                break

            try:
                driver.get(link)
                log_widget.insert(tk.END, f"[{idx}] Visiting {link}\n")
                log_widget.see(tk.END)

                success = cancel_request_on_profile(driver, log_widget)
                if success:
                    cancelled_count += 1
                    cancelled_requests.append(req_obj)

                human_sleep()

                if cancelled_count > 0 and cancelled_count % BATCH_SIZE == 0:
                    pause_time = random.randint(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
                    log_widget.insert(tk.END, f"--- Batch pause {pause_time}s ---\n")
                    log_widget.see(tk.END)
                    time.sleep(pause_time)

            except Exception as e:
                log_widget.insert(tk.END, f"❌ Error: {e}\n")
                log_widget.see(tk.END)
                time.sleep(2)

        if cancelled_requests:
            remaining = [r for r in requests if r not in cancelled_requests]
            data["relationships_follow_requests_sent"] = remaining

            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            log_widget.insert(tk.END, f"✅ Removed {len(cancelled_requests)} entries from JSON file.\n")

        log_widget.insert(tk.END, f"\n🎉 Finished. Cancelled {cancelled_count} requests.\n")
        log_widget.see(tk.END)

    finally:
        driver.quit()


def browse_json(entry_widget):
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, file_path)


def start_thread(username_entry, password_entry, json_entry, log_widget):
    username = username_entry.get()
    password = password_entry.get()
    json_file = json_entry.get()

    if not json_file:
        messagebox.showwarning("Missing File", "Please select a JSON file first!")
        return

    threading.Thread(
        target=start_cancelling,
        args=(username, password, json_file, log_widget),
        daemon=True
    ).start()


root = tk.Tk()
root.title("🚀 Instagram Auto Cancel (Bottom 50) 🚀")
root.geometry("820x600")
root.configure(bg="#0f0f1a")

tk.Label(root, text="Username:", fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12)).place(x=20, y=20)
username_entry = tk.Entry(root, fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12), insertbackground="#39ff14")
username_entry.insert(0, USERNAME)
username_entry.place(x=120, y=20, width=250)

tk.Label(root, text="Password:", fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12)).place(x=20, y=60)
password_entry = tk.Entry(root, fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12), insertbackground="#39ff14", show="*")
password_entry.insert(0, PASSWORD)
password_entry.place(x=120, y=60, width=250)

tk.Label(root, text="JSON File:", fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12)).place(x=20, y=100)
json_entry = tk.Entry(root, fg="#39ff14", bg="#0f0f1a", font=("Consolas", 12), insertbackground="#39ff14")
json_entry.place(x=120, y=100, width=500)

tk.Button(root, text="Browse", command=lambda: browse_json(json_entry),
          fg="#0f0f1a", bg="#39ff14", font=("Consolas", 10, "bold")).place(x=640, y=97)

tk.Button(root, text="Start Canceling 🚀",
          command=lambda: start_thread(username_entry, password_entry, json_entry, log_widget),
          fg="#0f0f1a", bg="#39ff14", font=("Consolas", 14, "bold")).place(x=300, y=150)

log_widget = scrolledtext.ScrolledText(root, width=95, height=25, bg="#1a1a2e", fg="#39ff14", font=("Consolas", 10))
log_widget.place(x=20, y=200)

root.mainloop()
