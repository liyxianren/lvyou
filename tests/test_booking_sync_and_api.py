import copy
import json

import app as travel_app


BASE_TRIP = {
    "meta": {"current_day": "day1"},
    "days": [{"id": "day1", "day": 1, "date": "7月1日", "title": "出发", "budget": []}],
    "expenses": [],
    "bookings": [],
    "supplies": [],
}


def use_trip(tmp_path, monkeypatch, trip=None):
    data_path = tmp_path / "trip.json"
    data_path.write_text(json.dumps(trip or copy.deepcopy(BASE_TRIP), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(travel_app, "DATA_PATH", data_path)
    return data_path


def read_trip(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_confirmed_booking_adds_matching_expense(tmp_path, monkeypatch):
    data_path = use_trip(tmp_path, monkeypatch)
    client = travel_app.app.test_client()

    response = client.post("/api/bookings", json={
        "day_id": "day1",
        "type": "酒店",
        "name": "云居酒店",
        "status": "已预订",
        "price": 298,
        "notes": "携程",
    })

    assert response.status_code == 200
    trip = read_trip(data_path)
    booking = trip["bookings"][0]
    assert trip["expenses"] == [{
        "id": f"exp-booking-{booking['id']}",
        "day_id": "day1",
        "category": "酒店",
        "title": "预订：云居酒店",
        "amount": 298.0,
        "paid_at": "预订同步",
        "notes": "来自预订自动同步：携程",
        "booking_id": booking["id"],
    }]


def test_booking_status_update_to_reserved_syncs_expense_once(tmp_path, monkeypatch):
    trip = copy.deepcopy(BASE_TRIP)
    trip["bookings"] = [{
        "id": "booking-1",
        "day_id": "day1",
        "type": "景区",
        "name": "赛里木湖门票",
        "status": "待确认",
        "price": 290,
        "notes": "两人",
    }]
    data_path = use_trip(tmp_path, monkeypatch, trip)
    client = travel_app.app.test_client()

    response = client.post("/api/bookings/booking-1", json={"status": "已预订", "price": 290})
    assert response.status_code == 200
    response = client.post("/api/bookings/booking-1", json={"status": "已确认", "price": 290})
    assert response.status_code == 200

    expenses = read_trip(data_path)["expenses"]
    assert len(expenses) == 1
    assert expenses[0]["booking_id"] == "booking-1"
    assert expenses[0]["category"] == "景区"
    assert expenses[0]["amount"] == 290.0


def test_confirm_change_reserved_booking_syncs_expense(tmp_path, monkeypatch):
    data_path = use_trip(tmp_path, monkeypatch)
    client = travel_app.app.test_client()

    response = client.post("/api/confirm-change", json={
        "proposal": {"operations": [{
            "type": "add_booking",
            "label": "新增预订：云居酒店",
            "payload": {"day_id": "day1", "type": "酒店", "name": "云居酒店", "status": "已预订", "price": 298, "notes": "携程"},
        }]}
    })

    assert response.status_code == 200
    trip = read_trip(data_path)
    assert len(trip["bookings"]) == 1
    assert len(trip["expenses"]) == 1
    assert trip["expenses"][0]["booking_id"] == trip["bookings"][0]["id"]


def test_heskills_api_exposes_booking_status_and_confirm_contract(tmp_path, monkeypatch):
    use_trip(tmp_path, monkeypatch)
    client = travel_app.app.test_client()

    response = client.get("/api/heskills")

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    skill_names = {skill["name"] for skill in data["skills"]}
    assert {"parse_travel_entry", "confirm_travel_change", "manage_bookings"}.issubset(skill_names)
    manage = next(skill for skill in data["skills"] if skill["name"] == "manage_bookings")
    assert "已预订" in manage["input_schema"]["properties"]["status"]["enum"]
    assert any(endpoint["path"] == "/api/confirm-change" for endpoint in data["endpoints"])
