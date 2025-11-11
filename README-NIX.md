# Nix Development Environment

This project uses Nix for managing the development environment with all dependencies, including C libraries.

## Quick Start

### Option 1: Using Nix Flakes (Recommended)

1. **Enable flakes** (if not already enabled):
   ```bash
   mkdir -p ~/.config/nix
   echo "experimental-features = nix-command flakes" >> ~/.config/nix/nix.conf
   ```

2. **Enter the development shell**:
   ```bash
   nix develop
   ```

3. **Python dependencies are automatically synced** via `uv sync` when entering the shell.

4. **Activate Python environment** (if needed):
   ```bash
   cd processor
   source .venv/bin/activate
   ```
   
   Or use `uv run` directly:
   ```bash
   cd processor
   uv run python script.py
   ```

### Option 2: Using direnv (Automatic)

1. **Install direnv**:
   ```bash
   nix profile install nixpkgs#direnv
   ```

2. **Allow direnv** (in project root):
   ```bash
   direnv allow
   ```

3. The environment will automatically load when you `cd` into the project!

## What's Included

- **Python 3.13** (base interpreter, packages managed by uv)
- **uv** - Fast Python package manager (manages all Python dependencies)
  - All packages from `processor/pyproject.toml` are installed via uv
  - Dependencies are synced from `processor/uv.lock` if available

- **C Dependencies**:
  - espeak-ng (text-to-speech engine, required for aeneas)
  - ffmpeg (audio/video processing)
  - sox (audio processing)

- **Node.js 20** (for book scripts)

- **Development Tools**:
  - git, curl, wget

## Usage

After entering the shell, you can use these convenient commands:

### Quick Commands

1. **Edit scripts with marimo** (opens in browser with live reload):
   ```bash
   segment-text    # Edit segment-text.py
   audio-femalize  # Edit audio-femalize.py
   ```

2. **Run main script**:
   ```bash
   main
   ```

### Manual Usage

If you prefer to run scripts manually:

1. **Process text segments**:
   ```bash
   cd processor
   uv run marimo edit segment-text.py --watch
   ```


3. **Run Node.js scripts** (for book processing):
   ```bash
   cd book/scripts
   npm install
   node index.js
   ```

## Troubleshooting

### Python packages not found
All Python packages are managed by `uv`. If packages are missing:
```bash
cd processor
uv sync  # Syncs from uv.lock, or installs from pyproject.toml
```

### Adding new Python dependencies
Add to `processor/pyproject.toml`, then:
```bash
cd processor
uv sync  # Updates lock file and installs
```

### aeneas or other packages with C dependencies
These should work automatically since the C libraries (espeak-ng, ffmpeg) are provided by Nix. If issues occur:
```bash
cd processor
uv pip install aeneas
```

### C library errors
All C dependencies (espeak-ng, ffmpeg) are provided by Nix. If you encounter library errors, make sure you're inside the `nix develop` shell.

### Python version mismatch
The project requires Python 3.13+. The Nix flake provides exactly this version, and `uv` is configured to use it automatically.

