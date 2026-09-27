from app.github_app import _load_private_key
from app.config import settings


def test_uses_direct_env_key_when_provided(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "github_private_key", "-----BEGIN RSA PRIVATE KEY-----\nFAKE\n-----END RSA PRIVATE KEY-----")
    assert _load_private_key() == "-----BEGIN RSA PRIVATE KEY-----\nFAKE\n-----END RSA PRIVATE KEY-----"


def test_falls_back_to_file_when_no_direct_key(monkeypatch, tmp_path):
    key_file = tmp_path / "key.pem"
    key_file.write_text("contenu-du-fichier-pem")

    monkeypatch.setattr(settings, "github_private_key", None)
    monkeypatch.setattr(settings, "github_private_key_path", str(key_file))

    assert _load_private_key() == "contenu-du-fichier-pem"
