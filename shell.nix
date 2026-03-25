{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    (python3.withPackages (py: [
      py.moderngl
      py.moderngl-window
      py.pillow
      py.pyrr
    ]))
  ];
}
