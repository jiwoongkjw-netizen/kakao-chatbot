"""
관리자 조회 페이지 (기장사업부 직원용)
문의 접수 건만 표시
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.knowledge_db import get_recent_logs

admin_page_router = APIRouter()

ADMIN_PASSWORD = "sedam2026"


@admin_page_router.get("/admin/page", response_class=HTMLResponse)
async def admin_page(pw: str = ""):
    if pw != ADMIN_PASSWORD:
        return HTMLResponse(content="""
        <html>
        <head><meta charset="utf-8"><title>세담택스 문의 접수함</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: -apple-system, sans-serif; max-width: 500px; margin: 50px auto; padding: 20px; }
            h2 { color: #1F4E79; }
            input { padding: 12px; font-size: 16px; width: 100%; margin: 10px 0; border: 1px solid #ddd; border-radius: 8px; box-sizing: border-box; }
            button { padding: 12px 24px; font-size: 16px; background: #FEE500; border: none; border-radius: 8px; cursor: pointer; width: 100%; font-weight: bold; }
        </style>
        </head>
        <body>
            <h2>세담택스 문의 접수함</h2>
            <form method="get">
                <input type="password" name="pw" placeholder="비밀번호를 입력하세요" />
                <button type="submit">로그인</button>
            </form>
        </body>
        </html>
        """)

    all_logs = get_recent_logs(500)
    inquiries = [log for log in all_logs if log.get("source") == "inquiry"]

    if not inquiries:
        rows = '<tr><td colspan="3" style="text-align:center;padding:40px;color:#999;">접수된 문의가 없습니다.</td></tr>'
    else:
        rows = ""
        for idx, log in enumerate(inquiries, 1):
            created = log.get("created_at", "")[:16]
            utterance = log.get("utterance", "").replace("<", "&lt;").replace(">", "&gt;")

            parts = utterance.split("/")
            if len(parts) >= 3:
                name = parts[0].strip()
                phone = parts[1].strip()
                content = "/".join(parts[2:]).strip()
                display = f"<strong>{name}</strong><br>📞 {phone}<br>💬 {content}"
            elif len(parts) == 2:
                display = f"📞 {parts[0].strip()}<br>💬 {parts[1].strip()}"
            else:
                display = utterance

            rows += f"""
            <tr>
                <td style="white-space:nowrap;color:#888;">{idx}</td>
                <td style="white-space:nowrap;">{created}</td>
                <td>{display}</td>
            </tr>
            """

    return HTMLResponse(content=f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>세담택스 문의 접수함</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: -apple-system, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .header {{ background: #1F4E79; color: white; padding: 20px; border-radius: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .badge {{ background: #FEE500; color: #333; padding: 6px 14px; border-radius: 20px; font-weight: bold; font-size: 16px; }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; }}
            th {{ background: #1F4E79; color: white; padding: 12px 10px; text-align: left; font-size: 13px; }}
            td {{ padding: 12px 10px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; line-height: 1.6; }}
            tr:hover {{ background: #f9f9f9; }}
            .refresh {{ background: #FEE500; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; margin-bottom: 15px; }}
            .note {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; font-size: 13px; color: #666; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📋 문의 접수함</h1>
            <span class="badge">{len(inquiries)}건</span>
        </div>

        <div class="note">
            고객이 업무시간 외에 남긴 문의 내역입니다.<br>
            확인 후 연락 부탁드립니다. (031-657-0187)
        </div>

        <button class="refresh" onclick="location.reload()">🔄 새로고침</button>

        <table>
            <tr>
                <th style="width:30px;">#</th>
                <th style="width:120px;">접수 시간</th>
                <th>문의 내용</th>
            </tr>
            {rows}
        </table>
    </body>
    </html>
    """)
