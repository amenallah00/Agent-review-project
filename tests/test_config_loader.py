import pytest

from app.config_loader import default_config, load_repo_config, parse_repo_config


def test_default_config_matches_global_settings():
    cfg = default_config()
    assert cfg.max_pr_lines > 0
    assert cfg.auto_approve_enabled is True


def test_parse_repo_config_overrides_only_known_keys():
    yaml_content = """
    max_pr_lines: 800
    auto_approve_enabled: false
    unknown_key: some_value
    """
    cfg = parse_repo_config(yaml_content)
    assert cfg.max_pr_lines == 800
    assert cfg.auto_approve_enabled is False
    assert not hasattr(cfg, "unknown_key")


def test_parse_repo_config_handles_empty_file():
    cfg = parse_repo_config("")
    default = default_config()
    assert cfg.max_pr_lines == default.max_pr_lines


def test_parse_repo_config_handles_malformed_yaml_gracefully():
    cfg = parse_repo_config("max_pr_lines: [unclosed")
    default = default_config()
    assert cfg.max_pr_lines == default.max_pr_lines


def test_parse_repo_config_ignores_non_dict_yaml():
    cfg = parse_repo_config("- just\n- a\n- list")
    default = default_config()
    assert cfg.max_pr_lines == default.max_pr_lines


class _FakeClientWithConfig:
    async def get_file_content(self, owner, repo, path, ref):
        return "max_pr_lines: 42\n"


class _FakeClientWithoutConfig:
    async def get_file_content(self, owner, repo, path, ref):
        raise Exception("404 Not Found")


@pytest.mark.asyncio
async def test_load_repo_config_uses_file_when_present():
    cfg = await load_repo_config(_FakeClientWithConfig(), "owner", "repo", "main")
    assert cfg.max_pr_lines == 42


@pytest.mark.asyncio
async def test_load_repo_config_falls_back_to_default_when_absent():
    cfg = await load_repo_config(_FakeClientWithoutConfig(), "owner", "repo", "main")
    default = default_config()
    assert cfg.max_pr_lines == default.max_pr_lines
