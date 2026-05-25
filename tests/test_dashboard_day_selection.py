import copy
import json

import app as travel_app


BASE_TRIP = {
    "meta": {"trip_year": 2026, "current_day": "day1", "total_budget": 10000},
    "days": [
        {
            "id": "day1",
            "day": 1,
            "date": "6 月 11 日",
            "title": "Day1 正式出发",
            "route": "机场 -> 安集海",
            "summary": "Day1 summary",
            "next_action": "Day1 action",
            "drive": {"time": "5小时", "toll_yuan": 100},
            "budget": [],
            "risks": [],
            "timeline": [],
        },
        {
            "id": "day2",
            "day": 2,
            "date": "6 月 12 日",
            "title": "Day2 赛里木湖",
            "route": "精河 -> 赛里木湖",
            "summary": "Day2 summary",
            "next_action": "Day2 action",
            "drive": {"time": "4小时", "toll_yuan": 80},
            "budget": [],
            "risks": [],
            "timeline": [],
        },
    ],
    "expenses": [],
    "bookings": [],
    "supplies": [
        {"id": "prep-id-card", "name": "身份证", "quantity": "2 人原件", "category": "01 证件支付", "status": "待购买"}
    ],
}


def use_trip(tmp_path, monkeypatch, trip=None):
    data_path = tmp_path / "trip.json"
    data_path.write_text(json.dumps(trip or copy.deepcopy(BASE_TRIP), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(travel_app, "DATA_PATH", data_path)
    return data_path


def test_dashboard_shows_day0_before_trip_start(tmp_path, monkeypatch):
    use_trip(tmp_path, monkeypatch)
    client = travel_app.app.test_client()

    response = client.get("/?date=2026-05-25")

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Day0 出发准备" in html
    assert "今日要完成" in html
    assert "身份证" in html
    assert 'href="/day/day0"' not in html
    assert "Day1 正式出发" not in html


def test_dashboard_shows_matching_trip_day_by_date(tmp_path, monkeypatch):
    use_trip(tmp_path, monkeypatch)
    client = travel_app.app.test_client()

    day1 = client.get("/?date=2026-06-11").get_data(as_text=True)
    day2 = client.get("/?date=2026-06-12").get_data(as_text=True)

    assert "Day1 正式出发" in day1
    assert "Day0 出发准备" not in day1
    assert "Day2 赛里木湖" in day2
