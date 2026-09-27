from app.diff_parser import FileChange, Hunk, filter_irrelevant_files
from app.secret_redactor import is_sensitive_file, redact_secrets


def test_env_files_are_sensitive():
    assert is_sensitive_file(".env")
    assert is_sensitive_file(".env.production")
    assert is_sensitive_file("config/.env.local")


def test_private_key_files_are_sensitive():
    assert is_sensitive_file("keys/server.pem")
    assert is_sensitive_file("id_rsa")
    assert is_sensitive_file("app.key")


def test_normal_source_files_are_not_sensitive():
    assert not is_sensitive_file("app/main.py")
    assert not is_sensitive_file("src/index.ts")


def test_redact_secrets_masks_value_but_keeps_key_visible():
    line = 'password = "SuperSecretValue123"'
    result = redact_secrets(line)
    assert "SuperSecretValue123" not in result
    assert "password" in result
    assert "[REDACTED]" in result


def test_redact_secrets_leaves_normal_code_untouched():
    line = "def compute_total(price, quantity):"
    assert redact_secrets(line) == line


def test_filter_irrelevant_files_also_excludes_sensitive_files():
    files = [
        FileChange(filename="app/main.py", hunks=[Hunk(header="@@", new_start=1, content="+x=1")]),
        FileChange(filename=".env", hunks=[Hunk(header="@@", new_start=1, content="+SECRET=abc")]),
        FileChange(filename="secrets.yaml", hunks=[Hunk(header="@@", new_start=1, content="+key: abc")]),
    ]
    filtered = filter_irrelevant_files(files)
    filenames = [f.filename for f in filtered]
    assert filenames == ["app/main.py"]
