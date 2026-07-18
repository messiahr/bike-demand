{
  description = "Development environment for bike-demand";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python313
            uv
            git
            ruff
            pre-commit
            pyright
          ];

          shellHook = ''
            echo "Python $(python --version)"
            echo "uv $(uv --version)"
            echo "Development environment ready. Run 'make setup' to install dependencies."
          '';
        };
      }
    );
}
