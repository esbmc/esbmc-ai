# Author: Yiannis Charalambous

from dataclasses import dataclass, field
from langchain.schema import BaseMessage
from langchain_core.language_models import BaseChatModel, FakeListChatModel


@dataclass(frozen=True, kw_only=True)
class MockAIModel:
    """Mock AI model for testing purposes."""

    name: str = "mock-model"
    tokens: int = 1024
    responses: list[str] = field(default_factory=list[str])

    def create_llm(self) -> BaseChatModel:
        """Create a fake LLM for testing."""
        return FakeListChatModel(responses=self.responses)


def test_mock_ai_model_creation() -> None:
    """Test that MockAIModel can be created."""
    mock_model = MockAIModel(
        name="test-model", tokens=2048, responses=["response1", "response2"]
    )
    assert mock_model.name == "test-model"
    assert mock_model.tokens == 2048
    assert len(mock_model.responses) == 2

    llm = mock_model.create_llm()
    assert llm is not None
    assert isinstance(llm, FakeListChatModel)
