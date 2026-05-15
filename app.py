import copy
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from markdown import markdown
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "trip.json"
CONTENT_DIR = BASE_DIR / "content"


def _git_head() -> str:
    """Return short git HEAD hash, or 'dev' if not available."""
    try:
        import subprocess
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(BASE_DIR),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "dev"


def load_day_markdown(day_id):
    """Load markdown content for a day and convert to HTML."""
    md_file = CONTENT_DIR / f"{day_id}.md"
    if not md_file.exists():
        return None
    text = md_file.read_text(encoding="utf-8")
    return markdown(
        text,
        extensions=["tables", "fenced_code", "codehilite", "toc", "nl2br"],
        output_format="html5",
    )

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


@app.context_processor
def inject_static_version():
    return {"static_version": _git_head()}


@app.after_request
def no_cache(response):
    """Force no-cache on all HTML pages so browsers always fetch fresh."""
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

BOOKING_STATUSES = {"待定", "待确认", "已预订", "已确认", "取消"}
SUPPLY_STATUSES = {"待购买", "已购买", "不买", "备用"}
BOOKING_STATUS_ALIASES = {
    "pending": "待定",
    "todo": "待定",
    "need_confirm": "待确认",
    "reserved": "已预订",
    "booked": "已预订",
    "confirmed": "已确认",
    "cancelled": "取消",
    "canceled": "取消",
}
SUPPLY_STATUS_ALIASES = {
    "todo": "待购买",
    "pending": "待购买",
    "bought": "已购买",
    "purchased": "已购买",
    "skip": "不买",
    "backup": "备用",
}


def load_trip():
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_trip(trip):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(trip, f, ensure_ascii=False, indent=2)
        f.write("\n")


def get_day(trip, day_id):
    return next((day for day in trip.get("days", []) if day["id"] == day_id), None)


def budget_bounds(day):
    items = day.get("budget", [])
    return {
        "min": sum(int(item.get("min", 0)) for item in items),
        "max": sum(int(item.get("max", 0)) for item in items),
    }


def actual_total(trip, day_id=None):
    expenses = trip.get("expenses", [])
    if day_id:
        expenses = [item for item in expenses if item.get("day_id") == day_id]
    return sum(float(item.get("amount", 0)) for item in expenses)


def json_payload():
    return request.get_json(force=True, silent=True) or {}


def make_expense(payload, trip):
    return {
        "id": payload.get("id") or f"exp-{uuid.uuid4().hex[:8]}",
        "day_id": payload.get("day_id", trip["meta"].get("current_day", "day1")),
        "category": str(payload.get("category", "其他")).strip() or "其他",
        "title": str(payload.get("title", "未命名支出")).strip() or "未命名支出",
        "amount": float(payload.get("amount", 0)),
        "paid_at": payload.get("paid_at") or datetime.now().strftime("%Y-%m-%d %H:%M"),
        "notes": str(payload.get("notes", "")).strip(),
    }


def normalize_booking_status(value, default="待定"):
    value = str(value or "").strip()
    if value in BOOKING_STATUSES:
        return value
    return BOOKING_STATUS_ALIASES.get(value.lower(), default)


def normalize_supply_status(value, default="待购买"):
    value = str(value or "").strip()
    if value in SUPPLY_STATUSES:
        return value
    return SUPPLY_STATUS_ALIASES.get(value.lower(), default)


def make_booking(payload, trip):
    return {
        "id": payload.get("id") or f"booking-{uuid.uuid4().hex[:8]}",
        "type": str(payload.get("type", "其他")).strip() or "其他",
        "name": str(payload.get("name", "未命名预订")).strip() or "未命名预订",
        "day_id": payload.get("day_id", trip["meta"].get("current_day", "day1")),
        "status": normalize_booking_status(payload.get("status", "待定")),
        "price": float(payload.get("price") or 0),
        "notes": str(payload.get("notes", "")).strip(),
    }


def booking_is_accountable(booking):
    return booking.get("status") in {"已预订", "已确认"} and float(booking.get("price") or 0) > 0


