import tkinter as tk
from tkinter import ttk
import threading
import asyncio
import os
import sys

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

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.last_y = 0

    def enable_touch_scroll(self):
        """내부 위젯들에 터치 스크롤 기능 주입"""
        self._bind_recursive(self.scrollable_frame)
        self.canvas.bind("<ButtonPress-1>", self.start_scroll)
        self.canvas.bind("<B1-Motion>", self.do_scroll)

    def _bind_recursive(self, widget):
        # [중요] 입력창(Entry)에서는 스크롤이 되면 안 됨 (글자 선택 방해)
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
def draw_gauge(canvas, oil, moisture):
    canvas.delete("all")
    # 유분
    canvas.create_oval(40, 40, 160, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(40, 40, 160, 160, start=90, extent=-oil * 3.6, outline="#00aaff", width=20, style="arc")
    canvas.create_text(100, 100, text=f"유분\n{int(oil)}%", fill="black", font=("Arial", 12, "bold"))
    # 수분
    canvas.create_oval(190, 40, 310, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(190, 40, 310, 160, start=90, extent=-moisture * 3.6, outline="#55ff55", width=20, style="arc")
    canvas.create_text(250, 100, text=f"수분\n{int(moisture)}%", fill="black", font=("Arial", 12, "bold"))


def run_measurement_thread():
    input_id = id_entry.get().strip()
    if not input_id:
        recommendation_label.config(text="⚠️ 아이디를 먼저 입력해주세요!")
        return

    measure_button.config(state="disabled", text="분석 중... (약 10초)")
    recommendation_label.config(text=f"'{input_id}'님의 피부를 분석 중입니다...")

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
            "pigmentation": scores.get("pigmentation", 0)
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
    else:
        draw_gauge(canvas, data['oil'], data['moisture'])
        score_label.config(text=f"종합 점수: {data['score']}점")

        acne_label.config(text=f"여드름: {data['acne']}")
        wrinkles_label.config(text=f"주름: {data['wrinkles']}")
        pores_label.config(text=f"모공: {data['pores']}")
        redness_label.config(text=f"홍조: {data['redness']}")
        pigmentation_label.config(text=f"색소: {data['pigmentation']}")

        recommendation_label.config(text="✅ 분석 완료! 결과가 저장되었습니다.")

    measure_button.config(state="normal", text="피부 측정하기")


def start_measurement():
    threading.Thread(target=run_measurement_thread, daemon=True).start()


# -----------------------------------------------------------
# [4] GUI 레이아웃 구성
# -----------------------------------------------------------
root = tk.Tk()
root.title("AI SkinCare Kiosk")
# root.attributes('-fullscreen', True) # 전체화면 필요 시 해제
root.geometry("480x800")
root.configure(bg="white")
root.bind("<Escape>", lambda e: root.destroy())

# --- 1. 상단 스크롤 영역 (여기에 내용을 다 넣습니다) ---
scroll_wrapper = ScrollableFrame(root)
scroll_wrapper.pack(side="top", fill="both", expand=True)

# content_frame: 실제 내용이 담기는 곳
content_frame = scroll_wrapper.scrollable_frame

# [내용물 배치]
tk.Label(content_frame, text="AI 스킨케어 분석", font=("Arial", 20, "bold"), bg="white").pack(pady=20)

canvas = tk.Canvas(content_frame, width=350, height=200, bg="white", highlightthickness=0)
canvas.pack()

score_label = tk.Label(content_frame, text="종합 점수: --점", font=("Arial", 18, "bold"), fg="#007bff", bg="white")
score_label.pack(pady=5)

# 상세 점수 (2열 배치)
detail_frame = tk.Frame(content_frame, bg="white")
detail_frame.pack(pady=10)

row1 = tk.Frame(detail_frame, bg="white")
row1.pack(pady=5)
acne_label = tk.Label(row1, text="여드름: --", font=("Arial", 12), bg="white", width=12)
acne_label.pack(side="left")
redness_label = tk.Label(row1, text="홍조: --", font=("Arial", 12), bg="white", width=12)
redness_label.pack(side="left")

row2 = tk.Frame(detail_frame, bg="white")
row2.pack(pady=5)
pigmentation_label = tk.Label(row2, text="색소: --", font=("Arial", 12), bg="white", width=12)
pigmentation_label.pack(side="left")
wrinkles_label = tk.Label(row2, text="주름: --", font=("Arial", 12), bg="white", width=12)
wrinkles_label.pack(side="left")

row3 = tk.Frame(detail_frame, bg="white")
row3.pack(pady=5)
pores_label = tk.Label(row3, text="모공: --", font=("Arial", 12), bg="white", width=12)
pores_label.pack(side="left")
tk.Label(row3, text="", font=("Arial", 12), bg="white", width=12).pack(side="left")  # 줄 맞춤용 공백

# --- [중요] 아이디 입력칸은 스크롤 영역 안에 넣습니다 ---
input_frame = tk.Frame(content_frame, bg="white", highlightbackground="#cccccc", highlightthickness=1)
input_frame.pack(pady=20, padx=20, ipady=10, fill="x")

tk.Label(input_frame, text="ID:", font=("Arial", 14, "bold"), bg="white").pack(side="left", padx=10)
id_entry = tk.Entry(input_frame, font=("Arial", 16), width=10, justify="center", bg="#f9f9f9")
id_entry.pack(side="left", padx=5, fill="x", expand=True)
id_entry.insert(0, "test_user")

# 안내 메시지 (입력칸 아래)
recommendation_label = tk.Label(content_frame, text="위 아이디를 확인하고\n아래 버튼을 눌러주세요.", font=("Arial", 12), bg="white",
                                fg="#555")
recommendation_label.pack(pady=10)

# 하단 여백 확보 (버튼에 가려지지 않게)
tk.Label(content_frame, text="", bg="white", height=2).pack()

# --- 2. 하단 고정 영역 (버튼은 여기에!) ---
bottom_frame = tk.Frame(root, bg="white", pady=10)
bottom_frame.pack(side="bottom", fill="x")

measure_button = tk.Button(bottom_frame, text="피부 측정하기",
                           font=("Arial", 22, "bold"),
                           bg="#00aaff", fg="white", relief="flat",
                           command=start_measurement)
# 버튼을 뚱뚱하게(ipady) 만들고 좌우 여백(padx)을 줍니다.
measure_button.pack(fill="x", padx=20, ipady=15)

# -----------------------------------------------------------
# [마지막] 터치 활성화 및 실행
# -----------------------------------------------------------
scroll_wrapper.enable_touch_scroll()
draw_gauge(canvas, 0, 0)
root.mainloop()