from dataclasses import dataclass


class ChatbotError(RuntimeError):
    """Base error for chatbot provider failures."""


@dataclass
class ProviderUnavailableError(ChatbotError):
    provider: str
    reason: str

    def __str__(self) -> str:
        return f"{self.provider} unavailable: {self.reason}"
