from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
import hashlib
import secrets
import uuid
import os
import requests
from dotenv import load_dotenv

# .env 파일 자동 로드 (main.py 같은 폴더에 있는 .env)
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

app = FastAPI(title="Capstone Backend API")

# -----------------------------------------
# [AI 추론 서버] 주소 설정
# -----------------------------------------
# AI 서버가 YOLO로 알약을 크롭하고 CNN+OCR+OpenCV로 추론한 결과를 JSON으로 돌려줍니다.
# 환경변수 AI_SERVER_URL 로 덮어쓸 수 있습니다.
AI_SERVER_URL = os.environ.get("AI_SERVER_URL", "http://127.0.0.1:8001/predict")
# AI 서버가 아직 안 떠 있을 때, 프론트엔드 흐름 테스트용 목업 응답을 반환할지 여부.
# AI 서버 구현이 끝나면 False 로 바꾸세요.
MOCK_WHEN_AI_DOWN = True

# -----------------------------------------
# [Together AI 챗봇] 설정
# -----------------------------------------
# API 키는 환경변수 TOGETHER_API_KEY 로 설정. (.env 또는 시스템 환경변수)
TOGETHER_API_KEY        = os.environ.get("TOGETHER_API_KEY", "")
TOGETHER_API_URL        = "https://api.together.xyz/v1/chat/completions"
TOGETHER_CHATBOT_MODEL  = os.environ.get(
    "TOGETHER_CHATBOT_MODEL",
    "meta-llama/Llama-3.3-70B-Instruct-Turbo",  # 추후 변경 가능
)
CHATBOT_SYSTEM_PROMPT   = os.environ.get(
    "CHATBOT_SYSTEM_PROMPT",
    (
        "당신은 약품 정보를 제공하는 보조 AI입니다. "
        "도구 사용 지침:\n"
        "- 사용자가 특정 약품(이름·코드)에 대해 질문하면 lookup_medicine 도구로 DB에서 조회하고, 그 결과를 바탕으로 답변하세요.\n"
        "- 사용자가 증상(예: 두통, 발열)에 맞는 약을 물어보면 find_pills_for_symptom 도구를 사용하세요. "
        "이 도구는 사용자 보관 알약을 우선 검색하고, 없으면 전체 약품 DB에서 추천합니다.\n"
        "응답 규칙:\n"
        "- DB 조회 결과의 사실만 사용하세요. 추측하지 마세요.\n"
        "- 의학적 처방을 대신할 수 없음을 명시하고, 심한 증상은 의사·약사 상담을 권하세요."
    ),
)

# -----------------------------------------
# [데이터베이스] SQLite 설정
# -----------------------------------------
# main.py 와 같은 폴더에 app.db 파일이 생성됩니다.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.db")


