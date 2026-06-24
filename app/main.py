import json
import mimetypes
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from .database import connect, init_db, rows_to_dicts


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"


TABLES: dict[str, dict[str, Any]] = {
    "user-profiles": {
        "table": "user_profiles",
        "order": "display_name COLLATE NOCASE",
        "required": ["display_name"],
        "fields": [
            "display_name",
            "role",
            "preferences",
            "communication_style",
            "long_term_context",
        ],
    },
    "project-profiles": {
        "table": "project_profiles",
        "order": "updated_at DESC",
        "required": ["name"],
        "fields": ["name", "goal", "status", "stack", "notes"],
    },
    "issue-progress": {
        "table": "issue_progress",
        "order": "updated_at DESC",
        "required": ["title"],
        "fields": [
            "project_id",
            "title",
            "state",
            "priority",
            "current_step",
            "next_action",
            "notes",
        ],
    },
    "error-records": {
        "table": "error_records",
        "order": "updated_at DESC",
        "required": ["title"],
        "fields": [
            "project_id",
            "title",
            "environment",
            "symptom",
            "root_cause",
            "fix",
            "prevention",
        ],
    },
    "prompt-templates": {
        "table": "prompt_templates",
        "order": "platform COLLATE NOCASE, title COLLATE NOCASE",
        "required": ["platform", "title"],
        "fields": ["platform", "title", "body", "notes"],
    },
}


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def definition(kind: str) -> dict[str, Any]:
    try:
        return TABLES[kind]
    except KeyError as exc:
        raise ApiError(404, "Unknown context type") from exc


