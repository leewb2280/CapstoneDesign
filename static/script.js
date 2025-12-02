const BASE_URL = "";
let currentDate = new Date();
let historyMap = {};

// 1. 초기 실행 (로그인 체크)
window.onload = function() {
    const token = localStorage.getItem("token");
    const userId = localStorage.getItem("userId");

    if (token && userId) {
        document.getElementById("loginOverlay").style.display = "none";
        document.getElementById("displayUserId").innerText = userId;
        fetchMonthlyData();
    } else {
        document.getElementById("loginOverlay").style.display = "flex";
    }
};

// --- [기능 1] 화면 전환 (사이드바 메뉴) ---
function switchView(viewName) {
    // 1. 모든 메뉴 활성화 상태 끄기
    document.querySelectorAll('.menu-item').forEach(el => el.classList.remove('active'));
    // 2. 클릭한 메뉴 활성화
    const activeMenu = document.getElementById(`menu-${viewName}`);
    if(activeMenu) activeMenu.classList.add('active');

    // 3. 모든 화면 숨기기
    document.querySelectorAll('.view-section').forEach(el => el.style.display = 'none');
    // 4. 선택한 화면 보여주기
    const activeView = document.getElementById(`view-${viewName}`);
    if(activeView) activeView.style.display = 'block';

    // 5. 설정 탭으로 갈 때 데이터 로드
    if (viewName === 'settings') {
        loadSettings();
    }
}

// --- [기능 2] 로그인 & 회원가입 ---
function handleEnter(e) {
    if (e.key === "Enter") performLogin();
}

async function performLogin() {
    const id = document.getElementById("inputId").value;
    const pw = document.getElementById("inputPw").value;

    if (!id || !pw) { alert("아이디와 비밀번호를 입력해주세요."); return; }

    try {
        const res = await fetch(`${BASE_URL}/login`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: id, password: pw })
        });
        const data = await res.json();

        if (data.success) {
            localStorage.setItem("token", data.token);
            localStorage.setItem("userId", id);
            document.getElementById("displayUserId").innerText = id;
            document.getElementById("loginOverlay").style.display = "none";
            fetchMonthlyData();
        } else {
            alert("로그인 실패: " + data.message);
        }
    } catch (e) { console.error(e); alert("서버 연결 실패"); }
}

async function performSignup() {
    const id = document.getElementById("inputId").value;
    const pw = document.getElementById("inputPw").value;
    if (!id || !pw) { alert("가입할 정보를 입력하세요."); return; }

    if(confirm(`'${id}' 계정으로 가입합니까?`)) {
        try {
            const res = await fetch(`${BASE_URL}/signup`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: id, password: pw, name: "WebUser" })
            });
            const data = await res.json();
            if (data.success) alert("가입 성공! 로그인해주세요.");
            else alert("가입 실패: " + data.message);
        } catch (e) { alert("서버 오류"); }
    }
}

function logout() {
    localStorage.clear();
    location.reload();
}

// --- [기능 3] 달력 (히스토리) ---
function changeMonth(delta) {
    currentDate.setMonth(currentDate.getMonth() + delta);
    fetchMonthlyData();
}

