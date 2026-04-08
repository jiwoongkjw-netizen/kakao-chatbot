"""
지식 데이터베이스 관리 모듈 (SQLite + 키워드 매칭)

FAQ/정형 답변을 저장하고, 사용자 발화에서 키워드를 추출하여
가장 적합한 답변을 검색합니다.
"""

import json
import sqlite3
import os
from typing import Optional
from app.config import settings


DB_PATH = settings.DB_PATH


def get_connection() -> sqlite3.Connection:
    """SQLite 연결 (동기)"""
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """테이블 생성 (서버 시작 시 1회 호출)"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT DEFAULT '일반',
            question    TEXT NOT NULL,
            answer      TEXT NOT NULL,
            keywords    TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     TEXT,
            utterance   TEXT NOT NULL,
            response    TEXT NOT NULL,
            source      TEXT DEFAULT 'ai',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


# ── 지식 검색 ──

def search_knowledge(utterance: str) -> Optional[dict]:
    """
    사용자 발화에서 키워드 매칭으로 가장 적합한 FAQ를 검색합니다.

    검색 우선순위:
    1. question 컬럼에 발화 전체가 포함된 경우 (정확 매칭)
    2. keywords 컬럼의 키워드가 발화에 포함된 경우 (키워드 매칭)
    3. question에 발화의 단어가 포함된 경우 (부분 매칭)
    """
    conn = get_connection()
    cursor = conn.cursor()
    utterance_lower = utterance.strip().lower()

    # 1단계: 질문 정확 매칭 (발화가 질문에 포함되거나 질문이 발화에 포함)
    cursor.execute("""
        SELECT *, 100 as score FROM knowledge
        WHERE LOWER(question) = ?
           OR LOWER(question) LIKE ?
           OR ? LIKE '%' || LOWER(question) || '%'
        LIMIT 1
    """, (utterance_lower, f"%{utterance_lower}%", utterance_lower))

    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    # 2단계: 키워드 매칭 (점수 기반)
    cursor.execute("SELECT * FROM knowledge WHERE keywords != ''")
    all_rows = cursor.fetchall()

    best_match = None
    best_score = 0

    for row in all_rows:
        keywords = [kw.strip().lower() for kw in row["keywords"].split(",") if kw.strip()]
        matched = sum(1 for kw in keywords if kw in utterance_lower)
        if matched > 0:
            score = matched / max(len(keywords), 1)
            if score > best_score:
                best_score = score
                best_match = dict(row)

    if best_match and best_score >= 0.3:  # 30% 이상 키워드 매칭
        conn.close()
        return best_match

    # 3단계: 단어 부분 매칭
    words = [w for w in utterance_lower.split() if len(w) >= 2]
    for word in words:
        cursor.execute("""
            SELECT * FROM knowledge
            WHERE LOWER(question) LIKE ? OR LOWER(keywords) LIKE ?
            LIMIT 1
        """, (f"%{word}%", f"%{word}%"))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    conn.close()
    return None


def get_all_knowledge_as_context() -> str:
    """
    전체 FAQ를 텍스트로 변환하여 AI 프롬프트 컨텍스트로 제공합니다.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT category, question, answer FROM knowledge ORDER BY category, id")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "등록된 FAQ가 없습니다."

    lines = []
    current_category = None
    for row in rows:
        if row["category"] != current_category:
            current_category = row["category"]
            lines.append(f"\n[{current_category}]")
        lines.append(f"Q: {row['question']}")
        lines.append(f"A: {row['answer']}")

    return "\n".join(lines)


# ── CRUD 관리 ──

def add_knowledge(category: str, question: str, answer: str, keywords: str = "") -> int:
    """FAQ 추가"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO knowledge (category, question, answer, keywords) VALUES (?, ?, ?, ?)",
        (category, question, answer, keywords)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def update_knowledge(knowledge_id: int, **kwargs) -> bool:
    """FAQ 수정"""
    allowed = {"category", "question", "answer", "keywords"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [knowledge_id]
    cursor.execute(
        f"UPDATE knowledge SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def delete_knowledge(knowledge_id: int) -> bool:
    """FAQ 삭제"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def list_knowledge() -> list:
    """전체 FAQ 목록"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM knowledge ORDER BY category, id")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def bulk_insert_knowledge(items: list) -> int:
    """FAQ 일괄 입력"""
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    for item in items:
        cursor.execute(
            "INSERT INTO knowledge (category, question, answer, keywords) VALUES (?, ?, ?, ?)",
            (
                item.get("category", "일반"),
                item["question"],
                item["answer"],
                item.get("keywords", ""),
            )
        )
        count += 1
    conn.commit()
    conn.close()
    return count


# ── 대화 로그 ──

def log_chat(user_id: str, utterance: str, response: str, source: str = "ai"):
    """대화 기록 저장"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_logs (user_id, utterance, response, source) VALUES (?, ?, ?, ?)",
        (user_id, utterance, response[:2000], source)
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 50) -> list:
    """최근 대화 로그 조회"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chat_logs ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


# ── 초기 데이터 로드 ──

def seed_from_json(json_path: str = "data/seed_data.json"):
    """JSON 파일에서 초기 FAQ 데이터 로드"""
    if not os.path.exists(json_path):
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM knowledge")
    if cursor.fetchone()["cnt"] > 0:
        conn.close()
        return 0  # 이미 데이터가 있으면 건너뛰기

    conn.close()

    with open(json_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    return bulk_insert_knowledge(items)
