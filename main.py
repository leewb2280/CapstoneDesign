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
from typing import Optional

# [수정 1] StaticFiles 임포트 추가
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 사용자 정의 모듈 임포트
from services.skin_analyzer import perform_skin_analysis
from services.skin_advisor import run_skin_advisor
from services.data_collector import run_data_collection
from core.utils import (
    register_user_db, authenticate_user_db, get_user_history_db,
    create_user_table, check_user_exists_db,
    save_user_profile_db, get_user_profile_db,
    search_skin_history_db
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 이미지 저장 경로 설정
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ==========================================
# 1. FastAPI 앱 초기화 및 설정
# ==========================================
create_user_table()

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [수정 2] 정적 파일 마운트 (이미지 접근 허용)
# 브라우저가 "/uploads"로 요청하면 실제 서버의 "temp_uploads" 폴더를 보여줌
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


# ==========================================
# 2. 웹(Web)용 데이터 모델 (DTO)
# ==========================================
class LifestyleData(BaseModel):
    sleep_hours_7d: float
    water_intake_ml: int
    wash_freq_per_day: int
    wash_temp: str = "warm"
    sensitivity: str


class UserPref(BaseModel):
    age: int
    pref_texture: str

class RecommendRequest(BaseModel):
    user_id: str
    analysis_id: int
    lifestyle: LifestyleData
    user_pref: UserPref

# 1. 데이터 모델 수정 (합치기)
class UserProfileRequest(BaseModel):
    user_id: str
    age: int
    sleep_hours_7d: float
    water_intake_ml: int
    wash_freq_per_day: int
    sensitivity: str
    pref_texture: str



class AuthRequest(BaseModel):
    user_id: str
    password: str
    name: str = None


# ==========================================
# 2. 안드로이드용 데이터 모델 (DTO)
# ==========================================
class AndroidAuthRequest(BaseModel):
    email: str      # 앱에서는 user_id 대신 email이라는 이름으로 보냄
    password: str

# ==========================================
# 3. 하드웨어 제어 로직 (Hardware Control)
# ==========================================
try:
    import spidev
    import RPi.GPIO as GPIO
    IS_RASPBERRY_PI = True
except ImportError:
    print("⚠️ 라즈베리파이가 아닙니다. 가상 모드(Mock)로 동작합니다.")
    IS_RASPBERRY_PI = False
    spidev = None


def hardware_capture():
    logger.info("📡 하드웨어 데이터 수집 시작...")

    if IS_RASPBERRY_PI:
        try:
            real_img_path = os.path.join(UPLOAD_DIR, "capture.jpg")
            os.system(f"libcamera-still -o {real_img_path} --width 640 --height 640 -t 1 --nopreview")

            if not os.path.exists(real_img_path):
                raise Exception("사진 촬영 실패")

            adc = spidev.SpiDev()
            adc.open(0, 0)
            adc.max_speed_hz = 1350000

            def read_adc(channel):
                r = adc.xfer2([1, (8 + channel) << 4, 0])
                data = ((r[1] & 3) << 8) + r[2]
                return data

            # 채널 0이 수분, 채널 1이 유분이라고 가정
            raw_moisture = read_adc(0)
            raw_sebum = read_adc(1)

            # 0~1023 값을 0~100 점수로 환산 (단순 예시)
            real_moisture = int((raw_moisture / 1023) * 100)
            real_sebum = int((raw_sebum / 1023) * 100)
            logger.info(f"📸 촬영 완료: {real_img_path}, 센서: 수분{real_moisture}/유분{real_sebum}")

            return real_img_path, real_moisture, real_sebum

        except Exception as e:
            logger.error(f"하드웨어 오류: {e}")

    logger.warning("⚠️ 하드웨어가 감지되지 않아 가상 데이터를 사용합니다.")
    # [수정 권장] 테스트 이미지가 실제 경로에 있는지 확인 필요
    mock_image = "image-data/test/images/acne-5_jpeg.rf.2d6671715f0149df7b494c4d3f12a98b.jpg"
    mock_moisture = random.randint(20, 60)
    mock_sebum = random.randint(40, 90)

    return mock_image, mock_moisture, mock_sebum


# ==========================================
# 안드로이드 앱용 API 엔드포인트
# ==========================================

# 1. 회원가입 (앱 경로: POST /auth/signup)
@app.post("/auth/signup", tags=["Android"])
async def signup_android(req: AndroidAuthRequest):
    # 앱은 email을 보내지만, DB에는 user_id로 저장
    user_id = req.email
    password = req.password

    if not user_id or not password:
        return {"success": False, "message": "이메일과 비밀번호를 입력하세요.", "token": None}

    success = register_user_db(user_id, password, "User")  # 이름은 임시로 User

    if not success:
        # 앱의 AuthResponse 형식에 맞춰서 리턴
        return {"success": False, "message": "이미 존재하는 계정입니다.", "token": None}

    return {"success": True, "message": "회원가입 성공!", "token": "dummy_token_123"}


# 2. 로그인 (앱 경로: POST /auth/login)
@app.post("/auth/login", tags=["Android"])
async def login_android(req: AndroidAuthRequest):
    user_id = req.email
    password = req.password

    user = authenticate_user_db(user_id, password)

    if not user:
        return {"success": False, "message": "아이디 또는 비밀번호 오류", "token": None}

    # 로그인 성공 시 앱이 원하는 포맷 (success, message, token)
    return {
        "success": True,
        "message": f"환영합니다, {user['name']}님!",
        "token": f"token_for_{user_id}"  # 임시 토큰 발행
    }


# 3. 홈 화면 - 피부 기록 (앱 경로: GET /skin/history)
# 앱에서는 Header에 토큰을 넣어 보내지만, 여기선 간단히 테스트용 더미 데이터 반환
@app.get("/skin/history", tags=["Android"])
async def history_android():
    # 실제로는 토큰을 해석해서 user_id를 찾아야 하지만,
    # 일단 연결 테스트를 위해 최근 데이터를 임의로 보냅니다.
    # 앱의 SkinResult 데이터 클래스 구조와 맞춰야 함 (여기선 예시)
    return [
        {
            "date": "2025-11-26",
            "score": 85,
            "comment": "수분 상태가 좋습니다."
        }
    ]


# ==========================================
# 4. 웹(Web)용 API 엔드포인트
# ==========================================

@app.get("/", tags=["General"])
def read_root():
    return FileResponse("static/index.html")

@app.get("/user/profile/{user_id}", tags=["User"])
async def get_profile_endpoint(user_id: str):
    profile = get_user_profile_db(user_id)
    if not profile:
        return {} # 없으면 빈 객체 반환 (프론트에서 기본값 사용)
    return profile

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
    if not check_user_exists_db(user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다. 먼저 회원가입을 해주세요.")

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
            "total_score": result["total_score"],
            "gpt_result": result["gpt_result"]
        }

    except Exception as e:
        logger.error(f"Analyze Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-hardware", tags=["Kiosk"])
async def analyze_hardware_endpoint(user_id: str = Form(...)):
    logger.info(f"📸 하드웨어 촬영 및 분석 요청: {user_id}")
    try:
        img_path, moist, seb = hardware_capture()
        result = perform_skin_analysis(user_id, img_path, moist, seb)

        if not result:
            raise HTTPException(status_code=500, detail="AI Analysis Failed")

        return {
            "message": "Hardware Analysis successful",
            "analysis_id": result["analysis_id"],
            "total_score": result["total_score"],
            "gpt_result": result["gpt_result"],
            "sensor_data": {"moisture": moist, "sebum": seb}
        }
    except Exception as e:
        logger.error(f"Hardware Analyze Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# [수정] 추천 요청 엔드포인트 (데이터 수신 -> DB 업데이트 -> 분석)
@app.post("/recommend", tags=["Mobile App"])
async def recommend_endpoint(req: RecommendRequest):
    logger.info(f"📥 추천 요청 및 프로필 업데이트: User {req.user_id}")

    if not check_user_exists_db(req.user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")

    try:
        # 1. 입력받은 최신 정보를 DB에 저장 (Upsert)
        # Lifestyle과 UserPref를 합쳐서 DB 저장 포맷으로 변환
        profile_data = {
            "age": req.user_pref.age,
            "pref_texture": req.user_pref.pref_texture,
            "sleep_hours_7d": req.lifestyle.sleep_hours_7d,
            "water_intake_ml": req.lifestyle.water_intake_ml,
            "wash_freq_per_day": req.lifestyle.wash_freq_per_day,
            "sensitivity": req.lifestyle.sensitivity,
            "wash_temp": req.lifestyle.wash_temp
        }
        save_user_profile_db(req.user_id, profile_data)

        # 2. 분석 엔진 실행 (방금 받은 데이터를 인자로 넘김)
        final_result = run_skin_advisor(
            user_id=req.user_id,
            analysis_id=req.analysis_id,
            lifestyle=req.lifestyle.model_dump(),
            user_pref=req.user_pref.model_dump()
        )

        if not final_result:
            raise HTTPException(status_code=404, detail="Analysis Failed")

        return {"message": "Recommendation successful", "result": final_result}

    except Exception as e:
        logger.error(f"Recommend Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update-products", tags=["Admin"])
async def update_products_endpoint(background_tasks: BackgroundTasks, secret_key: str = Form(...)):
    if secret_key != "admin1234":
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(run_data_collection)
    return {"message": "Update started in background", "status": "processing"}


@app.post("/signup", tags=["Auth"])
async def signup_endpoint(req: AuthRequest):
    if not req.user_id or not req.password:
        raise HTTPException(status_code=400, detail="ID와 비밀번호를 입력하세요.")
    success = register_user_db(req.user_id, req.password, req.name)
    if not success:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    return {"message": "회원가입 성공!", "user_id": req.user_id}


@app.post("/login", tags=["Auth"])
async def login_endpoint(req: AuthRequest):
    user = authenticate_user_db(req.user_id, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 틀렸습니다.")
    return {"message": "로그인 성공", "user_info": user}


# [신규 엔드포인트] 사용자 정보 저장/수정 (설정 페이지용)
@app.post("/user/profile", tags=["User"])
async def update_profile_endpoint(req: UserProfileRequest):
    if not check_user_exists_db(req.user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")

    # DB 저장 함수 호출
    data = req.model_dump()
    success = save_user_profile_db(req.user_id, data)

    if success:
        return {"message": "프로필이 성공적으로 저장되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="DB 저장 실패")


@app.get("/history/search", tags=["History"])
async def search_history_endpoint(
    user_id: str,
    condition: Optional[str] = None,
    page: int = 1
):
    # 1. 회원 확인
    if not check_user_exists_db(user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")

    # 2. DB 조회 (utils.py의 함수 호출)
    result = search_skin_history_db(user_id, condition, page)

    return {
        "status": "success",
        "filter": condition if condition else "all",
        "data": result
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)