from .base import BaseLLMClient

__all__ = ["BaseLLMClient", "LiteLLMClient"]


def __getattr__(name: str):
    if name == "LiteLLMClient":
        from .litellm_client import LiteLLMClient

        return LiteLLMClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
