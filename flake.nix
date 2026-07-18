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
            # Core libraries for compiled Python packages
            stdenv
            gfortran
            libz
            glib
            openblas
            gcc
            pkg-config
            libffi
            openssl
          ];

          shellHook = ''
            export CC=${pkgs.gcc}/bin/gcc
            export CXX=${pkgs.gcc}/bin/g++
            export FC=${pkgs.gfortran}/bin/gfortran
            export NPY_NUM_BUILD_JOBS=$(nproc)
            export CFLAGS="-I${pkgs.openblas}/include -I${pkgs.libffi}/include"
            export LDFLAGS="-L${pkgs.openblas}/lib -L${pkgs.libffi}/lib"
            export PKG_CONFIG_PATH="${pkgs.openblas}/lib/pkgconfig:${pkgs.openssl}/lib/pkgconfig:$PKG_CONFIG_PATH"
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:${pkgs.libz}/lib:${pkgs.glib}/lib:$LD_LIBRARY_PATH"
            echo "Python $(python --version)"
            echo "uv $(uv --version)"
            echo "Development environment ready. Run 'make setup' to install dependencies."
          '';
        };
      }
    );
}
