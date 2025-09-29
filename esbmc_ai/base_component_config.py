# Author: Yiannis Charalambous


from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseComponentConfig(BaseSettings):
    """Pydantic BaseSettings preconfigured to be able to load config values."""

    # Used to allow loading from cli and env.
    model_config = SettingsConfigDict(
        env_prefix="ESBMCAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        # Do not parse CLI args in component configs - only the main Config should
        cli_parse_args=False,
        # Ignore extra fields from .env file that don't match the component schema
        extra="ignore",
    )

    def __init_subclass__(cls):
        # Modify field aliases by adding prefix if alias is not explicit
        for field_name, model_field in cls.model_fields.items():
            new_alias: str
            if model_field.alias:
                # Set alias with prefix if none or default alias
                new_alias = cls.prefix() + model_field.alias
            else:
                # Set alias with prefix if none or default alias
                new_alias: str = cls.prefix() + field_name

            # Need to update alias in the field's metadata
            model_field.alias = new_alias

        super().__init_subclass__()

    @classmethod
    def prefix(cls) -> str:
        return "addons."
