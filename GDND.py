import sys
import os

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import ctypes
from ctypes import wintypes
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import cv2

from mp_path_fix import fix_windows_unicode_path
from zoom_image2 import run_zoom

VALID_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")

def get_short_path_windows(long_path):
    if os.name != "nt" or not long_path:
        return long_path
    try:
        _GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        _GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        _GetShortPathNameW.restype = wintypes.DWORD

        abs_path = os.path.abspath(long_path)
        buf_size = _GetShortPathNameW(abs_path, None, 0)
        if buf_size == 0:
            return abs_path
        buf = ctypes.create_unicode_buffer(buf_size)
        if _GetShortPathNameW(abs_path, buf, buf_size) == 0:
            return abs_path
        return buf.value
    except Exception:
        return long_path

def load_image_safe(file_path):
    if not file_path:
        return None, None, "Chưa chọn đường dẫn ảnh."

    clean_path = file_path.strip().strip('"').strip("'")

    if not os.path.exists(clean_path):
        return None, None, f"Đường dẫn không tồn tại:\n{clean_path}"

    if not os.path.isfile(clean_path):
        return None, None, f"Đường dẫn không phải là tệp hợp lệ:\n{clean_path}"

    ext = os.path.splitext(clean_path)[1].lower()
    if ext not in VALID_EXTENSIONS:
        return (
            None,
            None,
            f"Định dạng '{ext}' không được hỗ trợ.\nChỉ hỗ trợ: {', '.join(VALID_EXTENSIONS)}"
        )

    short_path = get_short_path_windows(clean_path)
    img = cv2.imread(short_path)

    if img is None:
        try:
            raw_data = np.fromfile(clean_path, dtype=np.uint8)
            img = cv2.imdecode(raw_data, cv2.IMREAD_COLOR)
        except Exception as e:
            return None, None, f"Lỗi khi đọc tệp ảnh:\n{str(e)}"

    if img is None:
        return None, None, "Không thể giải mã tệp ảnh (file có thể bị hỏng hoặc sai cấu trúc)."

    return img, short_path, None


def open_webcam_safe(cam_index=0):
    try:
        idx = int(cam_index)
    except ValueError:
        return None, f"Chỉ số webcam không hợp lệ: {cam_index}"

    cap = None
    if os.name == "nt":
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(idx)
    else:
        cap = cv2.VideoCapture(idx)

    if cap is None or not cap.isOpened():
        if cap is not None:
            cap.release()
        return None, f"Không thể mở Webcam số {idx}. Vui lòng kiểm tra kết nối hoặc chọn Webcam khác."

    ret, frame = cap.read()
    if not ret or frame is None:
        cap.release()
        return None, f"Webcam số {idx} đang bận hoặc không trả về hình ảnh."

    return cap, None

def scan_available_webcams(max_index=4):
    available = []
    for idx in range(max_index):
        cap, err = open_webcam_safe(idx)
        if cap is not None:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            available.append((idx, f"Camera {idx} - Hoạt động ({w}x{h})"))
    return available

