from pathlib import Path


def test_model_entry_forms_do_not_offer_image_uploads():
    bookings = Path("templates/bookings.html").read_text(encoding="utf-8")
    ledger = Path("templates/ledger.html").read_text(encoding="utf-8")
    app_py = Path("app.py").read_text(encoding="utf-8")

    assert 'type="file"' not in bookings
    assert 'type="file"' not in ledger
    assert "上传图片" not in app_py
    assert "image_url" not in app_py
    assert "base64" not in app_py


def test_booking_parse_prompt_requires_status_from_text():
    app_py = Path("app.py").read_text(encoding="utf-8")

    assert "用户明确说已预订/已订/订好了/已确认/取消时，必须解析到对应 status" in app_py
    assert "把用户输入或图片中的预订信息" not in app_py
