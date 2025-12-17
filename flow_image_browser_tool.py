import tkinter as tk
import json
import time
import os
import re
import urllib.request
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    from ttkbootstrap import Window as TtkbWindow
    _HAS_TTKBOOTSTRAP = True
except Exception:
    TtkbWindow = None
    _HAS_TTKBOOTSTRAP = False

from flow_browser_tool import FlowBrowserTool


class FlowImagesTool(FlowBrowserTool):
    """Flow Images variant with custom template defaults."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bỏ chọn mô hình từ UI: cố định Nano Banana Pro và khóa combobox
        self._force_model = "Nano Banana Pro"
        try:
            if hasattr(self, "model_choice"):
                self.model_choice.configure(values=[self._force_model], state="disabled")
                self.model_choice.set(self._force_model)
        except Exception:
            pass

    def _download_excel_template(self) -> None:
        """Download Excel template customized for Flow Images."""
        try:
            path = tk.filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel", "*.xlsx")],
                initialfile="flow_images_template.xlsx",
                title="Lưu template Excel"
            )
            if not path:
                return
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Tasks"
            # Pull options from current UI to ensure valid values
            ar_values = list(self.aspect_ratio.cget('values')) if hasattr(self, 'aspect_ratio') else ["16:9", "9:16"]
            op_values = list(self.outputs_per_prompt.cget('values')) if hasattr(self, 'outputs_per_prompt') else ["1", "2", "3", "4"]

            ws.append(["prompt", "media", "aspect_ratio", "outputs_per_prompt", "model"])  # header
            # three sample rows using Nano Banana Pro and 9:16
            default_ar = "9:16"
            default_md = "Nano Banana Pro"
            ws.append(["Running", "C:\\Users\\admin\\Downloads\\Shop-quan-ao-nu-quan-9-Fs-store.jpg", default_ar, op_values[0], default_md])
            ws.append(["A cinematic sunset over mountains", "", default_ar, op_values[-1], default_md])
            ws.append(["A neon-lit cyberpunk city at night", "", default_ar, op_values[1] if len(op_values) > 1 else op_values[0], default_md])
            wb.save(path)
            try:
                self._log_exec(f"Đã lưu template Excel: {path}")
            except Exception:
                pass
        except Exception as ex:
            tk.messagebox.showerror("Lỗi", f"Không thể tạo template: {ex}")

    def _open_settings_and_apply(self, driver, aspect: str, outputs: str, model: str) -> None:
        """Flow Images: apply aspect + outputs only, skip model selection."""
        try:
            self._log_exec("Flow Images: apply settings (aspect, outputs), skip model")
        except Exception:
            pass

        # Open settings popover
        settings_btn_xp = [
            "//button[.//i[normalize-space(text())='tune']]",
            "//button[.//span[normalize-space(text())='Cài đặt']]",
            "//button[contains(., 'Cài đặt') or contains(., 'Settings')]",
        ]
        clicked = False
        for xp in settings_btn_xp:
            try:
                el = driver.find_element(By.XPATH, xp)
                self._human_click_el(driver, el)
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            raise Exception("Settings button not found")

        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//*[@role='dialog']")))
        except Exception:
            pass

        def select_from_combobox(label_texts, option_texts):
            for label_text in label_texts:
                try:
                    combo = driver.find_element(By.XPATH, f"//button[@role='combobox'][.//span[normalize-space(text())='{label_text}']]")
                    aria_controls = combo.get_attribute("aria-controls") or ""
                    self._human_click_el(driver, combo)
                    listbox = None
                    if aria_controls:
                        try:
                            listbox = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.ID, aria_controls))
                            )
                        except Exception:
                            listbox = None
                    if listbox is None:
                        try:
                            listbox = WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located((By.XPATH, "//*[@role='listbox']"))
                            )
                        except Exception:
                            listbox = None
                    if listbox is None:
                        continue
                    # Log all available options for debugging
                    all_options = listbox.find_elements(By.XPATH, ".//*[@role='option']")
                    option_texts_list = []
                    for opt in all_options:
                        try:
                            opt_text_val = opt.text.strip()
                            option_texts_list.append(opt_text_val)
                        except Exception:
                            pass
                    self._log_exec(f"Available options: {option_texts_list}")
                    for opt_text in option_texts:
                        self._log_exec(f"Trying to find option containing: '{opt_text}'")
                        try:
                            # Ưu tiên exact match
                            el = listbox.find_element(By.XPATH, f".//*[@role='option'][.//span[normalize-space(text())='{opt_text}']]")
                            self._log_exec(f"Found exact match: '{opt_text}'")
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                            self._human_click_el(driver, el)
                            time.sleep(0.2)
                            return True
                        except Exception:
                            # Fallback: contains nhưng chỉ match nếu có dấu ":" và đúng pattern
                            try:
                                # Chỉ match nếu opt_text có dấu ":" (như "16:9", "9:16") và text chứa chính xác pattern đó
                                if ":" in opt_text:
                                    # Tìm option có chứa pattern "X:Y" với X và Y đúng thứ tự
                                    pattern = opt_text.replace(":", r"\s*:\s*")  # Cho phép khoảng trắng quanh dấu ":"
                                    el = listbox.find_element(By.XPATH, f".//*[@role='option'][contains(., '{opt_text}')]")
                                    # Verify: text phải chứa pattern đúng thứ tự
                                    el_text = el.text.strip()
                                    if opt_text in el_text or opt_text.replace(":", " : ") in el_text or opt_text.replace(":", ": ") in el_text:
                                        self._log_exec(f"Found contains match: '{opt_text}' in '{el_text}'")
                                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                                        self._human_click_el(driver, el)
                                        time.sleep(0.2)
                                        return True
                                    else:
                                        self._log_exec(f"Contains match found but pattern doesn't match: '{opt_text}' not in '{el_text}'")
                                        continue
                                else:
                                    # Không có dấu ":", dùng contains bình thường
                                    el = listbox.find_element(By.XPATH, f".//*[@role='option'][contains(., '{opt_text}')]")
                                    self._log_exec(f"Found contains match (no colon): '{opt_text}'")
                                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                                    self._human_click_el(driver, el)
                                    time.sleep(0.2)
                                    return True
                            except Exception as e:
                                self._log_exec(f"No match found for: '{opt_text}' - {e}")
                                continue
                except Exception:
                    continue
            return False

        # Aspect ratio - normalize và thêm các biến thể có số 0
        # Normalize aspect: "09:16" -> "9:16", "16:09" -> "16:9", "09:16:00" -> "9:16"
        normalized_aspect = aspect
        if ":" in aspect:
            parts = aspect.split(":")
            # Lấy 2 phần đầu (bỏ phần giây nếu có 3 phần)
            if len(parts) >= 2:
                try:
                    w = str(int(parts[0]))  # Bỏ số 0 ở đầu
                    h = str(int(parts[1]))
                    normalized_aspect = f"{w}:{h}"
                except ValueError:
                    pass
        
        aspect_map = {
            "16:9": ["16:9", "16:09", "Khổ ngang (16:9)", "Landscape (16:9)"],
            "9:16": ["9:16", "09:16", "Khổ dọc (9:16)", "Portrait (9:16)"],
            "1:1": ["1:1", "01:01", "Vuông (1:1)", "Square (1:1)"],
        }
        # Dùng normalized_aspect để lookup, nhưng thêm cả aspect gốc vào danh sách tìm
        search_texts = aspect_map.get(normalized_aspect, [normalized_aspect, aspect])
        self._log_exec(f"Flow Images: Tìm aspect ratio: gốc='{aspect}', normalized='{normalized_aspect}', danh sách tìm={search_texts}")
        select_from_combobox(["Tỷ lệ khung hình", "Aspect ratio"], search_texts)
        time.sleep(0.5)

        # Outputs per prompt
        select_from_combobox(["Câu trả lời đầu ra cho mỗi câu lệnh", "Outputs per prompt"], [outputs])
        time.sleep(0.5)

        # Skip model selection entirely
        return

    def _select_images_mode(self, driver):
        """Click Videos then Images radio buttons (simple, required)."""
        def find_button(icon_text):
            # Try simple order-based selection first
            try:
                buttons = driver.execute_script("return Array.from(document.querySelectorAll('button[role=\"radio\"]'));")
                if buttons and len(buttons) >= 2:
                    idx = 0 if icon_text == "videocam" else 1
                    el = buttons[idx] if idx < len(buttons) else None
                    if el:
                        return el
            except Exception:
                pass
            # Fallback: XPath by icon
            xps = [
                f"//div[@role='group']//button[@role='radio' and .//i[normalize-space(text())='{icon_text}']]",
                f"//button[@role='radio' and .//i[normalize-space(text())='{icon_text}']]",
            ]
            for xp in xps:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    return el
                except Exception:
                    continue
            return None

        def click_button(el):
            if el is None:
                return False
            try:
                self._human_click_el(driver, el)
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                except Exception:
                    return False
            time.sleep(0.2)
            state = (el.get_attribute("data-state") or el.get_attribute("aria-checked") or "").lower()
            return state in ("on", "true")

        # Click Videos
        try:
            self._log_exec("Đang click nút Videos (videocam)...")
        except Exception:
            pass
        try:
            driver.refresh()
            time.sleep(2)
        except Exception:
            pass
        video_el = find_button("videocam")
        if not click_button(video_el):
            raise Exception("Không click được nút Videos")

        time.sleep(1)

        # Click Images
        try:
            self._log_exec("Đang click nút Images (image)...")
        except Exception:
            pass
        image_el = find_button("image")
        if not click_button(image_el):
            # Fallback: any radio containing Images text
            try:
                el = driver.find_element(By.XPATH, "//button[@role='radio' and contains(., 'Images')]")
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                if not click_button(el):
                    raise Exception("fallback images click failed")
            except Exception:
                raise Exception("Không chọn được nút Images")

    # ---------------- Monitor & download (images) ----------------
    def _extract_image_uris_from_api_json(self, payload):
        urls = []
        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
        except Exception:
            return urls
        try:
            result = payload.get('result', {})
            data = result.get('data', {})
            j = data.get('json', {})
            res = j.get('result', {})
            workflows = res.get('workflows', [])
            for wf in workflows:
                for st in wf.get('workflowSteps', []):
                    for g in st.get('mediaGenerations', []):
                        try:
                            img = g.get('mediaData', {}).get('imageData', {})
                            fife = img.get('generatedImage', {}).get('fifeUri') or img.get('fifeUri')
                            if fife:
                                urls.append(fife)
                        except Exception:
                            continue
        except Exception:
            return urls
        return urls

    def _monitor_and_fetch_api(self, driver, wf: str = None, prompt: str = "") -> None:
        try:
            self._log_exec("Flow Images: bắt đầu monitor & đọc API")
        except Exception:
            pass
        """Images: wait solely on TRPC API searchProjectWorkflows responses, then download fifeUri."""
        try:
            expected = int((self.outputs_per_prompt.get() or "1").strip())
            if expected <= 0:
                expected = 1
        except Exception:
            expected = 1

        target_fragment = "/fx/api/trpc/project.searchProjectWorkflows"
        collected = {}

        # Enable network logs
        try:
            driver.execute_cdp_cmd('Network.enable', {})
        except Exception:
            pass

        start = time.time()
        last_reload = 0
        initial_delay = 30  # wait 5s before first reload
        reload_interval = 6
        timeout = 60  # 2 minutes total

        while True:
            print("expected", expected)
            print("collected", collected)
            now = time.time()
            if now - start > timeout:
                break

            if now - start > initial_delay and now - last_reload >= reload_interval:
                try:
                    try:
                        self._log_exec(f"Flow Images: reload to read network (t={int(now-start)}s)")
                    except Exception:
                        pass
                    driver.refresh()
                    time.sleep(1.5)
                except Exception:
                    pass
                last_reload = now

            try:
                logs = driver.get_log('performance')
            except Exception:
                logs = []

            request_ids = []
            for item in logs:
                try:
                    msg = json.loads(item.get('message', '{}')).get('message', {})
                    method = msg.get('method')
                    params = msg.get('params', {})
                    if method == 'Network.responseReceived':
                        response = params.get('response', {})
                        url = response.get('url', '')
                        if target_fragment in url and response.get('mimeType', '').startswith('application/json'):
                            request_ids.append(params.get('requestId'))
                except Exception:
                    continue

            for rid in request_ids:
                try:
                    body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': rid})
                    text = body.get('body', '')
                    try:
                        data = json.loads(text)
                    except Exception:
                        data = text
                    urls = self._extract_image_uris_from_api_json(data)
                    for u in urls:
                        try:
                            norm = self._normalize_media_url(u)
                        except Exception:
                            norm = u
                        if norm not in collected:
                            collected[norm] = u
                except Exception:
                    continue

            if len(collected) >= expected:
                break

            time.sleep(1)

        all_urls = list(collected.values())
        if expected > 0:
            all_urls = all_urls[:expected]

        if all_urls:
            # Use prompt passed from the current job to avoid mismatching previous row's prompt
            self._download_files(all_urls, prompt)
        else:
            try:
                tk.messagebox.showerror("Thất bại", "Không tìm thấy kết quả để tải từ API.")
            except Exception:
                pass

    def _download_files(self, urls, prompt_text=""):
        """Download to a separate folder for Flow Images."""
        try:
            out_dir = Path(os.getcwd()) / "downloads_images"
            out_dir.mkdir(parents=True, exist_ok=True)
            self._log_exec("Using downloads_images folder")
            
            # Lấy 8 ký tự đầu của prompt (sanitize)
            prompt_prefix = ""
            if prompt_text:
                # Sanitize: chỉ giữ chữ cái, số, gạch dưới, bỏ khoảng trắng và ký tự đặc biệt
                sanitized = re.sub(r'[^a-zA-Z0-9_]', '', prompt_text)
                prompt_prefix = sanitized[:8].lower() if sanitized else ""
            if not prompt_prefix:
                prompt_prefix = "prompt"
            
            for i, url in enumerate(urls, 1):
                try:
                    ext = ".jpeg"
                    ts = time.strftime('%Y%m%d_%H%M%S')
                    media_number = i
                    base_name = f"{prompt_prefix}_{media_number}_{ts}{ext}"
                    dest = out_dir / base_name
                    attempt = 1
                    while dest.exists() and attempt < 1000:
                        dest = out_dir / f"{prompt_prefix}_{media_number}_{ts}_{attempt}{ext}"
                        attempt += 1
                    self._log_exec(f"Downloading {dest.name}...")
                    req = urllib.request.Request(url, headers={
                        'User-Agent': self.current_user_agent or 'Mozilla/5.0',
                        'Referer': 'https://labs.google/fx/tools/flow',
                        'Accept': '*/*',
                        'Connection': 'keep-alive',
                    })
                    max_dl_retries = 3
                    for r in range(max_dl_retries):
                        try:
                            with urllib.request.urlopen(req, timeout=30) as resp, open(dest, 'wb') as f:
                                f.write(resp.read())
                            break
                        except Exception as e:
                            if r == max_dl_retries - 1:
                                raise e
                            time.sleep(1.5)
                    self._log_exec(f"Downloaded {dest.name}", success=True)
                except Exception as ex:
                    self._log_exec(f"Failed to download #{i}: {ex}", error=True)
        except Exception as ex:
            self._log_exec(f"Download error: {ex}", error=True)


def main() -> None:
    if _HAS_TTKBOOTSTRAP and TtkbWindow is not None:
        root = TtkbWindow(themename='superhero')
    else:
        root = tk.Tk()
    FlowImagesTool(
        root,
        use_tk_ui=True,
        window_title="🖼️ Google Flow Images",
        show_story_tab=False,
        show_help_tab=False,
        force_images_mode=True,
    )
    root.mainloop()


if __name__ == "__main__":
    main()

