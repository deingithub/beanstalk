with import (builtins.fetchTarball {
  # nixpkgs master on 2020-10-14
  url =
    "https://github.com/NixOS/nixpkgs/tarball/692d219a9312fbe3f8b34858a7ca0e32fb72bd07";
  sha256 = "1c5sm789yr6v34lhjscmn1c93ix5cqw6cksjc2n0lrm8hjwfllry";
}) { };


poetry2nix.mkPoetryApplication {
  projectDir = ./.;
  python = python39;
  nativeBuildInputs = [ imagemagick wmctrl gnome3.zenity ];
}
