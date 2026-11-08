# Hawa agent entry point

Hawa is an experimental embedded CFD plugin for Rhino 8 and Grasshopper.

For operating the installed plugin through **Rhino MCP only**, read
[docs/agents/rhino-mcp.md](docs/agents/rhino-mcp.md), then
[examples/grasshopper/README.md](examples/grasshopper/README.md).
These workflows use native Hawa components and Rhino's embedded Python runtime.
They do not require a separate Python process, shell access, browser automation,
or direct access to private embedded-runtime fields.

## Repository working rules

- Preserve user geometry, documents and edits. Example 09 is a modified legacy
  Galapagos definition; do not regenerate, overwrite or include it in release
  packages. Use example 10 for supported asynchronous hull search.
- Treat solver output as experimental. Read the release notes and moving-surface
  limits before reporting forces or coefficients. PorousMedium CPU/MPS parity
  remains unresolved. Do not relax comparison tolerances to hide a difference.
- Keep the Python production code compatible with Python 3.9 and the pinned
  PyTorch dependencies. MPS is PyTorch's Apple backend; MLX is not a backend here.
- Use cooperative pause/cancel and document disposal. Never kill Rhino to
  restart it. Quit through Rhino's normal application command when a restart is
  needed. Do not replace a loaded plugin assembly.
- Keep heavy work off the Grasshopper solution thread. Poll background jobs;
  do not wait in a C# loop, sleep on the UI thread, or use `.Wait()` / `.Result`
  on an unfinished task.
- Preserve functional object IDs, wires, parameter values and archive
  compatibility when improving example presentation. The annotation script
  checks connections and keeps local backups. Run it after regenerating examples.
- Original Hawa code is GPL-3.0-only. Preserve bundled upstream license notices.
- Report what was actually run, including device, steps and skipped checks.
  A rendered field is not a convergence or engineering-accuracy result.

## Developer checks

Use the repository's `.venv/bin/python` for local development commands. Test
changes with the relevant tests, then the Hawa suite. Run the native verification
scripts through Rhino MCP for changes to Grasshopper behavior. Paths in C# helper
scripts must be adjusted for a different checkout.

Build with `scripts/build_plugin.py`. It includes source and supported examples.
The installed-user workflow is documented separately from this developer build.
