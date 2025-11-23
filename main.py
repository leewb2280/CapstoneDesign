# main.py
"""
[AI Skin Advisor API Server]
- Mobile App & Kiosk Backend
- Features: Skin Analysis (GPT), Product Recommendation, Hardware Control
"""

import os
import shutil
import uuid
import random
import logging

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 사용자 정의 모듈 임포트
from skin_analyzer import perform_skin_analysis
from skin_advisor import run_skin_advisor
from data_collector import run_data_collection

# 로깅 설정 (서버 로그를 더 잘 보기 위해)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# 1. 서버 설정 (Configuration)
# ==========================================
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# API 문서(Swagger UI)를 예쁘게 정리하기 위한 태그 설정
tags_metadata = [
    {"name": "General", "description": "기본 페이지 및 정적 파일"},
    {"name": "Mobile App", "description": "모바일 앱 연동 API (분석 -> 추천)"},
    {"name": "Kiosk", "description": "키오스크/하드웨어 연동 API (원스톱 진단)"},
    {"name": "Admin", "description": "데이터 관리 및 업데이트"},
]

app = FastAPI(
    title="AI Skin Advisor Server",
    description="캡스톤 디자인 - 피부 분석 및 화장품 추천 시스템",
    version="1.0.0",
    openapi_tags=tags_metadata
)

# [중요] CORS 설정 (앱/웹 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 IP에서 접속 허용 (배포 시 보안 주의)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# 2. 데이터 모델 (DTO)
# ==========================================
class LifestyleData(BaseModel):
    sleep_hours_7d: float
    water_intake_ml: int
    wash_freq_per_day: int
    wash_temp: str
    sensitivity: str


class UserPref(BaseModel):
    age: int
    pref_texture: str


class RecommendRequest(BaseModel):
    user_id: str
    analysis_id: int
    lifestyle: LifestyleData
    user_pref: UserPref


# ==========================================
# 3. 하드웨어 제어 로직 (Hardware Control)
# ==========================================
# 하드웨어 라이브러리 추가
try:
    # 라즈베리파이 전용 라이브러리들
    import spidev       # SPI 통신 (유수분 센서용)
    import RPi.GPIO as GPIO # GPIO 제어용
    IS_RASPBERRY_PI = True
except ImportError:
    # PC에서 실행 중이면 에러가 나므로 가상 모드로 전환
    print("⚠️ 라즈베리파이가 아닙니다. 가상 모드(Mock)로 동작합니다.")
    IS_RASPBERRY_PI = False
    spidev = None


def hardware_capture():
    """
    [하드웨어 제어] 실제 센서/카메라가 있으면 작동시키고, 데이터를 가져옵니다.
    """
    logger.info("📡 하드웨어 데이터 수집 시작...")

    # 1. 라즈베리파이인지 확인 (PC면 가짜 데이터 반환)
    if IS_RASPBERRY_PI:
        try:
            # ---------------------------------------------------------
            # [A] 카메라 촬영 (libcamera 사용 예시)
            # ---------------------------------------------------------
            real_img_path = os.path.join(UPLOAD_DIR, "capture.jpg")

            # 터미널 명령어 실행 (카메라로 사진 찍어서 파일로 저장)
            # --nopreview: 화면 안 띄움, -t 1: 1ms 후 촬영, -o: 저장 경로
            os.system(f"libcamera-still -o {real_img_path} --width 640 --height 640 -t 1 --nopreview")

            if not os.path.exists(real_img_path):
                raise Exception("사진 촬영 실패")

            # ---------------------------------------------------------
            # [B] 유수분 센서 측정 (SPI 통신 예시)
            # ---------------------------------------------------------
            # (하드웨어 담당 팀원에게 받은 코드를 여기에 넣으세요!)

            # 예: ADC(아날로그-디지털 변환기) 값 읽기
            # spi = spidev.SpiDev()
            # spi.open(0, 0)
            # adc_value = spi.xfer2([1, (8 + 0) << 4, 0]) ...

            # 여기서는 예시로 임의의 변수에 센서값을 넣었다고 가정합니다.
            real_moisture = 45  # 실제 센서에서 읽은 값 변수
            real_sebum = 60  # 실제 센서에서 읽은 값 변수

            logger.info(f"📸 촬영 완료: {real_img_path}, 센서: 수분{real_moisture}/유분{real_sebum}")

            return real_img_path, real_moisture, real_sebum

        except Exception as e:
            logger.error(f"하드웨어 오류: {e}")
            # 오류 나면 가짜 데이터라도 반환해서 멈추지 않게 함 (선택사항)

    # ---------------------------------------------------------
    # [C] PC 테스트용 (가짜 데이터)
    # ---------------------------------------------------------
    logger.warning("⚠️ 하드웨어가 감지되지 않아 가상 데이터를 사용합니다.")

    mock_image = "image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg"
    mock_moisture = random.randint(20, 60)
    mock_sebum = random.randint(40, 90)

    return mock_image, mock_moisture, mock_sebum


