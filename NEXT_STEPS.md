# javalamp Next Steps

This repo was renamed in code from `terminaltwist` to `javalamp`.
The local directory and GitHub repository may still need to be renamed manually.

## Current State

- Python package path is now `src/javalamp`.
- CLI command is now `javalamp`.
- Package name in `pyproject.toml` is now `javalamp`.
- Docs now use `javalamp`, `~/.config/javalamp/scenes/`, and `JAVALAMP_SCENES_DIR`.
- No remaining `terminaltwist`, `TerminalTwist`, `TERMINALTWIST`, or `twist` references were found outside ignored cache/venv files.
- Verification passed after clearing the local macOS hidden flag on `.venv`:
  - `.venv/bin/python -m pytest -q`
  - `.venv/bin/javalamp -l`
  - `.venv/bin/python -m javalamp --version`
  - `.venv/bin/javalamp matrix -d 1s --no-splash --no-caffeinate`

## Manual User Tasks

1. Rename the local repo folder from `terminaltwist` to `javalamp`.
2. Rename the GitHub repository from `terminaltwist` to `javalamp`.
3. Update the local git remote if needed:

   ```sh
   git remote set-url origin git@github.com:tbreschi/javalamp.git
   ```

## Recommended Next Agent Tasks

1. Re-run the stale-name scan after the repo folder/GitHub rename:

   ```sh
   rg -n "terminaltwist|TerminalTwist|TERMINALTWIST|twist" . \
     -g '!*__pycache__*' -g '!.venv/*' -g '!.pytest_cache/*'
   ```

2. Polish the README positioning for the new name.
   Suggested tagline direction:

   > A glowing terminal screensaver that keeps your Mac awake.

   Make sure the top of the README clearly communicates both:
   - animated terminal screensavers
   - macOS `caffeinate -d -i` sleep prevention

3. Add a PyPI release workflow using Trusted Publishing.
   Goal install path:

   ```sh
   pipx install javalamp
   ```

   Suggested workflow:
   - Build with `python -m build`.
   - Publish on GitHub release/tag through `pypa/gh-action-pypi-publish`.
   - Use PyPI Trusted Publishing, not a long-lived token.

4. Add a README demo recording.
   The README already has a placeholder comment for an asciinema recording.
   This project needs motion near the top of the README before launch.

5. Make scene contribution easier.
   Consider adding:

   ```sh
   javalamp new-scene lava
   javalamp check-scene lava
   ```

   The goal is to let contributors create and validate a new scene quickly.

6. Add `SCENE_GUIDE.md`.
   Keep it short and friendly:
   - one tiny starter scene
   - one richer example
   - notes on theme roles, canvas helpers, resize behavior, and thumbnail constraints
   - expectations for PRs

7. Add stronger scene contract tests.
   Good checks:
   - all public scenes have lowercase slug names
   - all public scenes have title and description
   - every scene renders at small, medium, and large terminal sizes
   - every scene survives all themes
   - user scene loader still works with `JAVALAMP_SCENES_DIR`

8. Publish `v0.1.0` after the README/demo/release workflow are ready.

## Naming Context

`javalamp` was chosen because it combines:

- Java as coffee/caffeine
- lamp as desk glow / screen ambience
- a near-echo of lava lamp / screensaver visuals
- a developer-friendly pun

Availability checked before the rename:

- PyPI: available
- npm: available
- crates.io: available

The project also wraps macOS `caffeinate -d -i` by default while running,
unless the user passes `--no-caffeinate`.
