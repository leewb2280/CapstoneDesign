# main.py
"""
[AI Skin Advisor API Server]
FastAPI 기반의 메인 서버 구동 파일입니다.
웹(Web)과 앱(Android) 모두 이 API를 공통으로 사용합니다.
"""

import os
import logging
from typing import Optional

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
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# FastAPI 앱 초기화
app = FastAPI(
    title="AI Skin Advisor API",
    description="피부 분석 및 맞춤형 화장품 추천 시스템",
    version="2.0.0"  # 통합 버전 업데이트
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
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


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
        return {"message": "회원가입 성공"}
    else:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")


@app.post("/login", tags=["Auth"])
async def login(req: LoginRequest):
    user_info = authenticate_user_db(req.user_id, req.password)
    if user_info:
        return {"message": "로그인 성공", "user_info": user_info}
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
        # 한 줄로 끝!
        result = await process_skin_analysis(user_id, file, moisture, sebum)
        return result

    except Exception as e:
        logger.error(f"분석 요청 처리 중 오류: {e}")
        # 에러 메시지를 예쁘게 포장해서 반환
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
# 6. History & Statistics (기록 및 통계) - [앱/웹 통합 핵심]
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
# 7. Admin (관리자 기능)
# ==============================================================================

@app.post("/update-products", tags=["Admin"])
async def update_products_endpoint(background_tasks: BackgroundTasks, secret_key: str = Form(...)):
    if secret_key != "admin1234":
        raise HTTPException(status_code=401, detail="Unauthorized")
    background_tasks.add_task(run_data_collection)
    return {"message": "Update started in background", "status": "processing"}


# 서버 실행 (직접 실행 시)
if __name__ == "__main__":
    import uvicorn

    # 모든 IP 접속 허용 (0.0.0.0)
    uvicorn.run(app, host="0.0.0.0", port=8000)