def sync_booking_expense(trip, booking):
    if not booking_is_accountable(booking):
        return None
    expense_id = f"exp-booking-{booking['id']}"
    expense = next((item for item in trip.setdefault("expenses", []) if item.get("booking_id") == booking["id"]), None)
    notes = f"来自预订自动同步：{booking.get('notes', '')}".rstrip("：")
    payload = {
        "id": expense_id,
        "day_id": booking.get("day_id", trip["meta"].get("current_day", "day1")),
        "category": booking.get("type", "预订"),
        "title": f"预订：{booking.get('name', '未命名预订')}",
        "amount": float(booking.get("price") or 0),
        "paid_at": "预订同步",
        "notes": notes,
        "booking_id": booking["id"],
    }
    if expense:
        expense.update(payload)
    else:
        expense = payload
        trip.setdefault("expenses", []).append(expense)
    return expense


def make_supply(payload):
    return {
        "id": payload.get("id") or f"s-{uuid.uuid4().hex[:8]}",
        "name": str(payload.get("name", "未命名物品")).strip() or "未命名物品",
        "quantity": str(payload.get("quantity", "适量")).strip() or "适量",
        "category": str(payload.get("category", "其他")).strip() or "其他",
        "status": normalize_supply_status(payload.get("status", "待购买")),
    }


def dashboard_context():
    trip = load_trip()
    current_day = get_day(trip, trip["meta"].get("current_day", "day1")) or trip["days"][0]
    bounds = budget_bounds(current_day)
    actual = actual_total(trip, current_day["id"])
    return trip, current_day, bounds, actual


@app.route("/")
def index():
    trip, current_day, bounds, actual = dashboard_context()
    return render_template(
        "index.html",
        trip=trip,
        day=current_day,
        bounds=bounds,
        actual=actual,
        total_actual=actual_total(trip),
    )


@app.route("/itinerary")
def itinerary():
    trip = load_trip()
    return render_template("itinerary.html", trip=trip)


@app.route("/day/<day_id>")
def day_detail(day_id):
    trip = load_trip()
    day = get_day(trip, day_id)
    if not day:
        return redirect(url_for("index"))
    day_md = load_day_markdown(day_id)
    return render_template(
        "day.html",
        trip=trip,
        day=day,
        bounds=budget_bounds(day),
        actual=actual_total(trip, day_id),
        day_md=day_md,
    )


@app.route("/ledger")
def ledger():
    trip = load_trip()
    selected_day_id = request.args.get("day_id") or trip["meta"].get("current_day", "day1")
    days_by_id = {day["id"]: day for day in trip.get("days", [])}
    expenses = [item for item in trip.get("expenses", []) if item.get("day_id") == selected_day_id]
    return render_template(
        "ledger.html",
        trip=trip,
        days_by_id=days_by_id,
        selected_day_id=selected_day_id,
        selected_day=days_by_id.get(selected_day_id),
        expenses=expenses,
        selected_actual=actual_total(trip, selected_day_id),
        total_actual=actual_total(trip),
    )


@app.route("/bookings")
def bookings():
    trip = load_trip()
    selected_day_id = request.args.get("day_id") or trip["meta"].get("current_day", "day1")
    days_by_id = {day["id"]: day for day in trip.get("days", [])}
    day_bookings = [item for item in trip.get("bookings", []) if item.get("day_id") == selected_day_id]
    return render_template(
        "bookings.html",
        trip=trip,
        statuses=sorted(BOOKING_STATUSES),
        selected_day_id=selected_day_id,
        selected_day=days_by_id.get(selected_day_id),
        bookings=day_bookings,
    )


@app.route("/assistant")
def assistant():
    trip = load_trip()
    return render_template("assistant.html", trip=trip)


@app.get("/api/trip")
def api_trip():
    return jsonify(load_trip())


@app.get("/api/days")
def api_days_list():
    trip = load_trip()
    return jsonify({"ok": True, "days": trip.get("days", [])})


