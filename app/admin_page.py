"""
관리자 조회 페이지 (기장사업부 직원용)
문의 접수 건 표시 + 처리 체크박스
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from app.knowledge_db import get_recent_logs, mark_log_handled

admin_page_router = APIRouter()

ADMIN_PASSWORD = "a10301140*"


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

    total = len(inquiries)
    handled_count = sum(1 for i in inquiries if i.get("handled"))
    unhandled_count = total - handled_count

    if not inquiries:
        rows = '<tr><td colspan="4" style="text-align:center;padding:40px;color:#999;">접수된 문의가 없습니다.</td></tr>'
    else:
        rows = ""
        for idx, log in enumerate(inquiries, 1):
            created = log.get("created_at", "")[:16]
            utterance = log.get("utterance", "").replace("<", "&lt;").replace(">", "&gt;")
            log_id = log.get("id", 0)
            is_handled = log.get("handled", 0)

            parts = utterance.replace("/", " ").split()
            phone_found = ""
            name_found = ""
            content_parts = []
            for p in parts:
                cleaned = p.replace("-", "")
                if cleaned.isdigit() and len(cleaned) >= 10:
                    phone_found = p
                elif not name_found and not cleaned.isdigit():
                    name_found = p
                else:
                    content_parts.append(p)

            if phone_found:
                content = " ".join(content_parts) if content_parts else ""
                display = f"<strong>{name_found}</strong><br>📞 {phone_found}"
                if content:
                    display += f"<br>💬 {content}"
            else:
                display = utterance

            checked = "checked" if is_handled else ""
            row_bg = "background:#f0f8f0;" if is_handled else ""
            check_label = "✅ 처리완료" if is_handled else "⬜ 미처리"
            label_color = "#4CAF50" if is_handled else "#e74c3c"

            rows += f"""
            <tr style="{row_bg}" id="row-{log_id}">
                <td style="white-space:nowrap;color:#888;text-align:center;">{idx}</td>
                <td style="white-space:nowrap;">{created}</td>
                <td>{display}</td>
                <td style="text-align:center;">
                    <label style="cursor:pointer;font-size:13px;color:{label_color};" id="label-{log_id}">
                        <input type="checkbox" {checked} onchange="toggleHandled({log_id}, this.checked)" style="transform:scale(1.3);cursor:pointer;margin-right:4px;" />
                        <span id="status-{log_id}">{check_label}</span>
                    </label>
                </td>
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
            .header {{ background: #1F4E79; color: white; padding: 20px; border-radius: 12px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; }}
            .header h1 {{ margin: 0; font-size: 20px; }}
            .stats {{ display: flex; gap: 10px; margin-bottom: 15px; }}
            .stat {{ background: white; padding: 12px; border-radius: 10px; flex: 1; text-align: center; }}
            .stat .num {{ font-size: 22px; font-weight: bold; }}
            .stat .label {{ font-size: 11px; color: #888; margin-top: 2px; }}
            .red {{ color: #e74c3c; }}
            .green {{ color: #4CAF50; }}
            .blue {{ color: #1F4E79; }}
            table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; }}
            th {{ background: #1F4E79; color: white; padding: 12px 10px; text-align: left; font-size: 13px; }}
            td {{ padding: 12px 10px; border-bottom: 1px solid #eee; font-size: 14px; vertical-align: top; line-height: 1.6; }}
            tr:hover {{ background: #f9f9f9; }}
            .btn {{ border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-weight: bold; font-size: 14px; margin-right: 8px; margin-bottom: 10px; }}
            .btn-yellow {{ background: #FEE500; }}
            .btn-gray {{ background: #eee; }}
            .note {{ background: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; font-size: 13px; color: #666; line-height: 1.6; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📋 문의 접수함</h1>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="num blue">{total}</div>
                <div class="label">전체</div>
            </div>
            <div class="stat">
                <div class="num red">{unhandled_count}</div>
                <div class="label">미처리</div>
            </div>
            <div class="stat">
                <div class="num green">{handled_count}</div>
                <div class="label">처리완료</div>
            </div>
        </div>

        <div>
            <button class="btn btn-yellow" onclick="location.reload()">🔄 새로고침</button>
        </div>

        <table>
            <tr>
                <th style="width:30px;">#</th>
                <th style="width:120px;">접수 시간</th>
                <th>문의 내용</th>
                <th style="width:100px;text-align:center;">처리</th>
            </tr>
            {rows}
        </table>

        <script>
        async function toggleHandled(logId, handled) {{
            try {{
                const res = await fetch('/admin/handle/' + logId, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ handled: handled, pw: '{ADMIN_PASSWORD}' }})
                }});
                const data = await res.json();
                if (data.success) {{
                    const row = document.getElementById('row-' + logId);
                    const label = document.getElementById('label-' + logId);
                    const status = document.getElementById('status-' + logId);
                    if (handled) {{
                        row.style.background = '#f0f8f0';
                        label.style.color = '#4CAF50';
                        status.textContent = '✅ 처리완료';
                    }} else {{
                        row.style.background = '';
                        label.style.color = '#e74c3c';
                        status.textContent = '⬜ 미처리';
                    }}
                }}
            }} catch (e) {{
                alert('처리 상태 변경에 실패했습니다.');
            }}
        }}
        </script>
    </body>
    </html>
    """)


@admin_page_router.post("/admin/handle/{log_id}")
async def handle_inquiry(log_id: int, request: Request):
    data = await request.json()
    pw = data.get("pw", "")
    if pw != ADMIN_PASSWORD:
        return JSONResponse({"success": False, "error": "인증 실패"}, status_code=403)

    handled = data.get("handled", False)
    result = mark_log_handled(log_id, handled)
    return JSONResponse({"success": result})