def get_db() -> sqlite3.Connection:
    """요청마다 새 커넥션을 열고 dict 형태로 행을 받도록 설정합니다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 컬럼명을 key로 접근 가능하게
    return conn


def init_db() -> None:
    """서버 시작 시 테이블이 없으면 생성하고, 비어 있으면 샘플 데이터를 넣습니다."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            TEXT PRIMARY KEY,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name          TEXT,
            birth_date    TEXT,
            allergies     TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS medicines (
            drug_code                 TEXT PRIMARY KEY,
            medicine_name             TEXT,
            main_ingredient           TEXT,
            image                     TEXT,
            manufacturer_name         TEXT,
            indications               TEXT,
            dosage_and_administration TEXT,
            warnings                  TEXT,
            precautions               TEXT,
            drug_interactions         TEXT,
            adverse_reactions         TEXT,
            storage_instructions      TEXT,
            category                  TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS drug_interactions (
            ingredient_a       TEXT,
            ingredient_b       TEXT,
            risk_level         TEXT,
            interaction_effect TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_pills (
            user_id   TEXT NOT NULL,
            drug_code TEXT NOT NULL,
            added_at  TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, drug_code),
            FOREIGN KEY (user_id)   REFERENCES users(id),
            FOREIGN KEY (drug_code) REFERENCES medicines(drug_code)
        )
        """
    )
    # food_interactions 테이블은 사용 안 함 (제거 정책)
    cur.execute("DROP TABLE IF EXISTS food_interactions")

    conn.commit()
    conn.close()


# -----------------------------------------
# [비밀번호 해싱] 표준 라이브러리(PBKDF2-HMAC-SHA256) 사용
# -----------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, hashed = stored.split("$")
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return secrets.compare_digest(dk.hex(), hashed)


# 서버 시작 시 DB 초기화
init_db()

# CORS 설정: 프론트엔드(Flutter)에서 백엔드로 요청을 보낼 때 차단되지 않도록 설정합니다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 중에는 모든 접근을 허용합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/info")
def api_info():
    return {
        "message": "FastAPI 백엔드 서버가 정상적으로 실행되었습니다!",
        "database": "SQLite",
        "db_path": DB_PATH,
    }


@app.get("/api/status")
def get_status():
    return {"status": "ok"}


# -----------------------------------------
# [API 엔드포인트] 이미지 프록시 (CORS 우회)
# -----------------------------------------
from fastapi.responses import Response


@app.get("/api/image-proxy")
def image_proxy(url: str):
    """외부 이미지 URL을 백엔드 경유로 가져와 반환 (Flutter Web CORS 우회용)."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="잘못된 URL")
    try:
        r = requests.get(url, timeout=10, stream=True)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "image/jpeg")
        return Response(
            content=r.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"이미지 다운로드 실패: {e}")


# -----------------------------------------
# [API 엔드포인트] 약품 검색 (이름 또는 성분 부분 일치)
# -----------------------------------------
@app.get("/api/medicines/search")
def search_medicines(q: str = "", limit: int = 50):
    """약품명(medicine_name) 또는 주성분(main_ingredient) 부분 일치 검색."""
    q = q.strip()
    if not q:
        return {"count": 0, "results": []}

    conn = get_db()
    try:
        like = f"%{q}%"
        rows = conn.execute(
            """
            SELECT drug_code, medicine_name, main_ingredient, image, category
              FROM medicines
             WHERE medicine_name LIKE ? OR main_ingredient LIKE ?
             ORDER BY
                CASE WHEN medicine_name LIKE ? THEN 0 ELSE 1 END,
                medicine_name
             LIMIT ?
            """,
            (like, like, like, limit),
        ).fetchall()
        return {
            "count": len(rows),
            "results": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# -----------------------------------------
# [Pydantic 모델] 데이터 구조 정의
# -----------------------------------------
class UserSignup(BaseModel):
    email: str
    password: str
    name: str
    birth_date: str
    allergies: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


# 복약 분석 API용 요청 데이터 구조
class SafetyAnalysisRequest(BaseModel):
    current_drug_code: str         # 방금 스캔/인식한 알약 식별 코드 (예: "K-004378")
    taken_drug_codes: List[str]    # 사용자가 현재 복용 중이라고 선택한 알약 코드 리스트 (예: ["K-001029"])


# -----------------------------------------
# [API 엔드포인트] 회원가입 API
# -----------------------------------------
@app.post("/api/auth/signup")
def signup(user: UserSignup):
    conn = get_db()
    try:
        # 이메일 중복 확인
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ?", (user.email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="이미 가입된 이메일입니다.")

        user_id = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO users (id, email, password_hash, name, birth_date, allergies) VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                user.email,
                hash_password(user.password),
                user.name,
                user.birth_date,
                user.allergies,
            ),
        )
        conn.commit()

        return {
            "message": "회원가입 및 프로필 저장이 성공적으로 완료되었습니다.",
            "user_id": user_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"회원가입 실패: {str(e)}")
    finally:
        conn.close()


