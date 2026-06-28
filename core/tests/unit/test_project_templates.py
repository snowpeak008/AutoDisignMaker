from __future__ import annotations

from core.design import project_templates


def test_delete_custom_template_removes_only_existing_custom_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(project_templates, "runtime_project_root", lambda: tmp_path)
    path = project_templates.save_custom_template(
        "重复模板",
        "indie",
        {"projectName": "重复模板", "profile": {}, "nodes": {}},
    )

    assert path.exists()
    assert project_templates.delete_custom_template("重复模板", "indie") is True
    assert not path.exists()
    assert project_templates.delete_custom_template("重复模板", "indie") is False
