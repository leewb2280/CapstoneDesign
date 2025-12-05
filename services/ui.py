import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import os
import sys
from PIL import Image, ImageTk

# -----------------------------------------------------------
# [1] 경로 설정
# -----------------------------------------------------------
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

from services.skin_analyzer import process_skin_analysis


# -----------------------------------------------------------
# [2] 헬퍼 클래스: 터치 스크롤 가능한 프레임
# -----------------------------------------------------------
class ScrollableFrame(tk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)

        self.canvas = tk.Canvas(self, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="white")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.window_item = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.last_y = 0

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_item, width=event.width)

    def enable_touch_scroll(self):
        self._bind_recursive(self.scrollable_frame)
        self.canvas.bind("<ButtonPress-1>", self.start_scroll)
        self.canvas.bind("<B1-Motion>", self.do_scroll)

    def _bind_recursive(self, widget):
        if isinstance(widget, tk.Entry):
            return
        widget.bind("<ButtonPress-1>", self.start_scroll, add="+")
        widget.bind("<B1-Motion>", self.do_scroll, add="+")
        for child in widget.winfo_children():
            self._bind_recursive(child)

    def start_scroll(self, event):
        self.last_y = event.y_root

    def do_scroll(self, event):
        delta = self.last_y - event.y_root
        if abs(delta) > 0:
            self.canvas.yview_scroll(int(delta / 3), "units")
            self.last_y = event.y_root


# -----------------------------------------------------------
# [3] 로직 함수
# -----------------------------------------------------------
current_photo_image = None


def draw_gauge(canvas, oil, moisture):
    canvas.delete("all")

    # 그래프 설정값
    line_width = 30
    font_style = ("Arial", 26, "bold")

    # --- 유분 게이지 (좌측) ---
    canvas.create_oval(20, 20, 220, 220, outline="#e0e0e0", width=line_width)
    canvas.create_arc(20, 20, 220, 220, start=90, extent=-oil * 3.6,
                      outline="#00aaff", width=line_width, style="arc")
    canvas.create_text(120, 120, text=f"유분\n{int(oil)}%", fill="black", font=font_style)

    # --- 수분 게이지 (우측) ---
    canvas.create_oval(260, 20, 460, 220, outline="#e0e0e0", width=line_width)
    canvas.create_arc(260, 20, 460, 220, start=90, extent=-moisture * 3.6,
                      outline="#55ff55", width=line_width, style="arc")
    canvas.create_text(360, 120, text=f"수분\n{int(moisture)}%", fill="black", font=font_style)


def update_image_display(image_path):
    global current_photo_image
    if not image_path or not os.path.exists(image_path):
        image_display_label.config(image="", text="사진 영역", bg="#f0f0f0")
        return

    try:
        pil_image = Image.open(image_path)
        target_width = 450
        target_height = 550
        pil_image.thumbnail((target_width, target_height), Image.LANCZOS)
        current_photo_image = ImageTk.PhotoImage(pil_image)
        image_display_label.config(image=current_photo_image, text="", bg="black")
    except Exception as e:
        print(f"이미지 로드 실패: {e}")
        image_display_label.config(image="", text="이미지 로드 실패", bg="#ffcccc")


def run_measurement_thread():
    input_id = id_entry.get().strip()
    if not input_id:
        recommendation_label.config(text="⚠️ 아이디를 먼저 입력해주세요!")
        return

    measure_button.config(state="disabled", text="분석 중... (약 10초)")
    recommendation_label.config(text=f"'{input_id}'님의 피부를 분석 중입니다...")
    root.after(0, update_image_display, None)

    ui_data = None
    try:
        result = asyncio.run(process_skin_analysis(user_id=input_id, file=None))
        scores = result["scores"]
        ui_data = {
            "score": result["total_score"],
            "oil": scores.get("sebum", 0),
            "moisture": scores.get("moisture", 0),
            "acne": scores.get("acne", 0),
            "wrinkles": scores.get("wrinkles", 0),
            "pores": scores.get("pores", 0),
            "redness": scores.get("redness", 0),
            "pigmentation": scores.get("pigmentation", 0),
            "image_path": result.get("image_path")
        }
    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        ui_data = None

    root.after(0, update_ui, ui_data)


def update_ui(data):
    if data is None:
        recommendation_label.config(text="측정 실패. 다시 시도해주세요.")
        draw_gauge(canvas, 0, 0)
        score_label.config(text="종합 점수: --점")
        update_image_display(None)
    else:
        draw_gauge(canvas, data['oil'], data['moisture'])
        score_label.config(text=f"종합 점수: {data['score']}점")

        acne_label.config(text=f"여드름: {data['acne']}")
        wrinkles_label.config(text=f"주름: {data['wrinkles']}")
        pores_label.config(text=f"모공: {data['pores']}")
        redness_label.config(text=f"홍조: {data['redness']}")
        pigmentation_label.config(text=f"색소: {data['pigmentation']}")

        update_image_display(data.get('image_path'))
        recommendation_label.config(text="✅ 분석 완료! 결과가 저장되었습니다.")

    measure_button.config(state="normal", text="피부 측정하기")


