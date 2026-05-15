{pkgs}: {
  deps = [
    pkgs.xorg.libXtst
    pkgs.xorg.libXext
    pkgs.xorg.libX11
    pkgs.expat
    pkgs.alsa-lib
    pkgs.cairo
    pkgs.pango
    pkgs.mesa
    pkgs.libxkbcommon
    pkgs.xorg.libxcb
    pkgs.xorg.libXrandr
    pkgs.xorg.libXfixes
    pkgs.xorg.libXdamage
    pkgs.xorg.libXcomposite
    pkgs.libdrm
    pkgs.cups
    pkgs.atk
    pkgs.nss
    pkgs.nspr
  ];
}