async function fetchMonthlyData() {
    const userId = localStorage.getItem("userId");
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth() + 1;
    const startDate = `${year}-${String(month).padStart(2, '0')}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    const endDate = `${year}-${String(month).padStart(2, '0')}-${lastDay}`;

    try {
        const res = await fetch(`${BASE_URL}/history/search?user_id=${userId}&start_date=${startDate}&end_date=${endDate}&page=1&page_size=100`);
        const json = await res.json();

        historyMap = {};
        if (json.data && json.data.records) {
            json.data.records.forEach(record => {
                const dateKey = record.date.split(" ")[0];
                if (!historyMap[dateKey]) historyMap[dateKey] = record;
            });
        }
        renderCalendar();
    } catch (e) {
        console.error("로드 실패", e);
        renderCalendar();
    }
}

function renderCalendar() {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    document.getElementById("currentMonth").innerText = `${year}년 ${month + 1}월`;

    const firstDayIndex = new Date(year, month, 1).getDay();
    const lastDate = new Date(year, month + 1, 0).getDate();
    const grid = document.getElementById("calendarGrid");
    grid.innerHTML = "";

    for (let i = 0; i < firstDayIndex; i++) {
        const emptyDiv = document.createElement("div");
        emptyDiv.classList.add("day", "empty");
        grid.appendChild(emptyDiv);
    }

    for (let i = 1; i <= lastDate; i++) {
        const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
        const hasData = historyMap[dateStr] ? true : false;
        const dayDiv = document.createElement("div");
        dayDiv.classList.add("day");
        if (hasData) dayDiv.classList.add("has-data");

        dayDiv.innerHTML = `<span class="day-number">${i}</span><div class="dot"></div>`;
        dayDiv.onclick = () => {
            document.querySelectorAll('.day').forEach(d => d.classList.remove('selected'));
            dayDiv.classList.add('selected');
            showDetail(dateStr);
        };
        grid.appendChild(dayDiv);
    }
}

// [script.js] showDetail 함수 전체 교체

function showDetail(dateKey) {
    const contentDiv = document.getElementById("detailContent");
    const data = historyMap[dateKey];

    if (!data) {
        contentDiv.innerHTML = `<div class="no-data"><i class="fas fa-times-circle" style="font-size: 48px; margin-bottom: 10px; color: #ddd;"></i><p>${dateKey}<br>기록이 없습니다.</p></div>`;
        return;
    }

    const scoreColor = data.overall_score >= 80 ? '#4CAF50' : (data.overall_score >= 50 ? '#FF9800' : '#F44336');

    // 1. 기본 점수 정보 (기존 코드)
    let html = `
        <h3 style="margin-top:0; border-bottom:1px solid #eee; padding-bottom:10px;">📅 ${data.date}</h3>
        <div class="detail-card">
            <span style="font-size:14px; color:#666;">종합 피부 점수</span>
            <div style="font-size:48px; font-weight:bold; color:${scoreColor}; margin: 10px 0;">${data.overall_score}점</div>
            <span style="background:#eee; padding:5px 10px; border-radius:15px; font-size:12px;">피부 나이: ${data.skin_age}세</span>
        </div>
        <h4 style="margin-bottom:10px;">상세 분석</h4>
        <div class="score-grid">
            <div class="score-item"><span class="score-label">💧 수분</span><span class="score-value">${data.scores.moisture}%</span></div>
            <div class="score-item"><span class="score-label">✨ 유분</span><span class="score-value">${data.scores.sebum}%</span></div>
            <div class="score-item"><span class="score-label">🚨 여드름</span><span class="score-value">${data.scores.acne}</span></div>
            <div class="score-item"><span class="score-label">🧬 주름</span><span class="score-value">${data.scores.wrinkles}</span></div>
            <div class="score-item"><span class="score-label">👃 모공</span><span class="score-value">${data.scores.pore}</span></div>
            <div class="score-item"><span class="score-label">😡 홍조</span><span class="score-value">${data.scores.redness}</span></div>
            <div class="score-item"><span class="score-label">색소침착</span><span class="score-value">${data.scores.pigmentation}</span></div>
        </div>
    `;

    // 2. 과거 추천 제품 & 루틴 정보
    // (데이터가 있을 때만 표시)
    if (data.products && data.products.length > 0) {
        html += `<h4 style="margin-top:30px; margin-bottom:10px;">🧴 당시 추천 제품</h4>
                 <div class="product-list">`;

        data.products.forEach(p => {
            html += `
            <div class="product-card" style="margin-bottom:10px;">
                <div class="product-brand">${p.brand}</div>
                <div class="product-name" style="font-size:14px;">${p.name}</div>
            </div>`;
        });
        html += `</div>`;
    }

    if (data.routine && (data.routine.am || data.routine.pm)) {
        html += `<h4 style="margin-top:20px; margin-bottom:10px;">📝 당시 추천 루틴</h4>
                 <div class="routine-grid">`;

        if (data.routine.am) {
            html += `
            <div class="routine-card" style="padding:15px;">
                <div class="routine-title" style="font-size:14px; color:#FF9800"><i class="fas fa-sun"></i> 아침</div>
                ${data.routine.am.map(step => `<div class="routine-step" style="font-size:12px;">${step}</div>`).join('')}
            </div>`;
        }

        if (data.routine.pm) {
            html += `
            <div class="routine-card" style="padding:15px;">
                <div class="routine-title" style="font-size:14px; color:#3F51B5"><i class="fas fa-moon"></i> 저녁</div>
                ${data.routine.pm.map(step => `<div class="routine-step" style="font-size:12px;">${step}</div>`).join('')}
            </div>`;
        }
        html += `</div>`;
    }

    // 3. 피부 사진 (기존 코드)
    html += `
        <div style="margin-top: 20px; text-align: center;">
             <img src="${BASE_URL}/${data.image_path}" style="max-width: 100%; border-radius: 8px; border: 1px solid #ddd;" onerror="this.style.display='none'">
        </div>
    `;

    contentDiv.innerHTML = html;
}

// --- [기능 4] 리포트 (추천 시스템) ---
async function runAnalysis() {
    const btn = document.getElementById("analyzeBtn");
    const userId = localStorage.getItem("userId");

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 분석 중...';

    try {
        // 1. 최신 히스토리 ID 가져오기
        const historyRes = await fetch(`${BASE_URL}/history/search?user_id=${userId}&page=1`);
        const historyJson = await historyRes.json();

        const latestId = (historyJson.data.records && historyJson.data.records.length > 0)
                         ? historyJson.data.records[0].id : 0;

        // 2. 추천 요청 (POST /recommend)
        const reqData = {
            user_id: userId,
            analysis_id: latestId,
            lifestyle: { sleep_hours_7d: 7, water_intake_ml: 1000 },
            user_pref: { age: 25, pref_texture: "lotion" }
        };

        const res = await fetch(`${BASE_URL}/recommend`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(reqData)
        });
        const report = await res.json();

        // 3. 결과 렌더링
        renderReport(report);

        // 달력 데이터도 최신으로 갱신
        fetchMonthlyData();

    } catch (e) {
        console.error(e);
        alert("분석 실패: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-magic"></i> 다시 분석하기';
    }
}

function renderReport(data) {
    document.getElementById("reportEmpty").style.display = "none";
    document.getElementById("reportResult").style.display = "block";

    // 제품 렌더링
    const pList = document.getElementById("productList");
    pList.innerHTML = data.top3.map(p => `
        <div class="product-card">
            <div class="product-brand">${p.brand}</div>
            <div class="product-name">${p.name}</div>
            <div class="product-reason">💡 ${p.reasons.join('<br>')}</div>
        </div>
    `).join('');

    // 루틴 렌더링
    const rList = document.getElementById("routineList");
    rList.innerHTML = `
        <div class="routine-card">
            <div class="routine-title" style="color: #FF9800"><i class="fas fa-sun"></i> 아침 루틴</div>
            ${data.routine.am.map(step => `<div class="routine-step">${step}</div>`).join('')}
        </div>
        <div class="routine-card">
            <div class="routine-title" style="color: #3F51B5"><i class="fas fa-moon"></i> 저녁 루틴</div>
            ${data.routine.pm.map(step => `<div class="routine-step">${step}</div>`).join('')}
        </div>
    `;
}

async function loadSettings() {
    const userId = localStorage.getItem("userId");
    try {
        const res = await fetch(`${BASE_URL}/user/profile/${userId}`);

        if (res.ok) {
            const data = await res.json();
            if (data) {
                // 입력칸 채우기 (서버 키값 -> HTML ID)
                document.getElementById('inputSleep').value = data.sleep_hours_7d || 0;
                document.getElementById('inputWater').value = data.water_intake_ml || 0;
                document.getElementById('inputWashCount').value = data.wash_freq_per_day || 0;

                // 라디오 버튼(칩) 선택하기
                // 예: data.wash_temp가 'warm'이면 value='warm'인 라디오 체크
                checkRadio('washTemp', data.wash_temp);
                checkRadio('sensitive', data.sensitivity);
                checkRadio('texture', data.pref_texture);
            }
        }
    } catch (e) {
        console.error("설정 로드 실패", e);
    }
}

function checkRadio(name, value) {
    if (!value) return;
    const radio = document.querySelector(`input[name="${name}"][value="${value}"]`);
    if (radio) radio.checked = true;
}

async function saveSettings() {
    const userId = localStorage.getItem("userId");

    // 1. 값 가져오기
    const sleep = document.getElementById('inputSleep').value;
    const water = document.getElementById('inputWater').value;
    const washCount = document.getElementById('inputWashCount').value;

    // 라디오 값 가져오기 (선택된 것 찾기)
    const washTemp = document.querySelector('input[name="washTemp"]:checked')?.value || "warm";
    const sensitive = document.querySelector('input[name="sensitive"]:checked')?.value || "no";
    const texture = document.querySelector('input[name="texture"]:checked')?.value || "lotion";

    // 2. 전송 데이터 만들기 (서버 구조 맞춤)
    const payload = {
        user_id: userId,
        profile_data: {
            sleep_hours_7d: parseInt(sleep) || 0,
            water_intake_ml: parseInt(water) || 0,
            wash_freq_per_day: parseInt(washCount) || 0,
            wash_temp: washTemp,
            sensitivity: sensitive,
            pref_texture: texture,
            age: 25 // 나이는 입력칸 없으면 기본값 (필요 시 추가)
        }
    };

    try {
        const res = await fetch(`${BASE_URL}/user/profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.status === 'success') {
            alert("✅ 설정이 저장되었습니다!");
        } else {
            alert("저장 실패");
        }
    } catch (e) {
        console.error(e);
        alert("서버 오류");
    }
}

// --- [기능 6] 제품 업데이트 요청 ---
async function triggerProductUpdate() {
    if(!confirm("제품 정보를 최신으로 업데이트 하시겠습니까?\n(시간이 조금 걸릴 수 있습니다)")) return;

    try {
        const res = await fetch(`${BASE_URL}/products/update`, {
            method: 'POST'
        });
        const data = await res.json();

        if (data.status === 'success') {
            alert("✅ " + data.message);
        } else {
            alert("요청 실패: " + data.detail);
        }
    } catch (e) {
        console.error(e);
        alert("서버 통신 오류");
    }
}