def start_measurement():
    threading.Thread(target=run_measurement_thread, daemon=True).start()


# -----------------------------------------------------------
# [4] GUI 레이아웃 구성
# -----------------------------------------------------------
root = tk.Tk()
root.title("AI SkinCare Kiosk")
root.attributes('-fullscreen', True)
root.configure(bg="white")
# 키보드 ESC로도 종료 가능
root.bind("<Escape>", lambda e: root.destroy())

scroll_wrapper = ScrollableFrame(root)
scroll_wrapper.pack(side="top", fill="both", expand=True)
content_frame = scroll_wrapper.scrollable_frame

tk.Label(content_frame, text="AI 스킨케어 분석", font=("Arial", 32, "bold"), bg="white").pack(pady=(30, 20))

main_layout_frame = tk.Frame(content_frame, bg="white")
main_layout_frame.pack(fill="x", expand=True, padx=20, pady=10)

# --- 좌측 칼럼 ---
left_column = tk.Frame(main_layout_frame, bg="white")
left_column.pack(side="left", fill="both", expand=True, padx=(0, 20))

canvas = tk.Canvas(left_column, width=500, height=250, bg="white", highlightthickness=0)
canvas.pack()

score_label = tk.Label(left_column, text="종합 점수: --점", font=("Arial", 28, "bold"), fg="#007bff", bg="white")
score_label.pack(pady=10)

detail_frame = tk.Frame(left_column, bg="white")
detail_frame.pack(pady=20)

font_detail = ("Arial", 18)
width_detail = 10

row1 = tk.Frame(detail_frame, bg="white")
row1.pack(pady=8)
acne_label = tk.Label(row1, text="여드름: --", font=font_detail, bg="white", width=width_detail)
acne_label.pack(side="left", padx=5)
redness_label = tk.Label(row1, text="홍조: --", font=font_detail, bg="white", width=width_detail)
redness_label.pack(side="left", padx=5)

row2 = tk.Frame(detail_frame, bg="white")
row2.pack(pady=8)
pigmentation_label = tk.Label(row2, text="색소: --", font=font_detail, bg="white", width=width_detail)
pigmentation_label.pack(side="left", padx=5)
wrinkles_label = tk.Label(row2, text="주름: --", font=font_detail, bg="white", width=width_detail)
wrinkles_label.pack(side="left", padx=5)

row3 = tk.Frame(detail_frame, bg="white")
row3.pack(pady=8)
pores_label = tk.Label(row3, text="모공: --", font=font_detail, bg="white", width=width_detail)
pores_label.pack(side="left", padx=5)
tk.Label(row3, text="", font=font_detail, bg="white", width=width_detail).pack(side="left", padx=5)

# --- 우측 칼럼 (사진) ---
right_column = tk.Frame(main_layout_frame, bg="#f0f0f0", bd=2, relief="sunken")
right_column.pack(side="right", fill="both", expand=True, padx=(10, 0))

image_display_label = tk.Label(right_column, text="사진 영역\n(분석 후 표시)",
                               font=("Arial", 16), bg="#f0f0f0", fg="#888")
image_display_label.pack(fill="both", expand=True)

# --- 하단 입력 영역 ---
input_frame = tk.Frame(content_frame, bg="white", highlightbackground="#cccccc", highlightthickness=2)
input_frame.pack(pady=30, padx=30, ipady=15, fill="x")

tk.Label(input_frame, text="ID:", font=("Arial", 20, "bold"), bg="white").pack(side="left", padx=20)
id_entry = tk.Entry(input_frame, font=("Arial", 24), width=10, justify="center", bg="#f9f9f9")
id_entry.pack(side="left", padx=10, fill="x", expand=True)
id_entry.insert(0, "test_user")

recommendation_label = tk.Label(content_frame, text="위 아이디를 확인하고\n아래 버튼을 눌러주세요.",
                                font=("Arial", 16), bg="white", fg="#555")
recommendation_label.pack(pady=10)

tk.Label(content_frame, text="", bg="white", height=3).pack()

# --- 하단 버튼 ---
bottom_frame = tk.Frame(root, bg="white", pady=15)
bottom_frame.pack(side="bottom", fill="x")

measure_button = tk.Button(bottom_frame, text="피부 측정하기",
                           font=("Arial", 30, "bold"),
                           bg="#00aaff", fg="white", relief="flat",
                           command=start_measurement)
measure_button.pack(fill="x", padx=30, ipady=20)

# --- [추가] 우측 상단 종료 버튼 ---
# place()를 사용해 스크롤 프레임 위에 고정시킴
exit_button = tk.Button(root, text="종료", font=("Arial", 16, "bold"),
                        bg="#ff4444", fg="white", relief="flat",
                        command=root.destroy)
# 우측(relx=1.0)에서 왼쪽으로 20px, 위에서 20px 떨어진 곳에 배치
exit_button.place(relx=1.0, x=-20, y=20, anchor="ne")

# 실행
scroll_wrapper.enable_touch_scroll()
draw_gauge(canvas, 0, 0)
root.mainloop()