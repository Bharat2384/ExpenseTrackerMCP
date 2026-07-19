---
name: "main-cli"
description: "CLI for the main MCP server. Call tools, list resources, and get prompts."
---

# main CLI

## Tool Commands

### roll_dice

Roll n_dice and return the results

```bash
uv run --with fastmcp python cli.py call-tool roll_dice --n-dice <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--n-dice` | integer | no |  |

### add_number

Add two numbers

```bash
uv run --with fastmcp python cli.py call-tool add_number --a <value> --b <value>
```

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--a` | number | yes |  |
| `--b` | number | yes |  |

## Utility Commands

```bash
uv run --with fastmcp python cli.py list-tools
uv run --with fastmcp python cli.py list-resources
uv run --with fastmcp python cli.py read-resource <uri>
uv run --with fastmcp python cli.py list-prompts
uv run --with fastmcp python cli.py get-prompt <name> [key=value ...]
```
