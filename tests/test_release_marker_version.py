import app


def test_git_head_uses_deploy_release_marker_without_git(tmp_path, monkeypatch):
    marker = tmp_path / ".deploy-release"
    marker.write_text("project=lvyou\ngit_sha=288636ab0123456789\n", encoding="utf-8")
    monkeypatch.setattr(app, "BASE_DIR", tmp_path)

    assert app._git_head() == "288636a"


def test_git_head_falls_back_to_dev_without_git_or_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "BASE_DIR", tmp_path)

    assert app._git_head() == "dev"
