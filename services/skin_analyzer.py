# skin_analyzer.py
"""
[Service Layer] Skin Analysis Logic
1. 하드웨어 센서 (수분/유분) - HW팀 로직(Skin.py) 통합
2. 카메라 촬영 (Picamera2) - 보내주신 코드 통합
3. GPT Vision API (피부 상세 분석)
"""

import logging
import uuid
import shutil
import os
import time
from typing import Optional
from fastapi import UploadFile, HTTPException

# 1. DB 저장 (Repository)
from core.utils import save_analysis_log_db

# 2. GPT 분석 (External API)
from .gpt_api import analyze_skin_image

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 하드웨어 센서 제어 (수분/유분) - HW팀 로직 적용
# ==============================================================================

def read_hardware_sensors():
    """
    [환경 자동 감지]
    Skin.py 로직을 적용: 5초 평균 측정 -> 캘리브레이션 값 반환
    """
    try:
        import spidev
        # RPi.GPIO는 설치 확인용
        import RPi.GPIO as GPIO

        # --- [HW팀 설정 상수] ---
        WATER_MIN, WATER_MAX = 0, 300
        OIL_MIN, OIL_MAX = 300, 1200

        MEASUREMENT_DURATION = 5  # 5초 측정
        SAMPLING_INTERVAL = 0.1

        # SPI 초기화
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 1350000

        def read_adc(channel):
            command = [1, (8 + channel) << 4, 0]
            r = spi.xfer2(command)
            return ((r[1] & 3) << 8) + r[2]

        def map_value(value, min_val, max_val):
            value = max(min_val, min(value, max_val))
            return (value - min_val) / (max_val - min_val) * 100

        # 측정 시작
        water_readings = []
        oil_readings = []
        start_time = time.time()

        logger.info(f"💧 센서 측정 시작 ({MEASUREMENT_DURATION}초)...")

        while (time.time() - start_time) < MEASUREMENT_DURATION:
            water_readings.append(read_adc(0))
            oil_readings.append(read_adc(1))
            time.sleep(SAMPLING_INTERVAL)

        spi.close()

        real_moisture = 0
        real_sebum = 0

        if len(water_readings) > 0:
            avg_water = sum(water_readings) / len(water_readings)
            avg_oil = sum(oil_readings) / len(oil_readings)
            real_moisture = map_value(avg_water, WATER_MIN, WATER_MAX)
            real_sebum = map_value(avg_oil, OIL_MIN, OIL_MAX)

        logger.info(f"측정 완료 - 수분: {real_moisture:.1f}%, 유분: {real_sebum:.1f}%")
        return {"moisture": int(real_moisture), "sebum": int(real_sebum)}

    except ImportError:
        logger.warning("spidev 없음: PC 테스트 모드")
        # 테스트용 임시 값
        return {"moisture": 50, "sebum": 50}
    except Exception as e:
        logger.error(f"센서 오류: {e}")
        try:
            if 'spi' in locals(): spi.close()
        except:
            pass
        raise Exception(f"센서 측정 실패: {str(e)}")


# ==============================================================================
# 2. 카메라 제어 (Picamera2) - 보내주신 코드 통합
# ==============================================================================

# 1. 현재 파일(skin_analyzer.py)의 위치를 구함 -> .../SkinProject/services
CURRENT_FILE_PATH = os.path.abspath(__file__)
SERVICES_DIR = os.path.dirname(CURRENT_FILE_PATH)

# 2. 그 상위 폴더(프로젝트 루트)를 구함 -> .../SkinProject
ROOT_DIR = os.path.dirname(SERVICES_DIR)

# 3. 루트 경로와 폴더명을 합침 -> .../SkinProject/temp_uploads (무조건 여기로 고정됨)
DEFAULT_SAVE_DIR = os.path.join(ROOT_DIR, "temp_uploads")

