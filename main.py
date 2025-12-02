# main.py
"""
[AI Skin Advisor API Server]
FastAPI 기반의 메인 서버 구동 파일입니다.
웹(Web)과 앱(Android) 모두 이 API를 공통으로 사용합니다.
"""

import os
import logging
from typing import Optional

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body, BackgroundTasks
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------
# [Services Import]
# 핵심 로직은 services 폴더의 모듈에서 가져옵니다.
# ---------------------------------------------------------
from services.config import *
from core.utils import (
    init_db,
    register_user_db,
    authenticate_user_db,
    check_user_exists_db,
    save_user_profile_db,
    get_user_profile_db,
    search_skin_history_db,
    get_skin_period_stats_db
)
from services.skin_analyzer import process_skin_analysis
from services.skin_advisor import run_skin_advisor
from services.data_collector import run_data_collection

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 이미지 저장 경로 설정
# 1. 현재 main.py가 있는 폴더 위치를 구합니다.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 2. 그 위치를 기준으로 폴더 경로를 만듭니다.
UPLOAD_DIR = os.path.join(BASE_DIR, "temp_uploads")

# 3. 폴더가 없으면 생성합니다.
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---------------------------------------------------------
# [Lifespan 설정] 시작과 종료를 관리하는 함수
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # [시작 시 실행]
    print("🔄 서버 시작: DB 테이블을 점검하고 생성합니다...")
    init_db()  # 여기서 DB 초기화 실행
    print("✅ 서버 시작 완료: DB 초기화 끝")

    yield  # 👈 이 yield를 기준으로 위는 '시작', 아래는 '종료' 로직입니다.

    # [종료 시 실행]
    print("👋 서버 종료: 리소스를 정리합니다.")
    # (나중에 DB 연결 종료나 임시 파일 삭제 등이 필요하면 여기에 작성)


# ---------------------------------------------------------
# [App 생성] lifespan 파라미터 적용
# ---------------------------------------------------------
app = FastAPI(
    title="AI Skin Advisor API",
    description="피부 분석 및 맞춤형 화장품 추천 시스템",
    version="2.0.0",
    lifespan=lifespan
)

# ---------------------------------------------------------
# [Middleware & Mounts]
# ---------------------------------------------------------