@app.get("/api/days/<day_id>")
def api_days_get(day_id):
    trip = load_trip()
    day = get_day(trip, day_id)
    if not day:
        return jsonify({"ok": False, "error": "未找到该行程日"}), 404
    return jsonify({"ok": True, "day": day, "actual_total": actual_total(trip, day_id), "budget": budget_bounds(day)})


@app.post("/api/days/<day_id>")
def api_days_update(day_id):
    trip = load_trip()
    payload = json_payload()
    day = get_day(trip, day_id)
    if not day:
        return jsonify({"ok": False, "error": "未找到该行程日"}), 404

    for key in ["title", "route", "summary", "next_action", "risk_level", "lodging_city"]:
        if key in payload:
            day[key] = payload[key]
    if "risks" in payload and isinstance(payload["risks"], list):
        day["risks"] = payload["risks"]
    if "timeline" in payload and isinstance(payload["timeline"], list):
        day["timeline"] = payload["timeline"]
    if "budget" in payload and isinstance(payload["budget"], list):
        day["budget"] = payload["budget"]
    save_trip(trip)
    return jsonify({"ok": True, "day": day})


@app.post("/api/days/<day_id>/timeline")
def api_days_add_timeline(day_id):
    trip = load_trip()
    payload = json_payload()
    day = get_day(trip, day_id)
    if not day:
        return jsonify({"ok": False, "error": "未找到该行程日"}), 404
    item = {
        "id": payload.get("id") or f"t-{uuid.uuid4().hex[:6]}",
        "time": str(payload.get("time", "")).strip(),
        "title": str(payload.get("title", "新增安排")).strip() or "新增安排",
        "detail": str(payload.get("detail", "")).strip(),
    }
    day.setdefault("timeline", []).append(item)
    save_trip(trip)
    return jsonify({"ok": True, "timeline_item": item, "day": day})


@app.get("/api/expenses")
def api_expenses_list():
    trip = load_trip()
    day_id = request.args.get("day_id")
    expenses = trip.get("expenses", [])
    if day_id:
        expenses = [item for item in expenses if item.get("day_id") == day_id]
    return jsonify({"ok": True, "expenses": expenses, "total": actual_total(trip, day_id)})


@app.post("/api/expenses")
def api_expenses():
    trip = load_trip()
    payload = json_payload()
    action = payload.get("action")

    if not action:
        item = make_expense(payload, trip)
        trip.setdefault("expenses", []).append(item)
        save_trip(trip)
        return jsonify({"ok": True, "expense": item})

    if action == "add":
        expense = payload.get("expense", {})
        item = make_expense(expense, trip)
        trip.setdefault("expenses", []).append(item)
        save_trip(trip)
        return jsonify({"ok": True, "expense": item})

    expense_id = payload.get("id")
    expenses = trip.setdefault("expenses", [])
    target = next((item for item in expenses if item.get("id") == expense_id), None)
    if not target:
        return jsonify({"ok": False, "error": "未找到该支出"}), 404

    if action == "delete":
        trip["expenses"] = [item for item in expenses if item.get("id") != expense_id]
        save_trip(trip)
        return jsonify({"ok": True})

    if action == "edit":
        changes = payload.get("expense", {})
        for key in ["day_id", "category", "title", "notes", "paid_at"]:
            if key in changes:
                target[key] = str(changes[key]).strip()
        if "amount" in changes:
            target["amount"] = float(changes["amount"])
        save_trip(trip)
        return jsonify({"ok": True, "expense": target})

    return jsonify({"ok": False, "error": "不支持的操作"}), 400


@app.get("/api/expenses/<expense_id>")
def api_expense_get(expense_id):
    trip = load_trip()
    expense = next((item for item in trip.get("expenses", []) if item.get("id") == expense_id), None)
    if not expense:
        return jsonify({"ok": False, "error": "未找到该支出"}), 404
    return jsonify({"ok": True, "expense": expense})


