# Author: Yiannis Charalambous

"""Template key provider interface and implementations."""

from abc import ABC, abstractmethod
from typing import Any, override

from esbmc_ai.verifier_output import VerifierOutput
from esbmc_ai.verifiers.esbmc import ESBMCOutput


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
        esbmc_output: VerifierOutput,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get canonical template keys for ESBMC code repair workflows.

        Args:
            source_code: The source code being repaired
            esbmc_output: ESBMCOutput object with structured verification data
            **kwargs: Additional keys to include

        Returns:
            Dictionary of template keys including the esbmc_output object
            which provides access to all structured fields like error_type,
            error_message, stack_trace, etc.
        """
        keys: dict["str", Any] = {
            "source_code": source_code,
            "esbmc_output": esbmc_output,
        }
        # Include any additional keys passed in
        keys.update(kwargs)
        return keys


class GenericTemplateKeyProvider(TemplateKeyProvider):
    """Generic template key provider that passes through all kwargs."""

    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Get template keys by returning all provided kwargs."""
        return kwargs
