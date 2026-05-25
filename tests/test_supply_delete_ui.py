from pathlib import Path


def test_bookings_template_has_supply_delete_button():
    html = Path("templates/bookings.html").read_text(encoding="utf-8")
    assert 'data-delete-supply="{{ item.id }}"' in html
    assert "删除这个物资？" in Path("static/app.js").read_text(encoding="utf-8")


def test_supply_checkboxes_persist_status_from_itinerary_and_bookings():
    itinerary = Path("templates/itinerary.html").read_text(encoding="utf-8")
    bookings = Path("templates/bookings.html").read_text(encoding="utf-8")
    script = Path("static/app.js").read_text(encoding="utf-8")

    assert 'data-supply-toggle="{{ item.id }}"' in itinerary
    assert 'data-supply-toggle="{{ item.id }}"' in bookings
    assert 'input.checked ? "已购买" : "待购买"' in script
    assert "/api/supplies/${input.dataset.supplyToggle}" in script
