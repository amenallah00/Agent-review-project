import pytest

from app.llm.azure_openai_provider import AzureOpenAIProvider


def test_builds_correct_url_from_endpoint_and_deployment():
    provider = AzureOpenAIProvider(
        endpoint="https://amenallahbenabdrabah.openai.azure.com",
        api_key="fake-key",
        deployment="gpt-4o",
        api_version="2024-08-01-preview",
    )
    assert provider._url == (
        "https://amenallahbenabdrabah.openai.azure.com/openai/deployments/gpt-4o/chat/completions"
        "?api-version=2024-08-01-preview"
    )


def test_strips_trailing_slash_from_endpoint():
    provider = AzureOpenAIProvider(
        endpoint="https://example.openai.azure.com/", api_key="k", deployment="gpt-4o",
    )
    assert "azure.com//openai" not in provider._url
    assert provider._url.startswith("https://example.openai.azure.com/openai/")


def test_raises_clear_error_when_endpoint_missing():
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        AzureOpenAIProvider(endpoint="", api_key="k", deployment="gpt-4o")


def test_raises_clear_error_when_deployment_missing():
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        AzureOpenAIProvider(endpoint="https://example.openai.azure.com", api_key="k", deployment="")
