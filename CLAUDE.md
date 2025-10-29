# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ESBMC-AI is an Automated LLM Integrated Workflow Platform for Automated Program Repair (APR) research. It integrates ESBMC (a bounded model checker) with various AI models to automatically repair C/C++ code bugs. The platform provides different commands for code analysis, repair, and optimization.

## Common Development Commands

### Running the Application
```bash
# Main entry point using hatch
hatch run esbmc-ai <command> [options]

# Example: Fix code using the fix-code command
hatch run esbmc-ai fix-code path/to/file.c
```

### Testing
```bash
# Run all tests using hatch test environment
hatch test

# Run specific test files
hatch run pytest tests/test_specific_file.py

# Run tests with coverage
hatch run pytest --cov
```

### Building and Development
```bash
# Build the project
hatch build

# Check for dependency cycles
hatch run find-cycles

# Build Docker/Podman images
hatch run docker-build
hatch run podman-build
```

### Code Quality
```bash
# Run linting (configured in hatch environment)
hatch run pylint esbmc_ai/

# Development environment with debugging tools
hatch shell
```

## Architecture Overview

### Core Components

**Entry Point (`__main__.py`)**
- Handles command-line argument parsing and configuration loading
- Initializes built-in components (verifiers and commands)
- Manages addon loading through `AddonLoader`
- Routes commands to appropriate handlers

**Configuration System (`config.py`)**
- Singleton-based configuration management using `BaseConfig`
- Supports multiple sources: environment variables, config files, command-line args
- Hierarchical loading with `.env` file support
- Extensive validation and type checking for all config fields

**AI Models Integration (`ai_models.py`)**
- Abstract `AIModel` base class with concrete implementations for OpenAI, Anthropic, and Ollama
- Token counting and model management through `AIModels` singleton
- Template application and message formatting
- Caching system for model lists with configurable refresh intervals

**Component System (`base_component.py`)**
- Base class for all extensible components (commands and verifiers)
- Factory pattern with automatic instantiation validation
- Configuration field integration for component-specific settings

**Chat Interface (`chats/base_chat_interface.py`)**
- Base class for LLM interactions with message stack management
- Template substitution system for dynamic content
- Cooldown management between API requests
- Message compression and conversation handling

### Command Architecture

**Commands** (`commands/` directory)
- `FixCodeCommand`: Main repair functionality using ESBMC output
- `HelpCommand`: Dynamic help generation from loaded components
- Commands extend `ChatCommand` base class
- Support for configuration fields and argument parsing

**Solution System** (`solution.py`)
- Manages source code files and repair attempts 
- Tracks patches and modifications
- Integration with output directory management

### Verifier System

**Base Verifier** (`verifiers/base_source_verifier.py`)
- Abstract interface for code verification tools
- Standardized output format through `VerifierOutput`

**ESBMC Integration** (`verifiers/esbmc.py`)
- Bounded model checker integration
- Counterexample parsing and error extraction
- Program trace analysis for debugging

### Extension System

**Addon Loader** (`addon_loader.py`)
- Dynamic loading of external components
- Plugin architecture for extending functionality
- Component registration and management

**Component Loader** (`component_loader.py`)
- Central registry for all commands and verifiers
- Manages built-in and addon components
- Command routing and selection logic

## Key Configuration Patterns

- Use `ConfigField` for all configurable options with validation
- Environment variables follow `ESBMCAI_*` prefix pattern
- Config files support TOML format with hierarchical organization
- All paths support tilde expansion and environment variable substitution

## Testing Patterns

- Uses pytest with regression testing (`pytest-regtest`)
- Test files located in `tests/` directory
- Sample files for testing in `samples/` directory
- Configuration tests validate field loading and validation logic

## Development Notes

- The project uses modern Python features (3.12+) with type hints
- Structured logging throughout with category-based organization
- Singleton pattern used for global state management (Config, AIModels)
- All components follow factory pattern for instantiation
- Error handling with custom exceptions for verification timeouts and integrity issues