# ==========================================
# 4. API 엔드포인트 (Endpoints)
# ==========================================

# --- [General] ---
@app.get("/", tags=["General"])
def read_root():
    return FileResponse("index.html")


# --- [Mobile App] ---
@app.post("/analyze", tags=["Mobile App"])
async def analyze_skin_endpoint(
        user_id: str = Form(...),
        moisture: int = Form(...),
        sebum: int = Form(...),
        file: UploadFile = File(...)
):
    """
    [Step 1] 앱에서 사진과 유수분 값을 받아 분석을 수행합니다.
    """
    file_path = ""
    try:
        # 1. 파일 저장
        file_ext = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"📥 이미지 수신 완료: {user_id}")

        # 2. 분석 수행
        result = perform_skin_analysis(user_id, file_path, moisture, sebum)

        if not result:
            raise HTTPException(status_code=500, detail="AI Analysis Failed")

        return {
            "message": "Analysis successful",
            "analysis_id": result["analysis_id"],
            "gpt_result": result["gpt_result"]
        }

    except Exception as e:
        logger.error(f"Analyze Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # 3. 임시 파일 정리 (성공/실패 상관없이 실행)
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info("🗑️ 임시 파일 삭제 완료")
            except:
                pass


@app.post("/recommend", tags=["Mobile App"])
async def recommend_endpoint(req: RecommendRequest):
    """
    [Step 2] 분석 ID와 설문 데이터를 받아 제품을 추천합니다.
    """
    logger.info(f"📥 추천 요청: User {req.user_id}, ID {req.analysis_id}")

    try:
        # Pydantic v2 호환 (.model_dump)
        final_result = run_skin_advisor(
            user_id=req.user_id,
            analysis_id=req.analysis_id,
            lifestyle=req.lifestyle.model_dump(),
            user_pref=req.user_pref.model_dump()
        )

        if not final_result:
            raise HTTPException(status_code=404, detail="Data Not Found")

        return {
            "message": "Recommendation successful",
            "result": final_result
        }

    except Exception as e:
        logger.error(f"Recommend Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- [Admin] ---
@app.post("/update-products", tags=["Admin"])
async def update_products_endpoint(background_tasks: BackgroundTasks, secret_key: str = Form(...)):
    """
    [Admin] 백그라운드에서 제품 데이터 크롤링 및 DB 갱신
    """
    if secret_key != "admin1234":
        raise HTTPException(status_code=401, detail="Unauthorized")

    background_tasks.add_task(run_data_collection)
    return {"message": "Update started in background", "status": "processing"}


# ==========================================
# 5. 서버 실행 진입점 (Main)
# ==========================================
if __name__ == "__main__":
    import uvicorn

    # reload=True는 코드 수정 시 서버 자동 재시작 기능 (개발용)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)