# -----------------------------------------
# [API 엔드포인트] 로그인 API
# -----------------------------------------
@app.post("/api/auth/login")
def login(user: UserLogin):
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (user.email,)
        ).fetchone()

        if not row or not verify_password(user.password, row["password_hash"]):
            raise HTTPException(
                status_code=401, detail="로그인 실패: 이메일 또는 비밀번호를 확인해주세요."
            )

        # Supabase access_token 을 대체하는 간단한 토큰 발급
        access_token = secrets.token_hex(32)
        return {
            "message": "로그인 성공",
            "access_token": access_token,  # 프론트엔드에서 저장해야 할 토큰
            "user_id": row["id"],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"로그인 실패: {str(e)}")
    finally:
        conn.close()


# -----------------------------------------
# [API 엔드포인트] 챗봇 (Together AI 프록시)
# -----------------------------------------
class ChatMessage(BaseModel):
    role: str    # "user" | "assistant" | "system" | "tool"
    content: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[list] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    user_id: Optional[str] = None   # find_pills_for_symptom 도구가 활용


# -----------------------------------------
# Agent 도구 정의 (OpenAI 호환 function calling)
# -----------------------------------------
import json as _json

CHATBOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_medicine",
            "description": (
                "약품명 또는 K-코드, 주성분으로 약품 상세 정보(효능, 사용법, 주의사항, "
                "부작용, 상호작용, 보관법, 제조사 등)를 DB에서 조회합니다. "
                "사용자가 특정 약품에 대해 묻거나 정보 확인을 요청할 때 사용하세요."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "약품명, K-코드(K-XXXXXX), 또는 주성분",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_pills_for_symptom",
            "description": (
                "증상이나 효능 키워드에 적합한 약품을 찾습니다. "
                "사용자가 보관 중인 알약(user_pills) 중에서 먼저 매칭하고, "
                "없으면 전체 medicines에서 추천합니다."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symptom": {
                        "type": "string",
                        "description": "증상 또는 효능 키워드 (예: 두통, 발열, 소화불량, 위염)",
                    }
                },
                "required": ["symptom"],
            },
        },
    },
]


def tool_lookup_medicine(query: str) -> str:
    """약품 1건 조회 결과를 JSON 문자열로 반환."""
    if not query:
        return _json.dumps({"found": False, "reason": "empty query"})
    conn = get_db()
    try:
        like = f"%{query}%"
        row = conn.execute(
            """
            SELECT *
              FROM medicines
             WHERE drug_code = ?
                OR medicine_name LIKE ?
                OR main_ingredient LIKE ?
             ORDER BY
                CASE WHEN drug_code = ? THEN 0
                     WHEN medicine_name LIKE ? THEN 1
                     ELSE 2 END
             LIMIT 1
            """,
            (query, like, like, query, like),
        ).fetchone()
        if not row:
            return _json.dumps({"found": False, "query": query}, ensure_ascii=False)
        return _json.dumps({"found": True, **dict(row)}, ensure_ascii=False)
    finally:
        conn.close()


def tool_find_pills_for_symptom(symptom: str, user_id: Optional[str]) -> str:
    """증상으로 알약 검색. 사용자 보관 우선, 없으면 전체 검색."""
    if not symptom:
        return _json.dumps({"results": [], "source": "none", "reason": "empty symptom"})
    conn = get_db()
    try:
        like = f"%{symptom}%"

        # 1) 사용자 보관 알약 우선
        if user_id:
            rows = conn.execute(
                """
                SELECT m.drug_code, m.medicine_name, m.main_ingredient, m.indications
                  FROM user_pills up
                  JOIN medicines m ON m.drug_code = up.drug_code
                 WHERE up.user_id = ? AND m.indications LIKE ?
                """,
                (user_id, like),
            ).fetchall()
            if rows:
                return _json.dumps(
                    {
                        "source": "user_pills",
                        "count": len(rows),
                        "results": [dict(r) for r in rows],
                    },
                    ensure_ascii=False,
                )

        # 2) 전체 medicines에서 추천 (상위 5건)
        rows = conn.execute(
            """
            SELECT drug_code, medicine_name, main_ingredient, indications
              FROM medicines
             WHERE indications LIKE ?
             LIMIT 5
            """,
            (like,),
        ).fetchall()
        return _json.dumps(
            {
                "source": "all_medicines",
                "count": len(rows),
                "results": [dict(r) for r in rows],
            },
            ensure_ascii=False,
        )
    finally:
        conn.close()