@app.put("/api/expenses/<expense_id>")
@app.post("/api/expenses/<expense_id>")
def api_expense_update(expense_id):
    trip = load_trip()
    payload = json_payload()
    expense = next((item for item in trip.get("expenses", []) if item.get("id") == expense_id), None)
    if not expense:
        return jsonify({"ok": False, "error": "未找到该支出"}), 404
    for key in ["day_id", "category", "title", "notes", "paid_at"]:
        if key in payload:
            expense[key] = str(payload[key]).strip()
    if "amount" in payload:
        expense["amount"] = float(payload["amount"])
    save_trip(trip)
    return jsonify({"ok": True, "expense": expense})


@app.delete("/api/expenses/<expense_id>")
@app.post("/api/expenses/<expense_id>/delete")
def api_expense_delete(expense_id):
    trip = load_trip()
    before = len(trip.get("expenses", []))
    trip["expenses"] = [item for item in trip.get("expenses", []) if item.get("id") != expense_id]
    if len(trip["expenses"]) == before:
        return jsonify({"ok": False, "error": "未找到该支出"}), 404
    save_trip(trip)
    return jsonify({"ok": True})


@app.get("/api/bookings")
def api_bookings_list():
    trip = load_trip()
    day_id = request.args.get("day_id")
    bookings = trip.get("bookings", [])
    if day_id:
        bookings = [item for item in bookings if item.get("day_id") == day_id]
    return jsonify({"ok": True, "bookings": bookings})


@app.get("/api/bookings/<booking_id>")
def api_booking_get(booking_id):
    trip = load_trip()
    booking = next((item for item in trip.get("bookings", []) if item.get("id") == booking_id), None)
    if not booking:
        return jsonify({"ok": False, "error": "未找到该预订"}), 404
    return jsonify({"ok": True, "booking": booking})


@app.put("/api/bookings/<booking_id>")
@app.post("/api/bookings/<booking_id>")
def api_update_booking(booking_id):
    trip = load_trip()
    payload = json_payload()
    booking = next((item for item in trip.get("bookings", []) if item.get("id") == booking_id), None)
    if not booking:
        return jsonify({"ok": False, "error": "未找到该预订"}), 404

    status = payload.get("status")
    if status is not None:
        booking["status"] = normalize_booking_status(status, booking.get("status", "待定"))
    if "price" in payload and payload["price"] != "":
        booking["price"] = float(payload["price"])
    if "notes" in payload:
        booking["notes"] = str(payload["notes"]).strip()
    sync_booking_expense(trip, booking)
    save_trip(trip)
    return jsonify({"ok": True, "booking": booking})


@app.post("/api/bookings")
def api_add_booking():
    trip = load_trip()
    payload = json_payload()
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"ok": False, "error": "预订名称不能为空"}), 400

    booking = make_booking(payload, trip)
    trip.setdefault("bookings", []).append(booking)
    sync_booking_expense(trip, booking)
    save_trip(trip)
    return jsonify({"ok": True, "booking": booking})


@app.delete("/api/bookings/<booking_id>")
@app.post("/api/bookings/<booking_id>/delete")
def api_delete_booking(booking_id):
    trip = load_trip()
    before = len(trip.get("bookings", []))
    trip["bookings"] = [item for item in trip.get("bookings", []) if item.get("id") != booking_id]
    if len(trip["bookings"]) == before:
        return jsonify({"ok": False, "error": "未找到该预订"}), 404
    save_trip(trip)
    return jsonify({"ok": True})


@app.get("/api/supplies")
def api_supplies_list():
    trip = load_trip()
    status = request.args.get("status")
    supplies = trip.get("supplies", [])
    if status:
        supplies = [item for item in supplies if item.get("status") == status]
    return jsonify({"ok": True, "supplies": supplies})


@app.post("/api/supplies")
def api_add_supply():
    trip = load_trip()
    payload = json_payload()
    item = make_supply(payload)
    trip.setdefault("supplies", []).append(item)
    save_trip(trip)
    return jsonify({"ok": True, "supply": item})


@app.get("/api/supplies/<supply_id>")
def api_supply_get(supply_id):
    trip = load_trip()
    item = next((s for s in trip.get("supplies", []) if s.get("id") == supply_id), None)
    if not item:
        return jsonify({"ok": False, "error": "未找到该物品"}), 404
    return jsonify({"ok": True, "supply": item})


