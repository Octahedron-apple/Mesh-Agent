{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  # Python and basic development tools
  packages = with pkgs; [
    python3
  ];

  # When running pre-compiled binary wheels from PyPI in a virtual environment on NixOS, 
  # they often fail to find dynamically linked C/C++ libraries. We fix this by manually 
  # exposing these common libraries in the LD_LIBRARY_PATH.
  shellHook = ''
    export LD_LIBRARY_PATH=${pkgs.lib.makeLibraryPath [
      pkgs.stdenv.cc.cc.lib # libstdc++.so.6
      pkgs.zlib             # libz.so.1
      pkgs.glib             # libglib-2.0.so.0
      pkgs.xorg.libX11      # X11 libraries (common for GUI/plotting like matplotlib)
      pkgs.xorg.libXext
      pkgs.xorg.libXrender
      pkgs.xorg.libICE
      pkgs.xorg.libSM
      pkgs.libGL            # OpenGL (common for 3d/image processing)
    ]}:$LD_LIBRARY_PATH

    # Nix sets SOURCE_DATE_EPOCH which can cause issues with pip building wheels.
    # Unsetting it fixes timestamp issues with python zip files.
    unset SOURCE_DATE_EPOCH
  '';
}
