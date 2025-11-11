# Alternative shell.nix for users not using flakes
# Usage: nix-shell

let
  # Pin nixpkgs to a specific version for reproducibility
  # You can update this to a newer commit if needed
  pkgs = import (fetchTarball
    "https://github.com/NixOS/nixpkgs/archive/nixos-unstable.tar.gz") { };

in pkgs.mkShell {
  buildInputs = [
    # Base Python 3.13 interpreter - uv manages all packages
    pkgs.python313

    # C dependencies for aeneas
    pkgs.espeak-ng
    pkgs.ffmpeg
    pkgs.sox

    # Node.js
    pkgs.nodejs_20
    pkgs.nodePackages.npm

    # Development tools
    pkgs.git
    pkgs.curl
    pkgs.uv
  ];

  shellHook = ''
    echo "🐉 Wenyan Book Video Development Environment (nix-shell)"
    echo ""
    echo "Python: $(python --version)"
    echo "uv: $(uv --version)"
    echo "Node.js: $(node --version)"
    echo ""

    # Configure uv to use Nix Python
    export UV_PYTHON="${pkgs.python313}/bin/python3"

    # Create executable commands for marimo scripts
    segment-text() {
      cd processor && uv run marimo edit segment-text.py --watch
    }

    audio-femalize() {
      cd processor && uv run marimo edit audio-femalize.py --watch
    }

    main() {
      cd processor && uv run python main.py
    }

    # Export functions so they're available in the shell
    export -f segment-text audio-femalize main

    echo "Available commands:"
    echo "  segment-text    - Edit segment-text.py with marimo"
    echo "  audio-femalize  - Edit audio-femalize.py with marimo"
    echo "  main            - Run main.py"
    echo ""
    echo "Then in processor directory:"
    echo "  uv sync  # or uv pip install -e ."
    echo ""
    echo "Note: Use 'nix develop' with flake.nix for better integration"
  '';

  AENEAS_USE_ESPEAKNG = "1";
  LD_LIBRARY_PATH = "${pkgs.lib.makeLibraryPath
    (with pkgs; [ pkgs.stdenv.cc.cc pkgs.espeak-ng pkgs.ffmpeg ])}";
}