@app.put("/api/supplies/<supply_id>")
@app.post("/api/supplies/<supply_id>")
def api_update_supply(supply_id):
    trip = load_trip()
    payload = json_payload()
    item = next((s for s in trip.get("supplies", []) if s.get("id") == supply_id), None)
    if not item:
        return jsonify({"ok": False, "error": "未找到该物品"}), 404
    status = payload.get("status")
    if status is not None:
        item["status"] = normalize_supply_status(status, item.get("status", "待购买"))
    if "quantity" in payload:
        item["quantity"] = str(payload["quantity"]).strip()
    if "name" in payload:
        item["name"] = str(payload["name"]).strip()
    if "category" in payload:
        item["category"] = str(payload["category"]).strip()
    save_trip(trip)
    return jsonify({"ok": True, "supply": item})


@app.get("/api/heskills")
def api_heskills():
    return jsonify({
        "ok": True,
        "name": "lvyou-travel-api",
        "description": "旅行执行网站 API 技能清单。所有写入类变更应先生成 proposal，再由 /api/confirm-change 确认写入。",
        "skills": [
            {
                "name": "parse_travel_entry",
                "description": "把自然语言文本解析为账本或预订 proposal；不支持图片解析。",
                "method": "POST",
                "path": "/api/ai/parse-entry",
                "content_type": "multipart/form-data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "mode": {"type": "string", "enum": ["expense", "booking"]},
                        "day_id": {"type": "string"},
                        "text": {"type": "string"},
                    },
                    "required": ["mode", "text"],
                },
            },
            {
                "name": "confirm_travel_change",
                "description": "确认模型生成的 proposal 并写入旅行数据。",
                "method": "POST",
                "path": "/api/confirm-change",
                "content_type": "application/json",
                "input_schema": {"type": "object", "properties": {"proposal": {"type": "object"}}, "required": ["proposal"]},
            },
            {
                "name": "manage_bookings",
                "description": "新增、查询、修改、删除预订；状态为已预订/已确认且价格大于 0 时自动同步账本。",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "paths": ["/api/bookings", "/api/bookings/<booking_id>"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "day_id": {"type": "string"},
                        "type": {"type": "string"},
                        "name": {"type": "string"},
                        "status": {"type": "string", "enum": sorted(BOOKING_STATUSES)},
                        "price": {"type": "number"},
                        "notes": {"type": "string"},
                    },
                },
            },
            {
                "name": "manage_expenses",
                "description": "查询、新增、修改、删除账本支出。",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "paths": ["/api/expenses", "/api/expenses/<expense_id>"],
            },
            {
                "name": "manage_supplies",
                "description": "查询、新增、修改、删除全局物资。",
                "methods": ["GET", "POST", "PUT", "DELETE"],
                "paths": ["/api/supplies", "/api/supplies/<supply_id>"],
            },
        ],
        "endpoints": [
            {"method": "GET", "path": "/api/trip"},
            {"method": "POST", "path": "/api/ai/parse-entry"},
            {"method": "POST", "path": "/api/ai/propose"},
            {"method": "POST", "path": "/api/confirm-change"},
            {"method": "GET/POST", "path": "/api/bookings"},
            {"method": "GET/POST/PUT/DELETE", "path": "/api/bookings/<booking_id>"},
            {"method": "GET/POST", "path": "/api/expenses"},
            {"method": "GET/POST/PUT/DELETE", "path": "/api/expenses/<expense_id>"},
            {"method": "GET/POST", "path": "/api/supplies"},
            {"method": "GET/POST/PUT/DELETE", "path": "/api/supplies/<supply_id>"},
        ],
    })


@app.get("/api/skills")
def api_skills_alias():
    return api_heskills()


