# Author: Yiannis Charalambous

"""Template key provider interface and implementations."""

from abc import ABC, abstractmethod
from typing import Any, override

from esbmc_ai.solution import Solution
from esbmc_ai.verifier_output import VerifierOutput


class TemplateKeyProvider(ABC):
    """Abstract base class for providing template keys to chat interfaces."""

    @abstractmethod
    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Get template keys for message template substitution."""
        raise NotImplementedError()


class OracleTemplateKeyProvider(TemplateKeyProvider):
    """Template key provider for oracle-specific template variables."""

    @override
    def get_template_keys(
        self,
        *,
        solution: Solution,
        oracle_output: VerifierOutput,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Get canonical template keys for oracle-based code repair workflows.

        Args:
            solution: The solution containing source files being repaired
            oracle_output: VerifierOutput object with structured verification data
            **kwargs: Additional keys to include

        Returns:
            Dictionary of template keys including the oracle_output object
            which provides access to all structured fields like error_type,
            error_message, stack_trace, etc.
        """
        keys: dict["str", Any] = {
            "solution": solution,
            "oracle_output": oracle_output,
        }
        # Include any additional keys passed in
        keys.update(kwargs)
        return keys


class GenericTemplateKeyProvider(TemplateKeyProvider):
    """Generic template key provider that passes through all kwargs."""

    def get_template_keys(self, **kwargs: Any) -> dict[str, Any]:
        """Get template keys by returning all provided kwargs."""
        return kwargs