def capture_image_from_camera(save_dir="temp_uploads"):
    """
    [Picamera2 제어]
    라즈베리파이 카메라로 사진을 찍어 저장 경로를 반환합니다.
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # 파일명 랜덤 생성 (중복 방지)
    filename = f"cam_{uuid.uuid4()}.jpg"
    filepath = os.path.join(save_dir, filename)

    picam2 = None  # 변수 초기화

    try:
        from picamera2 import Picamera2

        logger.info("📸 [Pi] Picamera2로 촬영을 시도합니다...")
        picam2 = Picamera2()  # 카메라 연결

        config = picam2.create_still_configuration(main={"size": (640, 480)})
        picam2.configure(config)

        picam2.start()
        time.sleep(2)  # 안정화
        picam2.capture_file(filepath)
        picam2.stop()

        logger.info(f"✅ [Pi] 촬영 완료: {filepath}")
        return filepath

    except ImportError:
        logger.warning("⚠️ Picamera2 모듈 없음. PC 환경으로 간주합니다.")
    except Exception as e:
        logger.error(f"❌ Picamera2 에러: {e}")
        # 여기서 에러가 나도 아래 finally에서 닫아줍니다.
    finally:
        # [핵심 수정] 카메라가 켜져 있다면 무조건 닫아서 자원을 반환함
        if picam2 is not None:
            try:
                picam2.close()
                logger.info("🔒 카메라 자원 해제 완료")
            except Exception as e:
                logger.warning(f"카메라 닫기 실패(이미 닫힘 등): {e}")


# ==============================================================================
# 3. 통합 분석 프로세스 (Main Process)
# ==============================================================================

async def process_skin_analysis(
        user_id: str,
        file: Optional[UploadFile] = None,
        moisture: int = None,
        sebum: int = None
):
    """
    [분석 총괄 함수]
    1. 센서값 읽기 (없으면 에러)
    2. 이미지 확보 (업로드 파일 or 카메라 촬영)
    3. GPT API 호출
    4. DB 저장
    """

    # -------------------------------------------------------
    # [Step 1] 센서 데이터 확보 (수분/유분)
    # -------------------------------------------------------
    sensor_source = "app_input"

    if moisture is None or sebum is None:
        try:
            # HW 센서값 읽기 (5초 소요)
            sensor_data = read_hardware_sensors()
            if moisture is None: moisture = sensor_data["moisture"]
            if sebum is None: sebum = sensor_data["sebum"]
            sensor_source = "hardware_sensor"
        except Exception as e:
            # PC 테스트나 센서 고장 시에도 진행하고 싶다면 여기서 임의값을 넣거나 에러 처리
            error_msg = f"센서 데이터 누락 ({str(e)})"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

    # -------------------------------------------------------
    # [Step 2] 이미지 파일 확보
    # -------------------------------------------------------
    file_path = ""

    # A. 앱에서 파일 업로드 됨
    if file is not None:
        filename = f"{uuid.uuid4()}.jpg"
        file_path = f"temp_uploads/{filename}"
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail="이미지 파일 저장 실패")

    # B. 파일 없음 -> 카메라 촬영 시도
    else:
        logger.info("업로드된 파일 없음 -> 카메라 촬영 시도")
        try:
            # Picamera2 촬영 (3초 소요)
            file_path = capture_image_from_camera()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"카메라 촬영 실패: {str(e)}")

    # -------------------------------------------------------
    # [Step 3] AI 피부 분석 (GPT Vision API)
    # -------------------------------------------------------
    logger.info(f"🤖 GPT 분석 요청 시작: {file_path}")

    gpt_result = analyze_skin_image(file_path)

    if not gpt_result:
        raise HTTPException(status_code=502, detail="AI 분석 서버 응답 없음")

    # -------------------------------------------------------
    # [Step 4] 결과 통합 및 DB 저장
    # -------------------------------------------------------
    scores = {
        "moisture": moisture,
        "sebum": sebum,
        "acne": gpt_result.get("acne", 0),
        "wrinkles": gpt_result.get("wrinkles", 0),
        "pores": gpt_result.get("pores", 0),
        "redness": gpt_result.get("redness", 0),
        "pigmentation": gpt_result.get("pigmentation", 0)
    }

    negative_sum = (
            scores["acne"] + scores["wrinkles"] + scores["pores"] +
            scores["redness"] + scores["pigmentation"]
    )
    total_score = max(0, 100 - int(negative_sum / 5))

    # DB 저장
    new_id = save_analysis_log_db(user_id, file_path, scores, total_score)

    if not new_id:
        raise HTTPException(status_code=500, detail="데이터베이스 저장 실패")

    return {
        "analysis_id": new_id,
        "message": "분석 완료",
        "source": f"{sensor_source} + Camera + GPT",
        "total_score": total_score,
        "scores": scores
    }