@app.delete("/api/supplies/<supply_id>")
@app.post("/api/supplies/<supply_id>/delete")
def api_delete_supply(supply_id):
    trip = load_trip()
    before = len(trip.get("supplies", []))
    trip["supplies"] = [item for item in trip.get("supplies", []) if item.get("id") != supply_id]
    if len(trip["supplies"]) == before:
        return jsonify({"ok": False, "error": "未找到该物品"}), 404
    save_trip(trip)
    return jsonify({"ok": True})


AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_add_expense",
            "description": "为用户新增一笔真实支出，必须等待用户确认后才会写入。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day_id": {"type": "string", "description": "如 day1"},
                    "category": {"type": "string", "description": "午餐、酒店、补给、油费、门票等"},
                    "title": {"type": "string"},
                    "amount": {"type": "number"},
                    "notes": {"type": "string"}
                },
                "required": ["day_id", "category", "title", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_booking",
            "description": "修改酒店、餐厅、租车、景区等预订状态或备注。",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_id": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(BOOKING_STATUSES)},
                    "price": {"type": "number"},
                    "notes": {"type": "string"}
                },
                "required": ["booking_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_supply",
            "description": "修改采购清单中的物品数量或购买状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "supply_id": {"type": "string"},
                    "status": {"type": "string", "enum": sorted(SUPPLY_STATUSES)},
                    "quantity": {"type": "string"},
                    "notes": {"type": "string"}
                },
                "required": ["supply_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "propose_update_itinerary",
            "description": "修改某一天的行程说明、下一步动作或风险提醒。",
            "parameters": {
                "type": "object",
                "properties": {
                    "day_id": {"type": "string"},
                    "field": {"type": "string", "enum": ["next_action", "summary", "add_risk", "add_timeline"]},
                    "value": {"type": "string"},
                    "time": {"type": "string"},
                    "title": {"type": "string"},
                    "detail": {"type": "string"}
                },
                "required": ["day_id", "field"]
            }
        }
    }
]


def compact_trip_for_ai(trip):
    return {
        "meta": trip.get("meta", {}),
        "days": [
            {
                "id": day.get("id"),
                "date": day.get("date"),
                "title": day.get("title"),
                "next_action": day.get("next_action"),
                "risks": day.get("risks", []),
            }
            for day in trip.get("days", [])
        ],
        "bookings": trip.get("bookings", []),
        "supplies": trip.get("supplies", []),
        "expenses": trip.get("expenses", [])[-20:],
    }


def tool_call_to_operation(name, args):
    if name == "propose_add_expense":
        return {
            "type": "add_expense",
            "label": f"新增支出：{args.get('title')} ¥{args.get('amount')}",
            "payload": {
                "day_id": args.get("day_id", "day1"),
                "category": args.get("category", "其他"),
                "title": args.get("title", "未命名支出"),
                "amount": float(args.get("amount", 0)),
                "notes": args.get("notes", "")
            },
        }
    if name == "propose_update_booking":
        changes = {k: v for k, v in args.items() if k in {"status", "price", "notes"} and v is not None}
        return {
            "type": "update_booking",
            "label": f"修改预订：{args.get('booking_id')}",
            "payload": {"booking_id": args.get("booking_id"), "changes": changes},
        }
    if name == "propose_update_supply":
        changes = {k: v for k, v in args.items() if k in {"status", "quantity", "notes"} and v is not None}
        return {
            "type": "update_supply",
            "label": f"修改采购：{args.get('supply_id')}",
            "payload": {"supply_id": args.get("supply_id"), "changes": changes},
        }
    if name == "propose_update_itinerary":
        return {
            "type": "update_itinerary",
            "label": f"修改行程：{args.get('day_id')} / {args.get('field')}",
            "payload": args,
        }
    return None


