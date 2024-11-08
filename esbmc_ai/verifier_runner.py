from esbmc_ai.verifiers import BaseSourceVerifier
from esbmc_ai.config import ConfigField


class VerifierRunner:

    def __new__(cls):
        if not hasattr(cls, "instance"):
            cls.instance = super(VerifierRunner, cls).__new__(cls)
        return cls.instance

    def init(self, builtin_verifiers: list[BaseSourceVerifier]) -> None:
        self._builtin_verifiers: dict[str, BaseSourceVerifier] = {
            v.verifier_name: v for v in builtin_verifiers
        }
        """Builtin loaded verifiers"""
        self.addon_verifiers: dict[str, BaseSourceVerifier] = {}
        """Additional loaded verifiers"""
        self.verifier: BaseSourceVerifier = builtin_verifiers[0]
        """Default verifier"""

    @property
    def verifiers(self) -> dict[str, BaseSourceVerifier]:
        """Gets all verifiers"""
        return self._builtin_verifiers | self.addon_verifiers

    @property
    def addon_verifier_names(self) -> list[str]:
        """Gets all addon verifier names"""
        return list(self.addon_verifiers.keys())

    def init_configs(self) -> list[ConfigField]:
        """Adds each verifier's config fields to the config. After resolving
        each verifier's config fields to their namespace. Also, will raise an
        assertion error if there's duplicate fields."""
        fields_resolved: list[ConfigField] = []
        added_fields: list[str] = []
        for verifier in self.verifiers.values():
            fields: list[ConfigField] = verifier.get_config_fields()
            for field in fields:
                resolved_name: str = f"{verifier.verifier_name}.{field.name}"
                assert (
                    resolved_name not in added_fields
                ), f"Field {resolved_name} is redefined..."
                new_field = ConfigField(
                    name=resolved_name,
                    default_value=field.default_value,
                    default_value_none=field.default_value_none,
                    validate=field.validate,
                    on_load=field.on_load,
                    on_read=field.on_read,
                    error_message=field.error_message,
                )
                fields_resolved.append(new_field)
                added_fields.append(resolved_name)
        return fields_resolved
