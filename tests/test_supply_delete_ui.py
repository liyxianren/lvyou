from pathlib import Path


def test_bookings_template_has_supply_delete_button():
    html = Path("templates/bookings.html").read_text(encoding="utf-8")
    assert 'data-delete-supply="{{ item.id }}"' in html
    assert "删除这个物资？" in Path("static/app.js").read_text(encoding="utf-8")
