{
  description = "Wenyan Book Video - Development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };

        # Base Python 3.13 interpreter - uv will manage all packages
        python313 = pkgs.python313;

        # C dependencies for audio processing
        audioDeps = with pkgs; [ ffmpeg sox ];

        # Runtime packages needed for commands
        runtimePackages = [ python313 pkgs.uv ];

        # Create executable commands as proper Nix packages
        segment-text-cmd = pkgs.writeShellApplication {
          name = "segment-text";
          runtimeInputs = runtimePackages;
          text = ''
            export UV_PYTHON="${toString python313}/bin/python3"
            cd processor && uv run marimo edit segment-text.py --watch
          '';
        };

        voice-change-cmd = pkgs.writeShellApplication {
          name = "voice-change";
          runtimeInputs = runtimePackages;
          text = ''
            export UV_PYTHON="${toString python313}/bin/python3"
            cd processor && uv run marimo edit voice-change.py --watch
          '';
        };

        synthesize-cmd = pkgs.writeShellApplication {
          name = "synthesize";
          runtimeInputs = runtimePackages;
          text = ''
            export UV_PYTHON="${toString python313}/bin/python3"
            cd processor && uv run marimo edit synthesize.py --watch
          '';
        };

        transcribe-cmd = pkgs.writeShellApplication {
          name = "transcribe";
          runtimeInputs = runtimePackages;
          text = ''
            export UV_PYTHON="${toString python313}/bin/python3"
            cd processor && uv run marimo edit transcribe.py --watch
          '';
        };

        main-cmd = pkgs.writeShellApplication {
          name = "main";
          runtimeInputs = runtimePackages;
          text = ''
            export UV_PYTHON="${toString python313}/bin/python3"
            cd processor && uv run python main.py
          '';
        };

        remotion-render-cmd = pkgs.writeShellApplication {
          name = "remotion-render";
          runtimeInputs = [ pkgs.bun ];
          text = ''
            cd renderer && bun run remotion render
          '';
        };

        remotion-dev-cmd = pkgs.writeShellApplication {
          name = "remotion-dev";
          runtimeInputs = [ pkgs.bun ];
          text = ''
            cd renderer && bun run dev
          '';
        };

        # Collect all command packages
        commandPackages = [
          segment-text-cmd
          voice-change-cmd
          synthesize-cmd
          transcribe-cmd
          main-cmd
          remotion-render-cmd
          remotion-dev-cmd
        ];
      in {
        # Expose commands as packages
        packages = {
          segment-text = segment-text-cmd;
          voice-change = voice-change-cmd;
          synthesize = synthesize-cmd;
          transcribe = transcribe-cmd;
          main = main-cmd;
          remotion-render = remotion-render-cmd;
          remotion-dev = remotion-dev-cmd;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            # Base Python interpreter (uv manages all packages)
            python313

            # C dependencies for audio processing
            audioDeps

            # Node.js for book scripts
            pkgs.nodejs_20
            pkgs.nodePackages.npm

            # Bun for renderer
            pkgs.bun

            # System utilities
            pkgs.git
            pkgs.curl
            pkgs.wget

            # Audio processing tools
            pkgs.ffmpeg
            pkgs.sox

            # uv - Python package manager (manages all Python dependencies)
            pkgs.uv

            # Command packages
            commandPackages
          ];

          shellHook = ''
            # Set up a nice prompt for fish shell
            if [ -n "$FISH_VERSION" ]; then
              # Define the prompt function directly in fish
              fish -c 'function fish_prompt
                set_color -o cyan
                echo -n (whoami)
                set_color normal
                echo -n "@"
                set_color -o yellow
                echo -n (hostname | cut -d . -f 1)
                set_color normal
                echo -n ":"
                set_color -o blue
                echo -n (prompt_pwd)
                set_color normal
                echo -n " "
                set_color -o green
                echo -n "> "
                set_color normal
              end; funcsave fish_prompt' 2>/dev/null || true
            fi

            # Bash/zsh style prompt (fallback)
            export PS1='\[\e[36m\]\u\[\e[0m\]@\[\e[33m\]\h\[\e[0m\]:\[\e[34m\]\w\[\e[0m\] \[\e[32m\]\$\[\e[0m\] '

            echo "🐉 Wenyan Book Video Development Environment"
            echo ""
            echo "Python: $(python --version)"
            echo "uv: $(uv --version)"
            echo "Node.js: $(node --version)"
            echo "FFmpeg: $(ffmpeg -version 2>/dev/null | head -n 1 || echo 'available')"
            echo ""
            echo "Setting up Python environment with uv..."

            # Clear LD_LIBRARY_PATH to prevent conflicts
            # Nix packages work correctly when LD_LIBRARY_PATH is empty/unset
            # VSCode/system LD_LIBRARY_PATH causes glibc conflicts
            unset LD_LIBRARY_PATH
            export LD_LIBRARY_PATH=""

            # Configure uv to use the Nix-provided Python
            export UV_PYTHON="${toString python313}/bin/python3"

            # Set up uv environment in processor directory
            if [ -d processor ]; then
              cd processor
              
              # Use uv sync if lock file exists, otherwise uv pip install
              if [ -f uv.lock ]; then
                echo "Syncing dependencies from uv.lock..."
                uv sync
              elif [ -f pyproject.toml ]; then
                echo "Installing dependencies from pyproject.toml..."
                uv venv
                uv pip install -e .
              fi
              
              cd ..
            fi

            # Commands are available via packages in PATH
            echo ""
            echo "Available commands:"
            echo "  segment-text   - Edit segment-text.py with marimo"
            echo "  transcribe     - Edit transcribe.py with marimo"
            echo "  synthesize     - Edit synthesize.py with marimo"
            echo "  voice-change   - Edit voice-change.py with marimo"
            echo "  main           - Run main.py"
            echo "  remotion-dev    - Start Remotion dev server"
            echo "  remotion-render - Render video with Remotion"
            echo ""
            echo "To activate the Python virtual environment:"
            echo "  cd processor && source .venv/bin/activate"
            echo ""
            echo "Or use uv run directly:"
            echo "  cd processor && uv run python script.py"
            echo ""
            echo "Available tools:"
            echo "  - Python 3.13 (managed by uv)"
            echo "  - All Python packages from pyproject.toml (via uv)"
            echo "  - Node.js (for book scripts)"
            echo "  - FFmpeg, SoX (audio processing)"
          '';

          # Set environment variables
          # Clear LD_LIBRARY_PATH - Nix packages work correctly when it's empty
          # Setting it explicitly causes glibc symbol conflicts
          LD_LIBRARY_PATH = "";
        };
      });
}

