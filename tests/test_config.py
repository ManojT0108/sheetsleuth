from app.config import Settings


def test_butterbase_key_does_not_enable_product_mirrors_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("BUTTERBASE_API_KEY", "bb_sk_test")
    monkeypatch.delenv("SHEETSLEUTH_BUTTERBASE_ENABLED", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text("")

    settings = Settings.from_env(env_file)

    assert settings.butterbase_enabled is False


def test_butterbase_product_mirrors_are_explicit_opt_in(monkeypatch, tmp_path):
    monkeypatch.setenv("BUTTERBASE_API_KEY", "bb_sk_test")
    monkeypatch.setenv("SHEETSLEUTH_BUTTERBASE_ENABLED", "1")
    env_file = tmp_path / ".env"
    env_file.write_text("")

    settings = Settings.from_env(env_file)

    assert settings.butterbase_enabled is True
