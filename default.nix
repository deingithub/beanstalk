with import (builtins.fetchTarball {
  # nixpkgs master on 2021-06-24
  url =
    "https://github.com/NixOS/nixpkgs/tarball/5c7023e5f051e1f534c5bbac50f0d18320823b28";
  sha256 = "0v46qrjraamhxcf741z7k7fjpkgk2a3i3kjsa9q0jq18vcb2hwgn";
}) { };


poetry2nix.mkPoetryApplication {
  projectDir = ./.;
  doCheck = false;
  python = python39;
  nativeBuildInputs = [ imagemagick wmctrl gnome3.zenity youtube-dl ];
}
