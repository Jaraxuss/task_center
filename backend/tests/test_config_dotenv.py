from __future__ import annotations

import importlib


def test_config_reads_backend_dotenv_when_process_env_missing(monkeypatch) -> None:
    for key in (
        "TASK_CENTER_FEISHU_APP_ID",
        "TASK_CENTER_FEISHU_APP_SECRET",
        "TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID",
        "TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE",
    ):
        monkeypatch.delenv(key, raising=False)

    import config

    reloaded = importlib.reload(config)
    settings = reloaded.get_settings()

    assert settings.feishu_app_id
    assert settings.feishu_app_secret
    assert settings.feishu_default_receive_id
    assert settings.feishu_default_receive_id_type == "open_id"
