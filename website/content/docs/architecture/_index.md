---
title: Architecture
type: docs
---

ESBMC-AI is a platform that allows for easy development of APR methods. The platform contains components that provide a flexible and extensible framework for automated program repair research.

![Diagram of ESBMC-AI](/docs/images/platform_diag.png)

## Core Architecture Components

The ESBMC-AI platform is built around several key architectural components:

### Component System
- **[Base Component](base-component/)** - Foundation for all extensible components including commands and verifiers
- Component factory pattern with automatic instantiation validation
- Configuration field integration for component-specific settings

### AI Model Integration
- Abstract AIModel base class with concrete implementations for OpenAI, Anthropic, and Ollama
- **[Variable Substitution System](variable-substitution/)** - Dynamic template replacement for AI prompts
- Token counting and model management through AIModels singleton
- Caching system for model lists with configurable refresh intervals

### Chat Interface System
- Base class for LLM interactions with message stack management
- Template substitution system for dynamic content
- Cooldown management between API requests
- Message compression and conversation handling

### Command Architecture
- Commands extend ChatCommand base class and handle specific user requests
- Support for configuration fields and argument parsing
- Dynamic help generation from loaded components

### Verifier System  
- Abstract interface for code verification tools
- Standardized output format through VerifierOutput
- ESBMC integration with counterexample parsing and error extraction

### Configuration System
- Singleton-based configuration management using BaseConfig
- Supports multiple sources: environment variables, config files, command-line args
- Hierarchical loading with .env file support
- Extensive validation and type checking for all config fields

### Extension System
- **Addon Loader** - Dynamic loading of external components
- Plugin architecture for extending functionality
- Component registration and management
