# iflytek-digital-human - Codex plugin

This is the self-contained Codex package published by the iflytek-digital-human
repository. It includes the runtime resources required by its Skills.

## Contents

- `.codex-plugin/plugin.json` - Codex plugin manifest.
- `skills/` - iflytek-digital-human skills and references.
- `.codex/agents/` - converted Codex agent definitions.
- `hooks.json` - Codex lifecycle hook registration.
- `hooks/` - routing, consent, response, and session guards.
- `tools/` - Xfyun platform Python tools for login, credentials, templates,
  live projects, model management, and knowledge bases.
- `config/` - tool registry, platform registry, and error-code mappings.
- `docs/` and `rules/` - source documentation and domain conventions.

## Codex Usage

The entry skill is `avatar-workflow-entry`. For virtual-human or digital-human
tasks, start from that skill so it can route to the correct expert skill.

Version `1.1.0` stores local telemetry state under
`~/.codex/iflytek-digital-human/telemetry` and reports `agent=codex`.
On first use, the entry skill shows the full `docs/capabilities.md` content and
the exact `tools/telemetry.py notice` output before waiting for explicit
telemetry consent. Declining telemetry does not disable avatar features.

Codex stable 0.146.1 loads `hooks.json` and runs this package's
`UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Stop`, and `SessionEnd` hooks.
The hooks inject routing context, deny avatar business tools until consent is
decided, and block a final response that hides the complete capability and
consent notice. They never mark delivery complete: the entry skill still uses
`telemetry.py start`, `invoke`, and a final `complete` or `fail` with the
returned `workflowId`. When Hooks are disabled or untrusted, the same explicit
skill lifecycle is the fallback. A forced host shutdown is not a successful
completion signal.

When a skill asks to run `python tools/...`, run it from the plugin root:

```powershell
Set-Location <plugin-root>
python tools\xfyun_query_services.py
```

Install the GitHub marketplace and plugin with:

```powershell
codex plugin marketplace add firstdebug/avatar-platform --ref main
codex plugin add iflytek-digital-human@iflytek-digital-human-codex
```

## Runtime Dependencies

The Python tools require Python 3.8+ and the packages in `tools/requirements.txt`.
The browser-login flow also needs Playwright Chromium:

```powershell
pip install -r tools\requirements.txt
playwright install chromium
```

Network and browser operations are intentionally not run during plugin packaging.