def _execute_tool(name: str, args: dict, user_id: Optional[str]) -> str:
    if name == "lookup_medicine":
        return tool_lookup_medicine(args.get("query", ""))
    if name == "find_pills_for_symptom":
        return tool_find_pills_for_symptom(args.get("symptom", ""), user_id)
    return _json.dumps({"error": f"unknown tool: {name}"})


MAX_TOOL_ITERATIONS = 5


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Tool calling 지원 에이전트 챗봇. 도구가 필요하면 호출/실행을 반복."""
    if not TOGETHER_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="TOGETHER_API_KEY 환경변수가 설정되지 않았습니다.",
        )

    # 메시지 준비 (system 프롬프트 자동 주입)
    msgs = [m.dict(exclude_none=True) for m in req.messages]
    if not msgs or msgs[0].get("role") != "system":
        msgs = [{"role": "system", "content": CHATBOT_SYSTEM_PROMPT}] + msgs

    headers = {
        "Authorization": f"Bearer {TOGETHER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        for _ in range(MAX_TOOL_ITERATIONS):
            resp = requests.post(
                TOGETHER_API_URL,
                headers=headers,
                json={
                    "model": TOGETHER_CHATBOT_MODEL,
                    "messages": msgs,
                    "tools": CHATBOT_TOOLS,
                    "tool_choice": "auto",
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            # 도구 호출이 없으면 최종 응답
            if not tool_calls:
                return {"reply": message.get("content", "")}

            # 어시스턴트의 tool_calls 메시지를 그대로 push
            msgs.append(message)

            # 각 도구 실행 후 결과를 'tool' role로 추가
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = _json.loads(fn.get("arguments", "{}"))
                except _json.JSONDecodeError:
                    args = {}
                result = _execute_tool(name, args, req.user_id)
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "name": name,
                    "content": result,
                })

        # MAX_TOOL_ITERATIONS 초과
        return {"reply": "(도구 호출 한도 초과) 다시 질문해주세요."}

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Together AI 호출 실패: {e}")
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=500, detail=f"응답 파싱 실패: {e}")


# -----------------------------------------
# [API 엔드포인트] 사용자 프로필 조회/수정 (이메일/비밀번호 제외 필드만 수정 가능)
# -----------------------------------------
class UserProfileUpdate(BaseModel):
    user_id: str
    name: Optional[str] = None
    birth_date: Optional[str] = None
    allergies: Optional[str] = None


@app.get("/api/user/me")
def get_user_profile(user_id: str):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 필요")
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT id, email, name, birth_date, allergies FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        return dict(row)
    finally:
        conn.close()


@app.patch("/api/user/me")
def update_user_profile(req: UserProfileUpdate):
    conn = get_db()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE id = ?", (req.user_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
        # 보낸 필드만 업데이트
        fields, values = [], []
        if req.name is not None:
            fields.append("name = ?")
            values.append(req.name)
        if req.birth_date is not None:
            fields.append("birth_date = ?")
            values.append(req.birth_date)
        if req.allergies is not None:
            fields.append("allergies = ?")
            values.append(req.allergies)
        if not fields:
            return {"status": "no_change"}
        values.append(req.user_id)
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


# -----------------------------------------
# [API 엔드포인트] 사용자 알약 목록 (user_pills)
# -----------------------------------------
class UserPillRequest(BaseModel):
    user_id: str
    drug_code: str


@app.get("/api/user/pills")
def list_user_pills(user_id: str):
    """특정 사용자의 알약 목록 (medicines JOIN으로 정보 포함)."""
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 필요")
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT m.drug_code, m.medicine_name, m.main_ingredient, m.image, m.category, up.added_at
              FROM user_pills up
              JOIN medicines m ON m.drug_code = up.drug_code
             WHERE up.user_id = ?
             ORDER BY up.added_at DESC
            """,
            (user_id,),
        ).fetchall()
        return {"count": len(rows), "results": [dict(r) for r in rows]}
    finally:
        conn.close()


