# 카카오 비즈니스 채널 AI 챗봇 - 완전 구축 가이드

## 전체 아키텍처

```
사용자 (카카오톡)
    ↕
카카오톡 채널 (비즈니스)
    ↕
카카오 i 오픈빌더 (챗봇 관리자센터)
    ↕  POST /webhook (JSON)
스킬 서버 (FastAPI, 클라우드 배포)
    ↕
┌─────────────────────────┐
│ 1. 지식 DB (SQLite)     │ ← FAQ/정형 답변 즉시 반환
│ 2. Claude AI (Anthropic)│ ← DB에 없는 질문 AI 생성
└─────────────────────────┘
```

## 처리 흐름

1. 사용자가 카카오톡 채널에 메시지를 보냄
2. 카카오 오픈빌더가 스킬 서버(우리 서버)에 POST 요청 전송
3. 서버가 발화(utterance)를 추출
4. 지식 DB에서 매칭 FAQ 검색
   - 매칭 성공 → DB 답변 즉시 반환 (빠름)
   - 매칭 실패 → Claude API로 AI 답변 생성
5. 카카오 응답 JSON 형식으로 반환
6. 사용자에게 답변 노출

---

## PHASE 1: 사전 준비

### 필요 항목

- 카카오 비즈니스 계정: https://business.kakao.com
- 카카오 i 오픈빌더 접근: https://i.kakao.com
- Anthropic API Key: https://console.anthropic.com
- 클라우드 서버 (공인IP + HTTPS 필수): Railway, Render, AWS EC2 등
- Python 3.10 이상

### 카카오톡 채널이 이미 있다면

바로 PHASE 2로 넘어가면 됩니다. 채널이 없다면:

1. https://business.kakao.com → 로그인
2. 카카오톡 채널 → 새 채널 만들기
3. 채널 정보 입력 후 생성, 공개 상태로 전환

---

## PHASE 2: 서버 개발

### 프로젝트 구조

```
kakao-chatbot/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 서버 엔트리포인트
│   ├── config.py             # 환경변수 설정
│   ├── kakao_response.py     # 카카오 응답 JSON 빌더
│   ├── knowledge_db.py       # SQLite 지식 DB 관리
│   ├── ai_engine.py          # Claude API 연동
│   └── webhook.py            # 웹훅 + 관리자 API 라우터
├── data/
│   └── seed_data.json        # 초기 FAQ 데이터
├── test_webhook.py           # 로컬 테스트 스크립트
├── requirements.txt
├── .env
├── .gitignore
├── Dockerfile
└── docker-compose.yml
```

### 로컬 실행 방법

```bash
# 1. 프로젝트 디렉토리 이동
cd kakao-chatbot

# 2. 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경변수 설정
#    .env 파일을 열고 ANTHROPIC_API_KEY에 실제 키 입력
#    ADMIN_API_KEY도 원하는 값으로 변경

# 5. 서버 실행
uvicorn app.main:app --reload --port 8000

# 6. 테스트
python test_webhook.py
```

---

## PHASE 3: 카카오 i 오픈빌더 설정

### 3-1. 봇 생성

1. https://i.kakao.com 접속 → 로그인
2. [+ 봇 만들기] → [카카오톡 챗봇]
3. 봇 이름 입력 후 생성

### 3-2. 카카오톡 채널 연결

1. 오픈빌더 좌측 [설정] 탭
2. [카카오톡 채널 연결] → 운영할 채널 선택

### 3-3. 스킬 등록

1. 좌측 [스킬] 탭 → [생성] 클릭
2. 스킬 이름: `AI_답변_스킬`
3. URL: `https://your-domain.com/webhook`
   (반드시 HTTPS, 공인IP 또는 도메인 필요)
4. [저장]
5. [스킬서버로 전송] 버튼으로 테스트 가능

### 3-4. 폴백 블록에 스킬 연결

모든 사용자 발화를 AI가 처리하도록 폴백 블록에 연결합니다.

1. [시나리오] → [기본 시나리오] → [폴백 블록]
2. [파라미터 설정] → 스킬 선택에서 `AI_답변_스킬` 선택
3. [봇 응답] → [+ 응답 추가] → [스킬데이터] 선택
4. [저장]

### 3-5. 웰컴 블록 설정 (선택사항)

1. [기본 시나리오] → [웰컴 블록]
2. 봇 응답에 인사말 직접 입력
3. 예: "안녕하세요! 무엇이 궁금하신가요?"
4. 바로가기 버튼 추가 가능

### 3-6. 배포

1. 우측 상단 [배포] 클릭
2. 배포 사유 입력 후 [배포]
3. 1~2분 후 운영 채널에 반영

---

## PHASE 4: 클라우드 배포

### 방법 A: Railway (가장 간단)