def extract_json_object(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def model_parse_entry(mode, day_id, user_text):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY。请在环境变量或 .env 中设置后重启 Flask。")

    trip = load_trip()
    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    current_day = get_day(trip, day_id) or get_day(trip, trip["meta"].get("current_day", "day1"))

    if mode == "expense":
        schema_hint = {
            "category": "午餐/晚餐/补给/油费/过路费/酒店/门票/停车/其他",
            "title": "简短名称",
            "amount": 0,
            "notes": "可空"
        }
        task = "把用户输入中的消费信息解析成一笔账本记录。金额必须是数字；没有金额时 amount 为 0。"
    elif mode == "booking":
        schema_hint = {
            "type": "酒店/餐厅/景区/租车/交通/其他",
            "name": "预订对象名称",
            "status": "待定/待确认/已预订/已确认/取消",
            "price": 0,
            "notes": "平台、地址、取消规则、截图中有用信息，可空"
        }
        task = "把用户输入中的预订信息解析成一条预订记录。价格必须是数字；没有价格时 price 为 0。用户明确说已预订/已订/订好了/已确认/取消时，必须解析到对应 status。"
    else:
        raise ValueError("不支持的解析类型")

    prompt = (
        f"{task}\n"
        f"用户选择的日期 day_id={day_id}，日期信息：{current_day.get('date') if current_day else day_id}。\n"
        f"用户文本：{user_text or '无'}\n"
        "只返回一个 JSON 对象，不要解释，不要 Markdown。\n"
        f"JSON 字段必须严格匹配：{json.dumps(schema_hint, ensure_ascii=False)}\n"
        "不要编造已付款、已预订、已确认等事实；只有用户明确说了才使用这些状态。"
    )

    response = client.chat.completions.create(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        messages=[
            {"role": "system", "content": "你是旅行网站的数据录入解析器，输出必须是严格 JSON。"},
            {"role": "user", "content": prompt},
        ],
        stream=False,
    )
    parsed = extract_json_object(response.choices[0].message.content)

    if mode == "expense":
        return {
            "type": "add_expense",
            "label": f"新增支出：{parsed.get('title', '未命名支出')} ¥{parsed.get('amount', 0)}",
            "payload": {
                "day_id": day_id,
                "category": str(parsed.get("category", "其他")).strip() or "其他",
                "title": str(parsed.get("title", "未命名支出")).strip() or "未命名支出",
                "amount": float(parsed.get("amount") or 0),
                "notes": str(parsed.get("notes", "")).strip(),
            },
        }

    status = str(parsed.get("status", "待定")).strip()
    return {
        "type": "add_booking",
        "label": f"新增预订：{parsed.get('name', '未命名预订')}",
        "payload": {
            "day_id": day_id,
            "type": str(parsed.get("type", "其他")).strip() or "其他",
            "name": str(parsed.get("name", "未命名预订")).strip() or "未命名预订",
            "status": normalize_booking_status(status),
            "price": float(parsed.get("price") or 0),
            "notes": str(parsed.get("notes", "")).strip(),
        },
    }


@app.post("/api/ai/parse-entry")
def api_ai_parse_entry():
    mode = request.form.get("mode", "").strip()
    day_id = request.form.get("day_id", "day1").strip() or "day1"
    user_text = request.form.get("text", "").strip()
    if not user_text:
        return jsonify({"ok": False, "error": "请输入文字"}), 400
    try:
        operation = model_parse_entry(mode, day_id, user_text)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"模型解析失败：{exc}"}), 502
    return jsonify({
        "ok": True,
        "proposal": {
            "summary": "模型已解析为以下记录，确认后写入。",
            "operations": [operation]
        }
    })