# 1. CORS 설정 (앱/웹 통신 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 보안상 실서비스에선 특정 도메인만 허용 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 정적 파일 경로 설정 (이미지 저장소, 웹 페이지)
os.makedirs("temp_uploads", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/temp_uploads", StaticFiles(directory=UPLOAD_DIR), name="temp_uploads")


# ---------------------------------------------------------
# [Pydantic Models] 요청 데이터 검증용 모델
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    user_id: str
    password: str
    name: str = "User"


class SignupRequest(BaseModel):
    user_id: str
    password: str
    name: str


class RecommendationRequest(BaseModel):
    user_id: str
    analysis_id: int
    lifestyle: dict  # {sleep_hours_7d, water_intake_ml, ...}
    user_pref: dict  # {age, pref_texture}


# ==============================================================================
# 1. Web Page Hosting (프론트엔드)
# ==============================================================================

@app.get("/")
async def read_index():
    """웹 대시보드 메인 페이지(HTML)를 반환합니다."""
    return FileResponse("static/index.html")


# ==============================================================================
# 2. Authentication (회원가입/로그인)
# ==============================================================================

@app.post("/signup", tags=["Auth"])
async def signup(req: SignupRequest):
    if register_user_db(req.user_id, req.password, req.name):
        return {
            "success": True,
            "message": "회원가입 성공",
            "token": "test_token"
        }
    else:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")


@app.post("/login", tags=["Auth"])
async def login(req: LoginRequest):
    user_info = authenticate_user_db(req.user_id, req.password)
    if user_info:
        return {
            "success": True,
            "message":"로그인 성공",
            "token":"test_token",
            "user_info": user_info
        }
    else:
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 틀렸습니다.")


# ==============================================================================
# 3. User Profile (사용자 정보)
# ==============================================================================

@app.get("/user/profile/{user_id}", tags=["User"])
async def get_profile(user_id: str):
    """사용자의 상세 프로필(나이, 수면시간 등) 조회"""
    data = get_user_profile_db(user_id)
    return data if data else {}


@app.post("/user/profile", tags=["User"])
async def save_profile(user_id: str = Body(...), profile_data: dict = Body(...)):
    """(앱/웹 공용) 사용자 프로필 저장 및 업데이트"""
    success = save_user_profile_db(user_id, profile_data)
    if not success:
        raise HTTPException(status_code=500, detail="프로필 저장 실패")
    return {"status": "success", "message": "프로필 업데이트 완료"}


# ==============================================================================
# 4. Analysis (피부 측정 및 분석)
# ==============================================================================

@app.post("/analyze", tags=["Analysis"])
async def analyze_skin_endpoint(
    user_id: str = Form(...),
    moisture: Optional[int] = Form(None),
    sebum: Optional[int] = Form(None),
    file: UploadFile = File(...)
):
    """
    [통합 분석 API]
    복잡한 로직은 모두 skin_analyzer로 위임하고, 여기서는 호출만 담당합니다.
    """
    try:
        result = await process_skin_analysis(user_id, file, moisture, sebum)
        return result

    except Exception as e:
        logger.error(f"분석 요청 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# 5. Recommendation (솔루션 처방)
# ==============================================================================

@app.post("/recommend", tags=["Recommendation"])
async def recommend_endpoint(req: RecommendationRequest):
    """
    [Step 2] 최종 솔루션 요청
    - 분석된 피부 데이터 + 사용자 설문(lifestyle)을 종합하여 제품 및 루틴 추천
    """
    try:
        # skin_advisor.py의 메인 로직 실행
        result = run_skin_advisor(
            user_id=req.user_id,
            analysis_id=req.analysis_id,
            lifestyle=req.lifestyle,
            user_pref=req.user_pref
        )

        # [중요] 프로필 정보도 같이 업데이트 (설문 내용 반영)
        profile_update = req.lifestyle.copy()
        profile_update.update(req.user_pref)
        save_user_profile_db(req.user_id, profile_update)

        return result

    except Exception as e:
        logger.error(f"추천 로직 에러: {e}")
        raise HTTPException(status_code=500, detail=f"추천 생성 중 오류: {e}")


# ==============================================================================
# 6. History & Statistics (기록 및 통계)
# ==============================================================================

@app.get("/history/search", tags=["History"])
async def search_history_endpoint(
        user_id: str,
        condition: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        page: int = 1
):
    """
    [통합 히스토리 검색 API]
    - 앱과 웹에서 공통으로 사용합니다.
    - 필터(condition), 기간(date), 페이징(page)을 모두 지원합니다.
    """
    if not check_user_exists_db(user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")

    result = search_skin_history_db(
        user_id=user_id,
        condition=condition,
        start_date=start_date,
        end_date=end_date,
        page=page
    )

    return {
        "status": "success",
        "filter": condition if condition else "all",
        "period": {"start": start_date, "end": end_date},
        "data": result
    }


@app.get("/history/stats", tags=["History"])
async def get_stats_endpoint(user_id: str, start_date: str, end_date: str):
    """
    [통합 통계 API]
    - 특정 기간의 피부 변화 추이(평균 점수 등)를 반환합니다.
    """
    if not check_user_exists_db(user_id):
        raise HTTPException(status_code=401, detail="존재하지 않는 회원입니다.")

    stats = get_skin_period_stats_db(user_id, start_date, end_date)

    if not stats:
        return {"status": "empty", "message": "데이터 없음", "data": {}}

    return {
        "status": "success",
        "period": f"{start_date} ~ {end_date}",
        "data": stats
    }


# ==============================================================================
# 7. 제품 업데이트 기능
# ==============================================================================

@app.post("/products/update", tags=["Products"])
async def update_products_endpoint(background_tasks: BackgroundTasks):
    """
    [제품 정보 업데이트]
    크롤링 또는 데이터 갱신 작업을 백그라운드에서 실행합니다.
    (일반 사용자도 요청 가능하도록 권한 해제됨)
    """
    # 백그라운드에서 크롤링/업데이트 실행 (오래 걸리므로)
    background_tasks.add_task(run_data_collection)

    return {"status": "success", "message": "제품 정보 업데이트가 시작되었습니다. (잠시 후 반영됩니다)"}


# ==============================================================================
# 8. 웹 사이트 연결 (정적 파일 서빙)
# ==============================================================================

if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
else:
    print("⚠️ 'static' 폴더가 없습니다. 웹 대시보드를 보려면 폴더를 생성하고 파일을 넣으세요.")


# ==============================================================================
# 9. 메인 실행부 (서버 + UI 동시 실행)
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    import subprocess
    import sys
    import time

    # 1. UI(화면)를 별도 프로세스로 실행합니다.
    ui_path = os.path.join("services", "ui.py")

    print("🖥️ GUI 화면을 시작합니다...")
    ui_process = subprocess.Popen([sys.executable, ui_path])

    # 2. 서버가 켜질 때까지 잠시 대기
    time.sleep(2)

    try:
        # 3. 서버 실행
        print("🚀 API 서버를 시작합니다...")
        uvicorn.run(app, host="0.0.0.0", port=8000)

    except KeyboardInterrupt:
        print("종료 요청 받음.")

    finally:
        # 4. 서버가 꺼지면 UI도 같이 꺼줌
        if ui_process.poll() is None:  # 아직 켜져 있다면
            ui_process.terminate()
            print("✅ GUI 화면도 종료되었습니다.")