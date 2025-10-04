# Author: Yiannis Charalambous

"""Template key provider interface and implementations."""

from abc import ABC, abstractmethod
from typing import Any, override


class TemplateKeyProvider(ABC):
    """Abstract base class for providing template keys to chat interfaces."""

    @abstractmethod
    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Get template keys for message template substitution."""
        raise NotImplementedError()


class ESBMCTemplateKeyProvider(TemplateKeyProvider):
    """Template key provider for ESBMC-specific template variables."""

    @override
    def get_template_keys(
        self,
        *,
        source_code: str,
        esbmc_output: str,
        error_line: str,
        error_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get canonical template keys for ESBMC code repair workflows."""
        keys: dict["str", Any] = {
            "source_code": source_code,
            "esbmc_output": esbmc_output,
            "error_line": error_line,
            "error_type": error_type,
        }
        # Include any additional keys passed in
        keys.update(kwargs)
        return keys


class GenericTemplateKeyProvider(TemplateKeyProvider):
    """Generic template key provider that passes through all kwargs."""

    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Get template keys by returning all provided kwargs."""
        return kwargs