@app.post("/api/user/pills")
def add_user_pill(req: UserPillRequest):
    """사용자 알약 목록에 추가 (중복은 ON CONFLICT로 무시)."""
    conn = get_db()
    try:
        # 약품 존재 여부 확인
        med = conn.execute(
            "SELECT drug_code FROM medicines WHERE drug_code = ?",
            (req.drug_code,),
        ).fetchone()
        if not med:
            raise HTTPException(status_code=404, detail="해당 drug_code 약품을 찾을 수 없습니다.")
        conn.execute(
            "INSERT OR IGNORE INTO user_pills (user_id, drug_code) VALUES (?, ?)",
            (req.user_id, req.drug_code),
        )
        conn.commit()
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"추가 실패: {e}")
    finally:
        conn.close()


@app.delete("/api/user/pills")
def remove_user_pill(user_id: str, drug_code: str):
    """사용자 알약 목록에서 제거."""
    conn = get_db()
    try:
        conn.execute(
            "DELETE FROM user_pills WHERE user_id = ? AND drug_code = ?",
            (user_id, drug_code),
        )
        conn.commit()
        return {"status": "ok"}
    finally:
        conn.close()


# -----------------------------------------
# [API 엔드포인트] 복약 안전 분석 API
# -----------------------------------------
@app.post("/api/analyze-safety")
def analyze_safety(request: SafetyAnalysisRequest):
    conn = get_db()
    try:
        # 1. 방금 스캔한 알약 식별 코드를 기반으로 기본 스펙 및 주성분(main_ingredient) 조회
        current_medicine = conn.execute(
            "SELECT * FROM medicines WHERE drug_code = ?", (request.current_drug_code,)
        ).fetchone()
        if not current_medicine:
            raise HTTPException(
                status_code=404, detail="인식된 알약 코드가 medicines 테이블에 존재하지 않습니다."
            )

        target_ingredient = current_medicine["main_ingredient"]

        # 2. 복용 중인 다른 알약 코드 리스트의 주성분 정보 일괄 추출
        taken_ingredients = []
        if request.taken_drug_codes:
            placeholders = ",".join("?" for _ in request.taken_drug_codes)
            rows = conn.execute(
                f"SELECT main_ingredient FROM medicines WHERE drug_code IN ({placeholders})",
                tuple(request.taken_drug_codes),
            ).fetchall()
            taken_ingredients = [r["main_ingredient"] for r in rows]

        # 3. 약물 간 상호작용(DUR) 테이블 교차 대조
        drug_interactions = []
        for ingredient in taken_ingredients:
            rows = conn.execute(
                """
                SELECT * FROM drug_interactions
                WHERE (ingredient_a = ? AND ingredient_b = ?)
                   OR (ingredient_a = ? AND ingredient_b = ?)
                """,
                (target_ingredient, ingredient, ingredient, target_ingredient),
            ).fetchall()
            drug_interactions.extend(rows)

        # 4. 분석 데이터 최종 정제 후 Flutter 앱으로 결과 반환
        return {
            "status": "success",
            "medicine_info": {
                "drug_code": current_medicine["drug_code"],
                "medicine_name": current_medicine["medicine_name"],
                "main_ingredient": target_ingredient,
                "image": current_medicine["image"],
            },
            "drug_interactions": [
                {
                    "with_ingredient": res["ingredient_b"]
                    if res["ingredient_a"] == target_ingredient
                    else res["ingredient_a"],
                    "risk_level": res["risk_level"],
                    "effect": res["interaction_effect"],
                }
                for res in drug_interactions
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"복약 안전 분석 실패: {str(e)}")
    finally:
        conn.close()


# -----------------------------------------
# [API 엔드포인트] 약품 스캔 (이미지 업로드 → AI 서버 추론 → DB 보강)
# -----------------------------------------
# 동기(def) 핸들러로 두어 requests(동기) 호출이 FastAPI 스레드풀에서 안전하게 돌도록 합니다.
@app.post("/api/scan")
def scan_medicine(file: UploadFile = File(...)):
    # 1. 프론트엔드에서 전송한 이미지 파일을 메모리로 읽습니다.
    image_bytes = file.file.read()

    # 2. AI 서버로 이미지를 그대로 전달하고 추론 결과(JSON)를 받습니다.
    #    계약: 응답은 {"count": N, "results": [{"drug_code", "confidence", "status", "candidates"}, ...]}
    try:
        resp = requests.post(
            AI_SERVER_URL,
            files={
                "file": (
                    file.filename or "image.jpg",
                    image_bytes,
                    file.content_type or "image/jpeg",
                )
            },
            timeout=60,
        )
        resp.raise_for_status()
        ai_data = resp.json()
    except requests.exceptions.RequestException as e:
        if not MOCK_WHEN_AI_DOWN:
            raise HTTPException(
                status_code=503, detail=f"AI 추론 서버에 연결할 수 없습니다: {e}"
            )
        # AI 서버 미구현/미실행 시 프론트 흐름 테스트용 목업 (seed 데이터의 와파린)
        ai_data = {
            "count": 1,
            "results": [
                {"drug_code": "K-001029", "confidence": 0.0, "status": "mock", "candidates": []}
            ],
            "_mock": True,
        }

    # 3. 각 결과의 drug_code 로 medicines 테이블을 조회해 약 정보를 채웁니다.
    conn = get_db()
    try:
        enriched = []
        for r in ai_data.get("results", []):
            code = r.get("drug_code")
            med = None
            if code:
                row = conn.execute(
                    "SELECT * FROM medicines WHERE drug_code = ?", (code,)
                ).fetchone()
                med = dict(row) if row else None
            enriched.append(
                {
                    "drug_code": code,
                    "confidence": r.get("confidence"),
                    "status": r.get("status"),
                    "candidates": r.get("candidates", []),
                    "found_in_db": med is not None,
                    "name": med["medicine_name"] if med else (code or "알 수 없는 알약"),
                    "ingredient": med["main_ingredient"] if med else None,
                    "image": med["image"] if med else None,
                    "category": med["category"] if med else None,
                }
            )
    finally:
        conn.close()

    # 4. 프론트엔드 호환: 기존 코드가 읽는 ai_result(첫 결과)도 함께 제공합니다.
    first = enriched[0] if enriched else None
    mock_note = " (AI 서버 미연결 - 목업 응답)" if ai_data.get("_mock") else ""
    return {
        "message": "이미지가 성공적으로 처리되었습니다." + mock_note,
        "filename": file.filename,
        "count": len(enriched),
        "results": enriched,
        "ai_result": {
            "name": first["name"],
            "ingredient": first["ingredient"] or "",
            "drug_code": first["drug_code"],
            "confidence": first["confidence"],
        }
        if first
        else None,
    }


# -----------------------------------------
# [정적 파일] 프론트엔드 빌드 결과를 같이 서빙 (ngrok 1개로 통합)
# -----------------------------------------
# build/web 폴더가 있으면 / 경로로 서빙. SPA 라우팅을 위해 html=True.
_WEB_BUILD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "frontend", "build", "web",
)
if os.path.isdir(_WEB_BUILD_DIR):
    app.mount("/", StaticFiles(directory=_WEB_BUILD_DIR, html=True), name="web")

