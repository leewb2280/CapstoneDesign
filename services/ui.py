import tkinter as tk
import threading
import asyncio
import uuid
import os

# -----------------------------------------------------------
# [1] 서버 로직 가져오기 (핵심)
# -----------------------------------------------------------
# skin_analyzer.py가 같은 폴더(혹은 services 폴더)에 있어야 합니다.
# 파일 위치에 따라 import 경로는 조정해주세요.
from .skin_analyzer import process_skin_analysis


# -----------------------------------------------------------
# [2] UI 설정 및 헬퍼 함수
# -----------------------------------------------------------
def draw_gauge(canvas, oil, moisture):
    """유수분 게이지 그리기"""
    canvas.delete("all")

    # 유분 게이지 (파란색 계열)
    canvas.create_oval(40, 40, 160, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(40, 40, 160, 160, start=90, extent=-oil * 3.6, outline="#00aaff", width=20, style="arc")
    canvas.create_text(100, 100, text=f"유분\n{int(oil)}%", fill="black", font=("Arial", 12, "bold"))

    # 수분 게이지 (초록색 계열)
    canvas.create_oval(190, 40, 310, 160, outline="#e0e0e0", width=20)
    canvas.create_arc(190, 40, 310, 160, start=90, extent=-moisture * 3.6, outline="#55ff55", width=20, style="arc")
    canvas.create_text(250, 100, text=f"수분\n{int(moisture)}%", fill="black", font=("Arial", 12, "bold"))


def get_recommendation(scores):
    """점수에 따른 간단 추천 멘트"""
    # 점수가 낮은(안 좋은) 순서대로 우선순위 추천
    if scores['moisture'] < 30: return "수분 크림 (보습 강화 시급)"
    if scores['acne'] > 40: return "트러블 케어 앰플 (진정)"
    if scores['redness'] > 40: return "쿨링 시트팩 (홍조 완화)"
    if scores['wrinkles'] > 40: return "레티놀 세럼 (주름 개선)"
    return "현재 상태 양호 (유수분 밸런스 유지)"


def get_status_text(score):
    """0~100점 점수를 텍스트로 변환"""
    if score < 20:
        return "좋음"
    elif score < 50:
        return "보통"
    else:
        return "관리 필요"  # 점수가 높을수록 안 좋은 항목(트러블 등) 가정


# -----------------------------------------------------------
# [3] 측정 스레드 (비동기 처리)
# -----------------------------------------------------------
def run_measurement_thread():
    # 1. 버튼 비활성화 및 로딩 표시
    measure_button.config(state="disabled", text="분석 중... (약 10초)")
    recommendation_label.config(text="센서 측정 및 AI 분석을 진행하고 있습니다...")

    try:
        # 2. skin_analyzer의 통합 함수 호출
        # (센서 측정 + 카메라 촬영 + GPT 분석 + DB 저장이 한방에 됨)

        # UI에서는 user_id를 고정하거나 입력받아야 함 (여기선 demo_user로 가정)
        user_id = "demo_user_kiosk"

        # 비동기 함수를 동기식 UI에서 실행하기 위해 asyncio.run 사용
        # 주의: file=None으로 보내면 skin_analyzer가 알아서 카메라를 켭니다.
        result = asyncio.run(process_skin_analysis(user_id=user_id, file=None))

        # 3. 결과 받아오기
        final_scores = result["scores"]
        total_score = result["total_score"]

        # UI 업데이트용 데이터 정리
        ui_data = {
            "oil": final_scores["sebum"],
            "moisture": final_scores["moisture"],
            "score": total_score,
            # GPT는 0(좋음)~100(나쁨) 점수를 줌
            "trouble_text": f"{get_status_text(final_scores['acne'])} ({final_scores['acne']}점)",
            "redness_text": f"{get_status_text(final_scores['redness'])} ({final_scores['redness']}점)",
            "reco": get_recommendation(final_scores)
        }

        print(f"✅ 분석 완료: {ui_data}")

    except Exception as e:
        print(f"❌ 분석 실패: {e}")
        ui_data = None
        error_msg = str(e)

    # 4. UI 갱신 (메인 스레드에서 실행)
    root.after(0, update_ui, ui_data)


def update_ui(data):
    if data:
        draw_gauge(canvas, data['oil'], data['moisture'])

        score_label.config(text=f"종합 점수: {data['score']}점")
        trouble_label.config(text=f"트러블: {data['trouble_text']}")
        redness_label.config(text=f"홍조: {data['redness_text']}")
        recommendation_label.config(text=data['reco'])
    else:
        recommendation_label.config(text="측정 실패. 다시 시도해주세요.")

    measure_button.config(state="normal", text="다시 측정하기")


def start_measurement():
    # UI 멈춤 방지를 위해 별도 스레드에서 실행
    threading.Thread(target=run_measurement_thread, daemon=True).start()


# -----------------------------------------------------------
# [4] GUI 메인 (Tkinter)
# -----------------------------------------------------------
root = tk.Tk()
root.title("AI SkinCare Kiosk")

# 전체화면 설정 (라즈베리파이용)
# root.attributes('-fullscreen', True)
# 테스트용으로는 창 크기 지정
root.geometry("480x800")

root.configure(bg="white")
root.bind("<Escape>", lambda e: root.destroy())  # ESC 누르면 종료

# --- 상단 타이틀 ---
title = tk.Label(root, text="AI 스킨케어 분석", font=("Arial", 20, "bold"), fg="black", bg="white")
title.pack(pady=20)

# --- 게이지 캔버스 ---
canvas = tk.Canvas(root, width=350, height=200, bg="white", highlightthickness=0)
canvas.pack()

# --- 종합 점수 ---
score_label = tk.Label(root, text="종합 점수: --점", font=("Arial", 18, "bold"), fg="#007bff", bg="white")
score_label.pack(pady=5)

# --- 상세 상태 (트러블/홍조 등) ---
state_frame = tk.Frame(root, bg="white")
state_frame.pack(pady=10)

trouble_label = tk.Label(state_frame, text="트러블: --", font=("Arial", 14), fg="#555", bg="white")
trouble_label.pack(anchor="w", padx=20)

redness_label = tk.Label(state_frame, text="홍조: --", font=("Arial", 14), fg="#555", bg="white")
redness_label.pack(anchor="w", padx=20)

# --- 추천 멘트 ---
reco_title_label = tk.Label(root, text="[ AI 솔루션 ]", font=("Arial", 14, "bold"), fg="#d9534f", bg="white")
reco_title_label.pack(pady=(20, 5))

recommendation_label = tk.Label(root, text="버튼을 눌러 측정을 시작하세요.", font=("Arial", 12), fg="#333", bg="white",
                                wraplength=350)
recommendation_label.pack(pady=5)

# --- 측정 버튼 ---
measure_button = tk.Button(root, text="피부 측정하기",
                           font=("Arial", 16, "bold"),
                           bg="#00aaff", fg="white", relief="flat",
                           height=2,
                           command=start_measurement)
measure_button.pack(side="bottom", pady=30, padx=20, fill="x")

# 초기 게이지 그리기 (0점)
draw_gauge(canvas, 0, 0)

root.mainloop()