def select_image_dialog(initial_path="", default_cam_index=0):
    result = {"img": None, "path": None, "cam_index": None}

    root = tk.Tk()
    root.title("Cấu hình Ảnh & Webcam - Hand Gesture Zoom")
    root.geometry("580x440")
    root.resizable(False, False)
    root.configure(bg="#1e1e2e")

    root.attributes("-topmost", True)
    root.after(250, lambda: root.attributes("-topmost", False))
    root.lift()
    root.focus_force()

    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    x_pos = (sw - 580) // 2
    y_pos = (sh - 440) // 2
    root.geometry(f"580x440+{x_pos}+{y_pos}")

    path_var = tk.StringVar(master=root, value=initial_path)
    status_var = tk.StringVar(master=root, value="Chưa chọn ảnh nào.")

    cam_options_map = {
        "Camera 0 (Mặc định / Laptop)": 0,
        "Camera 1 (Webcam rời / USB)": 1,
        "Camera 2 (Thiết bị phụ / Ảo)": 2,
        "Camera 3": 3,
    }
    default_cam_label = f"Camera {default_cam_index} (Mặc định / Laptop)"
    for k, v in cam_options_map.items():
        if v == default_cam_index:
            default_cam_label = k
            break

    cam_var = tk.StringVar(master=root, value=default_cam_label)
    cam_status_var = tk.StringVar(master=root, value="Mặc định: Camera 0 (Nhấn 'Quét Cam' hoặc 'Thử Cam' để kiểm tra)")

    lbl_title = tk.Label(
        root,
        text="CHỌN ẢNH & WEBCAM ĐẦU VÀO",
        font=("Segoe UI", 13, "bold"),
        fg="#cdd6f4",
        bg="#1e1e2e"
    )
    lbl_title.pack(pady=(12, 6))

    drop_canvas = tk.Canvas(
        root,
        width=520,
        height=130,
        bg="#313244",
        highlightthickness=0,
        cursor="hand2"
    )
    drop_canvas.pack(padx=30, pady=4)

    rect_id = drop_canvas.create_rectangle(
        8, 8, 512, 122,
        outline="#89b4fa",
        width=2,
        dash=(6, 4)
    )
    drop_canvas.create_text(
        260, 44,
        text="KÉO VÀ THẢ FILE ẢNH VÀO KHUNG NÀY",
        font=("Segoe UI", 11, "bold"),
        fill="#89b4fa"
    )
    drop_canvas.create_text(
        260, 72,
        text="hoặc nhấp chuột vào đây để mở hộp thoại chọn ảnh từ máy tính",
        font=("Segoe UI", 9),
        fill="#a6adc8"
    )
    drop_canvas.create_text(
        260, 100,
        text="Hỗ trợ: .png, .jpg, .jpeg, .webp, .bmp, .tiff",
        font=("Segoe UI", 8, "italic"),
        fill="#6c7086"
    )

    path_frame = tk.Frame(root, bg="#1e1e2e")
    path_frame.pack(fill="x", padx=30, pady=(8, 2))

    entry_path = tk.Entry(
        path_frame,
        textvariable=path_var,
        font=("Segoe UI", 10),
        bg="#45475a",
        fg="#ffffff",
        insertbackground="#ffffff",
        relief="flat"
    )
    entry_path.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))

    lbl_status = tk.Label(
        root,
        textvariable=status_var,
        font=("Segoe UI", 9),
        fg="#a6adc8",
        bg="#1e1e2e",
        anchor="w"
    )

    def verify_file(candidate_path, show_popup_on_error=True):
        img, valid_path, err = load_image_safe(candidate_path)
        path_var.set(candidate_path.strip().strip('"').strip("'"))
        if err:
            status_var.set("Lỗi ảnh: " + err.replace("\n", " "))
            lbl_status.config(fg="#f38ba8")
            drop_canvas.itemconfig(rect_id, outline="#f38ba8")
            result["img"] = None
            result["path"] = None
            if show_popup_on_error:
                messagebox.showerror("Lỗi đọc ảnh", err, parent=root)
            return False
        else:
            h, w = img.shape[:2]
            fname = os.path.basename(candidate_path.strip().strip('"').strip("'"))
            status_var.set(f"Ảnh hợp lệ: {fname} ({w}x{h} px)")
            lbl_status.config(fg="#a6e3a1")
            drop_canvas.itemconfig(rect_id, outline="#a6e3a1")
            result["img"] = img
            result["path"] = valid_path
            return True

    def open_file_dialog(event=None):
        chosen = filedialog.askopenfilename(
            parent=root,
            title="Chọn ảnh từ máy tính",
            filetypes=[
                ("Tệp hình ảnh", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tiff"),
                ("Tất cả các tệp", "*.*")
            ]
        )
        if chosen:
            verify_file(chosen, show_popup_on_error=True)

    btn_browse = tk.Button(
        path_frame,
        text="Chọn file...",
        command=open_file_dialog,
        font=("Segoe UI", 9, "bold"),
        bg="#585b70",
        fg="#ffffff",
        activebackground="#6c7086",
        activeforeground="#ffffff",
        relief="flat",
        padx=12,
        pady=4,
        cursor="hand2"
    )
    btn_browse.pack(side="right")

    drop_canvas.bind("<Button-1>", open_file_dialog)
    lbl_status.pack(fill="x", padx=30, pady=(2, 6))

    cam_section = tk.Frame(root, bg="#28283d", bd=0, highlightthickness=1, highlightbackground="#45475a")
    cam_section.pack(fill="x", padx=30, pady=(4, 8), ipady=6)

    cam_row = tk.Frame(cam_section, bg="#28283d")
    cam_row.pack(fill="x", padx=12, pady=(6, 2))

    lbl_cam = tk.Label(
        cam_row,
        text="Thiết bị Webcam:",
        font=("Segoe UI", 9, "bold"),
        fg="#cdd6f4",
        bg="#28283d"
    )
    lbl_cam.pack(side="left", padx=(0, 8))

    combo_cam = ttk.Combobox(
        cam_row,
        textvariable=cam_var,
        values=list(cam_options_map.keys()),
        state="readonly",
        font=("Segoe UI", 9),
        width=28
    )
    combo_cam.pack(side="left", fill="x", expand=True, padx=(0, 8))

    lbl_cam_status = tk.Label(
        cam_section,
        textvariable=cam_status_var,
        font=("Segoe UI", 8),
        fg="#a6adc8",
        bg="#28283d",
        anchor="w"
    )
    lbl_cam_status.pack(fill="x", padx=12, pady=(2, 2))

    def get_selected_cam_index():
        label = cam_var.get().strip()
        if label in cam_options_map:
            return cam_options_map[label]
        for token in label.split():
            if token.isdigit():
                return int(token)
        return 0

    def on_test_cam():
        idx = get_selected_cam_index()
        cam_status_var.set(f"Đang kiểm tra Camera {idx}...")
        lbl_cam_status.config(fg="#f9e2af")
        root.update_idletasks()

        cap, err = open_webcam_safe(idx)
        if err:
            cam_status_var.set(err)
            lbl_cam_status.config(fg="#f38ba8")
            messagebox.showerror("Lỗi Webcam", err, parent=root)
        else:
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            cap.release()
            cam_status_var.set(f"Camera {idx} hoạt động tốt (Độ phân giải: {w}x{h} px)")
            lbl_cam_status.config(fg="#a6e3a1")

    def on_scan_cams():
        cam_status_var.set("Đang quét các cổng Webcam (0 -> 3), vui lòng đợi...")
        lbl_cam_status.config(fg="#f9e2af")
        root.update_idletasks()

        found = scan_available_webcams(max_index=4)
        if not found:
            cam_status_var.set("Không tìm thấy Webcam nào khả dụng từ cổng 0 đến 3!")
            lbl_cam_status.config(fg="#f38ba8")
            messagebox.showwarning(
                "Không tìm thấy Webcam",
                "Không phát hiện được Webcam nào hoạt động (Index 0 -> 3).",
                parent=root
            )
        else:
            cam_options_map.clear()
            for idx, desc in found:
                cam_options_map[desc] = idx
            new_keys = list(cam_options_map.keys())
            combo_cam.config(values=new_keys)
            cam_var.set(new_keys[0])
            cam_status_var.set(f"Đã tìm thấy {len(found)} thiết bị khả dụng. Đã chọn: {new_keys[0]}")
            lbl_cam_status.config(fg="#a6e3a1")

    btn_test_cam = tk.Button(
        cam_row,
        text="Thử Cam",
        command=on_test_cam,
        font=("Segoe UI", 8, "bold"),
        bg="#585b70",
        fg="#ffffff",
        activebackground="#6c7086",
        activeforeground="#ffffff",
        relief="flat",
        padx=8,
        pady=3,
        cursor="hand2"
    )
    btn_test_cam.pack(side="right", padx=(4, 0))

    btn_scan_cam = tk.Button(
        cam_row,
        text="Quét Cam",
        command=on_scan_cams,
        font=("Segoe UI", 8, "bold"),
        bg="#45475a",
        fg="#89b4fa",
        activebackground="#585b70",
        activeforeground="#ffffff",
        relief="flat",
        padx=8,
        pady=3,
        cursor="hand2"
    )
    btn_scan_cam.pack(side="right")

    hook_state = {"hwnd": None, "old_wndproc": None, "new_wndproc": None}

    def safe_close():
        if hook_state["hwnd"] and hook_state["old_wndproc"]:
            try:
                user32 = ctypes.windll.user32
                SetWindowLongPtrW = (
                    user32.SetWindowLongPtrW
                    if ctypes.sizeof(ctypes.c_void_p) == 8
                    else user32.SetWindowLongW
                )
                SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
                SetWindowLongPtrW.restype = ctypes.c_void_p
                SetWindowLongPtrW(hook_state["hwnd"], -4, hook_state["old_wndproc"])
            except Exception:
                pass
            hook_state["old_wndproc"] = None
        root.quit()
        root.destroy()

    def on_confirm(event=None):
        raw_path = path_var.get().strip()
        if not raw_path:
            messagebox.showwarning(
                "Chưa chọn ảnh",
                "Vui lòng kéo thả ảnh vào khung hoặc bấm 'Chọn file...' trước!",
                parent=root
            )
            return
        if not verify_file(raw_path, show_popup_on_error=True):
            return

        chosen_cam = get_selected_cam_index()
        cap, cam_err = open_webcam_safe(chosen_cam)
        if cam_err:
            cam_status_var.set(cam_err)
            lbl_cam_status.config(fg="#f38ba8")
            ask_continue = messagebox.askyesno(
                "Cảnh báo Webcam",
                f"{cam_err}\n\nBạn có vẫn muốn tiếp tục với Camera {chosen_cam} không?",
                parent=root
            )
            if not ask_continue:
                return
        else:
            cap.release()

        result["cam_index"] = chosen_cam
        safe_close()

    def on_cancel():
        result["img"] = None
        result["path"] = None
        result["cam_index"] = None
        safe_close()

    entry_path.bind("<Return>", on_confirm)
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    btn_frame = tk.Frame(root, bg="#1e1e2e")
    btn_frame.pack(fill="x", padx=30, pady=(6, 12))

    btn_ok = tk.Button(
        btn_frame,
        text="Mở ảnh & Bắt đầu",
        command=on_confirm,
        font=("Segoe UI", 10, "bold"),
        bg="#89b4fa",
        fg="#11111b",
        activebackground="#b4befe",
        relief="flat",
        padx=18,
        pady=6,
        cursor="hand2"
    )
    btn_ok.pack(side="right", padx=(8, 0))

    btn_exit = tk.Button(
        btn_frame,
        text="Hủy / Thoát",
        command=on_cancel,
        font=("Segoe UI", 10),
        bg="#45475a",
        fg="#cdd6f4",
        activebackground="#585b70",
        relief="flat",
        padx=14,
        pady=6,
        cursor="hand2"
    )
    btn_exit.pack(side="right")

    if os.name == "nt":
        try:
            WM_DROPFILES = 0x0233
            GWL_WNDPROC = -4
            LRESULT = ctypes.c_ssize_t
            WPARAM = ctypes.c_size_t
            LPARAM = ctypes.c_ssize_t
            WNDPROCTYPE = ctypes.WINFUNCTYPE(
                LRESULT, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM
            )

            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32

            shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
            shell32.DragQueryFileW.argtypes = [
                wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT
            ]
            shell32.DragQueryFileW.restype = wintypes.UINT
            shell32.DragFinish.argtypes = [wintypes.HANDLE]

            SetWindowLongPtrW = (
                user32.SetWindowLongPtrW
                if ctypes.sizeof(ctypes.c_void_p) == 8
                else user32.SetWindowLongW
            )
            SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
            SetWindowLongPtrW.restype = ctypes.c_void_p

            CallWindowProcW = user32.CallWindowProcW
            CallWindowProcW.argtypes = [
                ctypes.c_void_p, wintypes.HWND, wintypes.UINT, WPARAM, LPARAM
            ]
            CallWindowProcW.restype = LRESULT

            hwnd = int(root.wm_frame(), 16) if root.wm_frame() else root.winfo_id()

            try:
                user32.ChangeWindowMessageFilterEx(hwnd, WM_DROPFILES, 1, None)
                user32.ChangeWindowMessageFilterEx(hwnd, 0x0049, 1, None)
            except Exception:
                pass

            shell32.DragAcceptFiles(hwnd, True)

            def wndproc_callback(h_wnd, msg, wparam, lparam):
                if msg == WM_DROPFILES:
                    hdrop = wparam
                    count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
                    if count > 0:
                        length = shell32.DragQueryFileW(hdrop, 0, None, 0)
                        buf = ctypes.create_unicode_buffer(length + 1)
                        shell32.DragQueryFileW(hdrop, 0, buf, length + 1)
                        dropped_path = buf.value
                        root.after(
                            10,
                            lambda p=dropped_path: verify_file(p, show_popup_on_error=True)
                        )
                    shell32.DragFinish(hdrop)
                    return 0
                return CallWindowProcW(
                    hook_state["old_wndproc"], h_wnd, msg, wparam, lparam
                )

            hook_state["hwnd"] = hwnd
            hook_state["new_wndproc"] = WNDPROCTYPE(wndproc_callback)
            hook_state["old_wndproc"] = SetWindowLongPtrW(
                hwnd,
                GWL_WNDPROC,
                ctypes.cast(hook_state["new_wndproc"], ctypes.c_void_p)
            )
        except Exception as e:
            print("[CANH BAO] Khong the kich hoat Keo & Tha Win32:", e)

    if initial_path and os.path.exists(initial_path):
        verify_file(initial_path, show_popup_on_error=False)

    root.mainloop()
    return result["img"], result["path"], result["cam_index"]

if __name__ == "__main__":
    if "SPYDER_ARGS" not in os.environ and "IPYKERNEL_CELL_NAME" not in os.environ:
        fix_windows_unicode_path(__file__)

    print("[TEST MUC 1] Dang mo cua so chon Anh & Webcam...")
    selected_img, selected_path, selected_cam = select_image_dialog()

    if selected_img is not None and selected_cam is not None:
        print(f"[THANH CONG] Da chon anh: {selected_path}")
        print(f"[THONG TIN] Kich thuoc anh: {selected_img.shape[1]}x{selected_img.shape[0]} px")
        print(f"[WEBCAM] Da chon Camera Index: {selected_cam}")
        run_zoom(selected_img,selected_cam)
    else:
        print("[THONG BAO] Nguoi dung da huy chon anh/webcam.")