```bash
# Railway CLI 설치 후
railway login
railway init
railway up

# 환경변수 설정
railway variables set ANTHROPIC_API_KEY=sk-ant-api03-xxxxx
railway variables set ADMIN_API_KEY=my-secret-key

# HTTPS 도메인 자동 할당
railway domain
# → 출력된 URL을 오픈빌더 스킬 URL에 등록
```

### 방법 B: Render.com

1. GitHub에 코드 push
2. https://render.com → New Web Service
3. GitHub 레포 연결
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Environment Variables에 .env 내용 입력
7. 배포 완료 후 URL → 오픈빌더 스킬 URL에 등록

### 방법 C: Docker (AWS EC2 등)

```bash
# EC2에서
git clone <your-repo>
cd kakao-chatbot

# .env 파일 편집
nano .env

# Docker 실행
docker-compose up -d --build

# Nginx + Let's Encrypt로 HTTPS 설정 필요
```

Nginx 설정 예시:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
# HTTPS 인증서 설치
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## PHASE 5: 지식 DB 관리

### 관리자 API 사용법

```bash
# FAQ 목록 조회
curl https://your-domain.com/admin/knowledge \
  -H "X-Admin-Key: my-secret-key"

# FAQ 추가
curl -X POST https://your-domain.com/admin/knowledge \
  -H "X-Admin-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "category": "서비스안내",
    "question": "상담 예약은 어떻게 하나요?",
    "answer": "전화 또는 카카오 메시지로 예약 가능합니다.",
    "keywords": "예약,상담,전화"
  }'

# FAQ 수정
curl -X PUT https://your-domain.com/admin/knowledge/1 \
  -H "X-Admin-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"answer": "수정된 답변 내용"}'

# FAQ 삭제
curl -X DELETE https://your-domain.com/admin/knowledge/1 \
  -H "X-Admin-Key: my-secret-key"

# FAQ 일괄 입력 (JSON 배열)
curl -X POST https://your-domain.com/admin/knowledge/bulk \
  -H "X-Admin-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d @data/seed_data.json

# 대화 로그 조회
curl https://your-domain.com/admin/logs?limit=20 \
  -H "X-Admin-Key: my-secret-key"
```

### seed_data.json 커스터마이징

`data/seed_data.json` 파일을 편집하여 초기 FAQ를 설정합니다.
서버 최초 실행 시 자동으로 DB에 로드됩니다.

각 항목 형식:
```json
{
  "category": "카테고리명",
  "question": "예상 질문",
  "answer": "답변 내용",
  "keywords": "키워드1,키워드2,키워드3"
}
```

keywords 필드가 검색 정확도에 큰 영향을 미칩니다.
사용자가 실제로 입력할 만한 단어를 쉼표로 구분하여 넣어주세요.

---

## 5초 타임아웃 대응 전략

카카오 오픈빌더 스킬 타임아웃은 5초 고정입니다.

1. claude-haiku 모델 사용 (기본값) → 대부분 2~3초 내 응답
2. DB 우선 검색 → 정확 매칭 시 AI 호출 없이 즉시 응답 (0.1초 이내)
3. max_tokens=300 → 답변 길이 제한으로 생성 속도 확보
4. 콜백 기능 (고급) → 오픈빌더 설정에서 AI 챗봇 콜백 신청 시 1분까지 가능

---

## 주요 파일 설명

| 파일 | 역할 |
|------|------|
| app/main.py | FastAPI 서버 시작, 라우터 등록, DB 초기화 |
| app/config.py | .env 환경변수 로드 |
| app/webhook.py | 카카오 웹훅 처리 + 관리자 CRUD API |
| app/knowledge_db.py | SQLite DB CRUD, 키워드 검색, 대화 로그 |
| app/ai_engine.py | Claude API 호출, 시스템 프롬프트 구성 |
| app/kakao_response.py | 카카오 응답 JSON 포맷 빌더 |
| data/seed_data.json | 초기 FAQ 데이터 |
| test_webhook.py | 로컬 테스트 스크립트 |

---

## 테스트 체크리스트

- [ ] 서버 헬스체크: curl https://your-domain.com/health
- [ ] 로컬 웹훅 테스트: python test_webhook.py
- [ ] 오픈빌더 스킬 테스트: 스킬 페이지 → 스킬서버로 전송
- [ ] 오픈빌더 봇테스트: 우측 상단 봇테스트 패널
- [ ] 실제 카카오톡 테스트: 배포 후 채널에서 직접 대화

---

## 운영 팁

- 오픈빌더 [분석] → [미응답 발화]에서 봇이 처리 못한 질문을 확인하고 DB에 추가
- 관리자 API /admin/logs로 실제 대화를 모니터링
- 자주 반복되는 AI 답변은 DB에 FAQ로 등록하면 응답 속도가 빨라짐
- .env의 BOT_DESCRIPTION을 수정하면 AI의 답변 톤/범위를 조절 가능