def normalize_payload(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = definition(kind)
    data: dict[str, Any] = {}
    for field in item["fields"]:
        value = payload.get(field)
        if field == "project_id":
            data[field] = str(value).strip() if value else None
        else:
            data[field] = str(value).strip() if value is not None else ""

    for field in item["required"]:
        if not data.get(field):
            raise ApiError(400, f"{field} is required")

    if "project_id" in data:
        ensure_project_exists(data.get("project_id"))
    return data


def get_record(table: str, record_id: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ApiError(404, "Record not found")
    return dict(row)


def ensure_project_exists(project_id: str | None) -> None:
    if not project_id:
        return
    with connect() as conn:
        row = conn.execute("SELECT id FROM project_profiles WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise ApiError(400, "project_id does not exist")


def list_records(kind: str) -> list[dict[str, Any]]:
    item = definition(kind)
    with connect() as conn:
        rows = conn.execute(f"SELECT * FROM {item['table']} ORDER BY {item['order']}").fetchall()
    return rows_to_dicts(rows)


def create_record(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = definition(kind)
    data = normalize_payload(kind, payload)
    record_id = str(uuid4())
    timestamp = now_iso()
    fields = item["fields"]
    columns = ["id", *fields, "created_at", "updated_at"]
    values = [record_id, *[data.get(field) for field in fields], timestamp, timestamp]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        conn.execute(
            f"INSERT INTO {item['table']} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )
    return get_record(item["table"], record_id)


def update_record(kind: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = definition(kind)
    data = normalize_payload(kind, payload)
    fields = item["fields"]
    assignments = ", ".join(f"{field} = ?" for field in fields)
    values = [data.get(field) for field in fields]
    timestamp = now_iso()
    with connect() as conn:
        cursor = conn.execute(
            f"UPDATE {item['table']} SET {assignments}, updated_at = ? WHERE id = ?",
            [*values, timestamp, record_id],
        )
        if cursor.rowcount == 0:
            raise ApiError(404, "Record not found")
    return get_record(item["table"], record_id)


def delete_record(kind: str, record_id: str) -> dict[str, str]:
    item = definition(kind)
    with connect() as conn:
        cursor = conn.execute(f"DELETE FROM {item['table']} WHERE id = ?", (record_id,))
        if cursor.rowcount == 0:
            raise ApiError(404, "Record not found")
    return {"status": "deleted"}


def summary() -> dict[str, Any]:
    with connect() as conn:
        counts = {
            key: conn.execute(f"SELECT COUNT(*) AS c FROM {value['table']}").fetchone()["c"]
            for key, value in TABLES.items()
        }
        active_issues = conn.execute(
            "SELECT COUNT(*) AS c FROM issue_progress WHERE state NOT IN ('done', 'closed')"
        ).fetchone()["c"]
    return {"counts": counts, "active_issues": active_issues}


def filtered_context(project_id: str | None, platform: str | None) -> dict[str, Any]:
    with connect() as conn:
        users = rows_to_dicts(conn.execute("SELECT * FROM user_profiles ORDER BY display_name").fetchall())
        if project_id:
            projects = rows_to_dicts(
                conn.execute("SELECT * FROM project_profiles WHERE id = ?", (project_id,)).fetchall()
            )
            if not projects:
                raise ApiError(404, "Project not found")
            issues = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM issue_progress WHERE project_id = ? ORDER BY updated_at DESC",
                    (project_id,),
                ).fetchall()
            )
            errors = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM error_records WHERE project_id = ? ORDER BY updated_at DESC",
                    (project_id,),
                ).fetchall()
            )
        else:
            projects = rows_to_dicts(conn.execute("SELECT * FROM project_profiles ORDER BY updated_at DESC").fetchall())
            issues = rows_to_dicts(conn.execute("SELECT * FROM issue_progress ORDER BY updated_at DESC").fetchall())
            errors = rows_to_dicts(conn.execute("SELECT * FROM error_records ORDER BY updated_at DESC").fetchall())

        if platform:
            templates = rows_to_dicts(
                conn.execute(
                    "SELECT * FROM prompt_templates WHERE platform = ? ORDER BY title",
                    (platform,),
                ).fetchall()
            )
        else:
            templates = rows_to_dicts(
                conn.execute("SELECT * FROM prompt_templates ORDER BY platform, title").fetchall()
            )

    return {
        "generated_at": now_iso(),
        "filters": {"project_id": project_id, "platform": platform},
        "user_profiles": users,
        "project_profiles": projects,
        "issue_progress": issues,
        "error_records": errors,
        "prompt_templates": templates,
    }


def project_name(projects: list[dict[str, Any]], project_id: str | None) -> str:
    if not project_id:
        return "全部项目"
    if not projects:
        return project_id
    return projects[0]["name"]


def bullet_block(items: list[tuple[str, Any]]) -> list[str]:
    lines: list[str] = []
    for label, value in items:
        if value:
            lines.append(f"- {label}: {value}")
    return lines or ["- 暂无记录"]


def render_markdown(context: dict[str, Any]) -> str:
    sections: list[str] = [
        "# Personal Context Package",
        "",
        f"- 生成时间: {context['generated_at']}",
        f"- 项目范围: {project_name(context['project_profiles'], context['filters']['project_id'])}",
        f"- 平台范围: {context['filters']['platform'] or '全部平台'}",
        "",
        "## 用户档案",
    ]

    if context["user_profiles"]:
        for user in context["user_profiles"]:
            sections.extend(
                [
                    f"### {user['display_name']}",
                    *bullet_block(
                        [
                            ("角色", user["role"]),
                            ("偏好", user["preferences"]),
                            ("沟通风格", user["communication_style"]),
                            ("长期上下文", user["long_term_context"]),
                        ]
                    ),
                    "",
                ]
            )
    else:
        sections.extend(["暂无用户档案。", ""])

    sections.append("## 项目档案")
    if context["project_profiles"]:
        for project in context["project_profiles"]:
            sections.extend(
                [
                    f"### {project['name']}",
                    *bullet_block(
                        [
                            ("目标", project["goal"]),
                            ("状态", project["status"]),
                            ("技术栈", project["stack"]),
                            ("备注", project["notes"]),
                        ]
                    ),
                    "",
                ]
            )
    else:
        sections.extend(["暂无项目档案。", ""])

    sections.append("## 问题进度")
    if context["issue_progress"]:
        for issue in context["issue_progress"]:
            sections.extend(
                [
                    f"### {issue['title']}",
                    *bullet_block(
                        [
                            ("状态", issue["state"]),
                            ("优先级", issue["priority"]),
                            ("当前进度", issue["current_step"]),
                            ("下一步", issue["next_action"]),
                            ("备注", issue["notes"]),
                        ]
                    ),
                    "",
                ]
            )
    else:
        sections.extend(["暂无问题进度。", ""])

    sections.append("## 错误记录")
    if context["error_records"]:
        for error in context["error_records"]:
            sections.extend(
                [
                    f"### {error['title']}",
                    *bullet_block(
                        [
                            ("环境", error["environment"]),
                            ("现象", error["symptom"]),
                            ("根因", error["root_cause"]),
                            ("修复", error["fix"]),
                            ("预防", error["prevention"]),
                        ]
                    ),
                    "",
                ]
            )
    else:
        sections.extend(["暂无错误记录。", ""])

    sections.append("## 平台 Prompt 模板")
    if context["prompt_templates"]:
        for template in context["prompt_templates"]:
            sections.extend(
                [
                    f"### {template['platform']} - {template['title']}",
                    template["body"] or "暂无模板内容。",
                    "",
                    *(["备注: " + template["notes"], ""] if template["notes"] else []),
                ]
            )
    else:
        sections.extend(["暂无 Prompt 模板。", ""])

    return "\n".join(sections).strip() + "\n"


def query_one(params: dict[str, list[str]], name: str) -> str | None:
    value = params.get(name, [""])[0].strip()
    return value or None


class PersonalContextHandler(BaseHTTPRequestHandler):
    server_version = "PersonalContextAgent/0.1"

    def do_GET(self) -> None:
        self.handle_request("GET")

    def do_POST(self) -> None:
        self.handle_request("POST")

    def do_PUT(self) -> None:
        self.handle_request("PUT")

    def do_DELETE(self) -> None:
        self.handle_request("DELETE")

    def handle_request(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        params = parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                self.handle_api(method, path, params)
            elif method == "GET":
                self.serve_static(path)
            else:
                raise ApiError(405, "Method not allowed")
        except ApiError as exc:
            self.send_json({"detail": exc.message}, status=exc.status)
        except json.JSONDecodeError:
            self.send_json({"detail": "Invalid JSON"}, status=400)
        except Exception as exc:
            self.send_json({"detail": str(exc)}, status=500)

    def handle_api(self, method: str, path: str, params: dict[str, list[str]]) -> None:
        if method == "GET" and path == "/api/health":
            self.send_json({"status": "ok"})
            return
        if method == "GET" and path == "/api/summary":
            self.send_json(summary())
            return
        if method == "GET" and path in ["/api/context-package", "/api/context-package/download"]:
            self.handle_context_package(path, params)
            return

        parts = [part for part in path.removeprefix("/api/").split("/") if part]
        if not parts:
            raise ApiError(404, "Not found")

        kind = parts[0]
        definition(kind)

        if len(parts) == 1 and method == "GET":
            self.send_json(list_records(kind))
            return
        if len(parts) == 1 and method == "POST":
            self.send_json(create_record(kind, self.read_json()), status=201)
            return
        if len(parts) == 2 and method == "PUT":
            self.send_json(update_record(kind, parts[1], self.read_json()))
            return
        if len(parts) == 2 and method == "DELETE":
            self.send_json(delete_record(kind, parts[1]))
            return

        raise ApiError(405, "Method not allowed")

    def handle_context_package(self, path: str, params: dict[str, list[str]]) -> None:
        output = query_one(params, "output") or "markdown"
        if output not in {"markdown", "json"}:
            raise ApiError(400, "output must be markdown or json")

        context = filtered_context(query_one(params, "project_id"), query_one(params, "platform"))
        download = path.endswith("/download")
        if output == "json":
            body = json.dumps(context, ensure_ascii=False, indent=2)
            media_type = "application/json; charset=utf-8"
            filename = "personal-context-package.json"
        else:
            body = render_markdown(context)
            media_type = "text/markdown; charset=utf-8"
            filename = "personal-context-package.md"

        headers = {}
        if download:
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        self.send_text(body, media_type=media_type, headers=headers)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ApiError(400, "JSON body must be an object")
        return data

    def serve_static(self, path: str) -> None:
        target = STATIC_DIR / "index.html" if path == "/" else STATIC_DIR / path.lstrip("/")
        resolved = target.resolve()
        static_root = STATIC_DIR.resolve()
        if not resolved.is_file() or static_root not in [resolved, *resolved.parents]:
            raise ApiError(404, "Not found")

        content = resolved.read_bytes()
        media_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        if media_type.startswith("text/") or media_type == "application/javascript":
            media_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, media_type: str, headers: dict[str, str] | None = None) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        print("%s - - [%s] %s" % (self.address_string(), self.log_date_time_string(), format % args))


def run() -> None:
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8088"))
    server = ThreadingHTTPServer((host, port), PersonalContextHandler)
    print(f"Personal Context Agent running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
