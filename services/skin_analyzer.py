# skin_analyzer.py
"""
[Service Layer] Skin Analysis Logic
- 하드웨어 센서 (수분/유분)
- GPT Vision API (피부 상세 분석)
"""

import logging
import uuid
import shutil
from fastapi import UploadFile, HTTPException

# 1. DB 저장 (Repository)
from core.utils import save_analysis_log_db

# 2. GPT 분석 (External API)
from .gpt_api import analyze_skin_image

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==============================================================================
# 1. 하드웨어 센서 제어 (Hardware Control)
# ==============================================================================

def read_hardware_sensors():
    """
    [환경 자동 감지]
    라즈베리파이 센서 라이브러리가 있으면 값을 읽어옵니다.
    """
    try:
        import spidev
        import RPi.GPIO as GPIO

        # 1. 카메라 촬영 (옵션) - skin_analyzer는 이미지 파일 자체를 인자로 받으므로
        # 센서값만 읽는 것이 목적이라면 카메라는 제외해도 됩니다.

        # 2. 센서값 읽기
        adc = spidev.SpiDev()
        adc.open(0, 0)
        adc.max_speed_hz = 1350000

        def read_adc(channel):
            r = adc.xfer2([1, (8 + channel) << 4, 0])
            data = ((r[1] & 3) << 8) + r[2]
            return data

        raw_moisture = read_adc(0)
        raw_sebum = read_adc(1)

        # 변환 로직
        real_moisture = int((raw_moisture / 1023) * 100)
        real_sebum = int((raw_sebum / 1023) * 100)

        return {"moisture": real_moisture, "sebum": real_sebum}

    except ImportError:
        # PC 환경이거나 라이브러리가 없는 경우
        raise Exception("하드웨어 센서를 찾을 수 없습니다. (PC에서는 수분/유분 값을 직접 입력해주세요.)")

    except Exception as e:
        logger.error(f"센서 하드웨어 오류: {e}")
        raise Exception(f"센서 측정 중 오류 발생: {str(e)}")


# ==============================================================================
# 2. 통합 분석 프로세스 (Main Process)
# ==============================================================================

async def process_skin_analysis(user_id: str, file: UploadFile, moisture: int = None, sebum: int = None):
    """
    [분석 총괄 함수]
    1. 센서값 읽기 (없으면 에러)
    2. 이미지 저장
    3. GPT API 호출 (실패하면 에러)
    4. 결과 통합 및 DB 저장
    """

    # -------------------------------------------------------
    # [Step 1] 센서 데이터 확보 (수분/유분)
    # -------------------------------------------------------
    sensor_source = "app_input"

    # 앱(웹)에서 값을 안 보냈다면(None), 하드웨어 센서를 직접 읽어야 함
    if moisture is None or sebum is None:
        try:
            sensor_data = read_hardware_sensors()

            # 센서에서 읽어온 값 적용
            if moisture is None: moisture = sensor_data["moisture"]
            if sebum is None: sebum = sensor_data["sebum"]
            sensor_source = "hardware_sensor"

        except Exception as e:
            # 센서도 없고 입력도 없으면 -> 분석 불가(에러 처리)
            error_msg = f"수분/유분 데이터가 누락되었습니다. ({str(e)})"
            logger.error(error_msg)
            raise HTTPException(status_code=400, detail=error_msg)

    # -------------------------------------------------------
    # [Step 2] 이미지 파일 저장
    # -------------------------------------------------------
    filename = f"{uuid.uuid4()}.jpg"
    file_path = f"temp_uploads/{filename}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"파일 저장 실패: {e}")
        raise HTTPException(status_code=500, detail="이미지 파일 저장 실패")

    # -------------------------------------------------------
    # [Step 3] AI 피부 분석 (GPT Vision API)
    # -------------------------------------------------------

    logger.info(f"🤖 GPT 분석 요청 시작: {file_path}")

    # 실제 GPT API 호출
    gpt_result = analyze_skin_image(file_path)

    if not gpt_result:
        # GPT 분석 실패 시 -> 분석 불가(에러 처리)
        logger.error("GPT API 응답 실패")
        raise HTTPException(status_code=502, detail="AI 분석 서버(GPT) 응답이 없습니다. 잠시 후 다시 시도해주세요.")

    logger.info(f"✅ GPT 분석 완료: {gpt_result}")

    # -------------------------------------------------------
    # [Step 4] 데이터 통합
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

    # 종합 점수 계산
    negative_sum = (
        scores["acne"] + scores["wrinkles"] + scores["pores"] +
        scores["redness"] + scores["pigmentation"]
    )
    total_score = max(0, 100 - int(negative_sum / 5))

    # -------------------------------------------------------
    # [Step 5] DB 저장
    # -------------------------------------------------------
    new_id = save_analysis_log_db(user_id, file_path, scores)

    if not new_id:
        raise HTTPException(status_code=500, detail="데이터베이스 저장 실패")

    return {
        "analysis_id": new_id,
        "message": "분석 완료",
        "source": f"{sensor_source} + GPT_Vision",
        "total_score": total_score,
        "scores": scores
    }