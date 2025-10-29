---
title: "Contributing"
type: docs
weight: 6
prev: /docs/addons
next: /docs/build
---

It is recommended to contribute to ESBMC-AI directly, especially if the feature would improve ESBMC-AI directly. When contributing you can create a pull request, and after all the issues are resolved, and it passes the code-review, it will be merged.

**Important**: Contributing to ESBMC-AI requires agreeing to the terms and conditions set forth by the [Contributor License Agreement (CLA)](https://github.com/esbmc/esbmc-ai/blob/master/CLA.md). By submitting any contribution, you acknowledge that you have read, understood, and agree to be bound by the CLA.

Try to submit patches that follow the following rules:

1. Keep the coding style consistent. Use the [Black](https://pypi.org/project/black/) code formatter, it is specified as a development dependency, so it will be installed automatically.
2. Document the contributions you make accordingly, if it is a new feature, please add the correct documentation. Keep the righting style professional when writing documentation.
3. Include comments and function doc-strings to all public functions made.
4. Make sure to update tests as appropriate.

To learn more about the code-base of ESBMC-AI, you can read so in the [Architecture](/docs/architecture).

## Source Code Setup

In order to begin contributing to ESBMC-AI's source code, please follow the steps:

{{% steps %}}

### Fork the repo

### Begin working

ESBMC-AI is developed using the [Hatch](https://hatch.pypa.io/latest/) project management. So initializing an environment in it would automatically install all the dependencies, allowing the development to begin relatively painlessly. Initialize the development environment:

```sh
hatch shell
```

Now you can write you code and run the `esbmc_ai` module directly or using the helper script `./esbmc-ai`.

### Submit a pull request in the ESBMC-AI repo

If you aren't sure if this feature wil be accepted into ESBMC-AI, you can create one as a draft where you describe the feature. If it gets rejected without any comments you can turn it into an [addon](#addon-development).

{{% /steps %}}

## Addon Development

> [!IMPORTANT]
> Before developing an addon, create a draft PR to discuss if a topic should be contributed directly into ESBMC-AI. Contributing directly to ESBMC-AI has benefits vs. addons.
>* Ease-of-use: Avoids the need to separatley install the addon, making it more widely used in ESBMC-AI.
>* Credit: If a major contribution is made, you will be added in the contributors credit page for ESBMC-AI (when we make one).
>* Version Compatibility: Features in the main code-base will work with future versions, as future compatibility will be ensured. With addons this is not guaranteed, and it is solely up to the addon developer to ensure this compaitbility.

If a feature would not be suitable as in the ESBMC-AI Platform, you can create an addon for it. This can happen if a PR is denied. Creating an addon is a relatively easy experience. The following steps can be used to begin development:

{{% steps %}}

### Enabling Addon Development Mode

Enable the `dev_mode` flag in the config. This will make ESBMC-AI search for modules in your current directory in addition to the system path which is by default.

### Addon Template

Download the [addon template](https://github.com/Yiannis128/esbmc_ai_addon_template) and begin developing using it.

{{% /steps %}}

In order for ESBMC-AI to detect the addon, export it by specifying it in the `__all__` variable in `__init__.py`. In the config used for ESBMC-AI, specify the import path to that addon as an entry to the `addon_modules` config field.

{{% details title="Example" closed="true" %}}

Assume you are developing an addon called "metanoia" with the following folder structure:

{{< filetree/container >}}
    {{< filetree/file name="pyproject.toml" >}}
    {{< filetree/file name="config.toml" >}}
    {{< filetree/folder name="metanoia" >}}
        {{< filetree/file name="\_\_init\_\_.py" >}}
        {{< filetree/file name="metanoia.py" >}}
        {{< filetree/folder name="chat_commands" >}}
            {{< filetree/file name="custom_fix.py" >}}
        {{< /filetree/folder >}}
        {{< filetree/folder name="verifiers" >}}
            {{< filetree/file name="pytest_verifier.py" >}}
        {{< /filetree/folder >}}
    {{< /filetree/folder >}}
{{< /filetree/container >}}

In order for ESBMC-AI to detect the addon, you can export all the relevant classes by assigning them to the `__all__` variable in the `__init__.py` file that will be specified in the ESBMC-AI config:

```py {filename="metanoia/__init__.py"}
from .chat_commands.custom_fix import CustomFix
from .verifiers.pytest_verifier import PyTestVerifier

__all__ = [
    "CustomFix",
    "PyTestVerifier",
]
```

{{% /details %}}