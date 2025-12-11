import tkinter as tk
import json
import time

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
        """Override to force fixed model (no selection flow)."""
        forced_model = getattr(self, "_force_model", "Nano Banana Pro")
        return super()._open_settings_and_apply(driver, aspect, outputs, forced_model)

    def _select_images_mode(self, driver):
        """For Flow Images: click Videos first, wait 1s, then click Images (no class selectors)."""
        def click_radio(icon_text):
            candidates = [
                f"//button[@role='radio' and .//i[normalize-space(text())='{icon_text}']]",
                f"//button[@role='radio' and contains(., '{icon_text}')]",
            ]
            for xp in candidates:
                try:
                    el = driver.find_element(By.XPATH, xp)
                    try:
                        self._log_exec(f"Tìm thấy nút radio '{icon_text}' với xpath: {xp}")
                    except Exception:
                        pass
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    self._human_click_el(driver, el)
                    time.sleep(0.2)
                    state = el.get_attribute("data-state") or el.get_attribute("aria-checked")
                    if state and str(state).lower() in ("on", "true"):
                        try:
                            self._log_exec(f"Đã click thành công radio '{icon_text}', state={state}")
                        except Exception:
                            pass
                        return True
                except Exception:
                    continue
            return False

        try:
            self._log_exec("Đang click nút Videos (videocam)...")
        except Exception:
            pass
        clicked_videos = click_radio("videocam")
        time.sleep(1)
        try:
            self._log_exec("Đang click nút Images (image)...")
        except Exception:
            pass
        clicked_images = click_radio("image")
        if not clicked_images:
            raise Exception("Không chọn được nút Images")
        if not clicked_videos:
            try:
                self._log_exec("Không click được nút Videos trước, tiếp tục với Images", error=False)
            except Exception:
                pass

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

    def _monitor_and_fetch_api(self, driver, wf: str = None) -> None:
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
        initial_delay = 20  # wait 20s before first reload
        reload_interval = 8
        timeout = 90  # 1m30s total

        while True:
            now = time.time()
            if now - start > timeout:
                break

            if now - start > initial_delay and now - last_reload >= reload_interval:
                try:
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
            prompt_text = getattr(self, 'current_prompt', '')
            self._download_files(all_urls, prompt_text)
        else:
            try:
                tk.messagebox.showerror("Thất bại", "Không tìm thấy kết quả để tải từ API.")
            except Exception:
                pass


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

