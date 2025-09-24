# ESBMC AI


[![Development](https://github.com/esbmc/esbmc-ai/actions/workflows/workflow.yml/badge.svg?branch=master)](https://github.com/esbmc/esbmc-ai/actions/workflows/workflow.yml)
[![Docker Repository on Quay](https://quay.io/repository/yiannis128/esbmc-ai/status "Docker Repository on Quay")](https://quay.io/repository/yiannis128/esbmc-ai)

Automated LLM Integrated Workflow Platform. Primarily oriented around Automated Program Repair (APR) research. There are different commands that can be executed with ESBMC-AI. There are different commands that ESBMC-AI can run, and can also be extended with Addons (see [below](#wiki)).

The basic repair implementation passes the output from ESBMC to an AI model with instructions to repair the code. As the output from ESBMC can be quite technical in nature.

![ESBMC-AI Visual Abstract](website/content/docs/images/esbmc-ai_framework.png)

![ESBMC-AI Platform](website/content/docs/images/platform_diag.png)

## Quick Start

```sh
hatch run esbmc-ai ...
```

## Demonstration

[![Fix Code Demo](https://img.youtube.com/vi/anpRa6GpVdU/0.jpg)](https://www.youtube.com/watch?v=anpRa6GpVdU)

More videos can be found on the [ESBMC-AI Youtube Channel](https://www.youtube.com/@esbmc-ai)

## Wiki

For full documentation, see the [ESBMC-AI Wiki](esbmc.github.io/esbmc-ai). Quick Links:

* [Initial Setup Guide](esbmc.github.io/esbmc-ai/docs/initial-setup/).
* [Built-in Commands](http://localhost:1313/docs/commands/)
* [Addons](http://localhost:1313/docs/addons/)

## Contributing

See [this page](esbmc.github.io/esbmc-ai/contributing).

## License

> [!NOTE]
>This project is offered under a [dual-licence](LICENSE) model.