@app.post("/api/ai/propose")
def api_ai_propose():
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        return jsonify({
            "ok": False,
            "error": "未配置 DEEPSEEK_API_KEY。请在环境变量或 .env 中设置后重启 Flask。"
        }), 400

    payload = request.get_json(force=True)
    user_message = payload.get("message", "").strip()
    if not user_message:
        return jsonify({"ok": False, "error": "请输入要调整的内容"}), 400

    trip = load_trip()
    client = OpenAI(
        api_key=api_key,
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    system = (
        "你是旅行执行网站的结构化修改助手。只能根据给定 JSON 数据提出修改建议。"
        "不要编造已预订、已付款、已购买等事实；除非用户明确说已经发生。"
        "你必须通过 tools 生成待确认修改，不要直接声称已经改好。"
    )
    try:
        response = client.chat.completions.create(
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": "当前旅行 JSON：\n" + json.dumps(compact_trip_for_ai(trip), ensure_ascii=False)},
                {"role": "user", "content": user_message},
            ],
            tools=AI_TOOLS,
            tool_choice="auto",
            stream=False,
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": f"模型调用失败：{exc}"}), 502

    message = response.choices[0].message
    operations = []
    for call in getattr(message, "tool_calls", None) or []:
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            continue
        operation = tool_call_to_operation(call.function.name, args)
        if operation:
            operations.append(operation)

    if not operations:
        return jsonify({
            "ok": True,
            "proposal": {
                "summary": message.content or "模型没有生成可执行修改。",
                "operations": []
            }
        })

    return jsonify({
        "ok": True,
        "proposal": {
            "summary": "以下修改需要你确认后才会写入数据。",
            "operations": operations
        }
    })


@app.post("/api/confirm-change")
def api_confirm_change():
    trip = load_trip()
    payload = request.get_json(force=True)
    proposal = payload.get("proposal", {})
    operations = proposal.get("operations", [])
    if not isinstance(operations, list):
        return jsonify({"ok": False, "error": "无效的变更格式"}), 400

    updated = copy.deepcopy(trip)
    applied = []
    for op in operations:
        op_type = op.get("type")
        data = op.get("payload", {})
        if op_type == "add_expense":
            item = {
                "id": f"exp-{uuid.uuid4().hex[:8]}",
                "day_id": data.get("day_id", "day1"),
                "category": data.get("category", "其他"),
                "title": data.get("title", "未命名支出"),
                "amount": float(data.get("amount", 0)),
                "paid_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "notes": data.get("notes", "")
            }
            updated.setdefault("expenses", []).append(item)
            applied.append(op.get("label", "新增支出"))
        elif op_type == "add_booking":
            item = {
                "id": f"booking-{uuid.uuid4().hex[:8]}",
                "type": data.get("type", "其他"),
                "name": data.get("name", "未命名预订"),
                "day_id": data.get("day_id", "day1"),
                "status": data.get("status", "待定") if data.get("status") in BOOKING_STATUSES else "待定",
                "price": float(data.get("price", 0)),
                "notes": data.get("notes", "")
            }
            updated.setdefault("bookings", []).append(item)
            sync_booking_expense(updated, item)
            applied.append(op.get("label", "新增预订"))
        elif op_type == "update_booking":
            booking = next((b for b in updated.get("bookings", []) if b.get("id") == data.get("booking_id")), None)
            if not booking:
                continue
            for key, value in data.get("changes", {}).items():
                if key == "status":
                    booking[key] = normalize_booking_status(value, booking.get("status", "待定"))
                elif key in {"price", "notes"}:
                    booking[key] = value
            sync_booking_expense(updated, booking)
            applied.append(op.get("label", "修改预订"))
        elif op_type == "update_supply":
            supply = next((s for s in updated.get("supplies", []) if s.get("id") == data.get("supply_id")), None)
            if not supply:
                continue
            for key, value in data.get("changes", {}).items():
                if key == "status":
                    supply[key] = normalize_supply_status(value, supply.get("status", "待购买"))
                elif key in {"quantity", "notes"}:
                    supply[key] = value
            applied.append(op.get("label", "修改采购"))
        elif op_type == "update_itinerary":
            day = get_day(updated, data.get("day_id", "day1"))
            if not day:
                continue
            field = data.get("field")
            if field in {"next_action", "summary"}:
                day[field] = data.get("value", "")
            elif field == "add_risk" and data.get("value"):
                day.setdefault("risks", []).append(data["value"])
            elif field == "add_timeline":
                day.setdefault("timeline", []).append({
                    "id": f"t-{uuid.uuid4().hex[:6]}",
                    "time": data.get("time", ""),
                    "title": data.get("title", "新增安排"),
                    "detail": data.get("detail") or data.get("value", "")
                })
            applied.append(op.get("label", "修改行程"))

    save_trip(updated)
    return jsonify({"ok": True, "applied": applied, "trip": updated})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
