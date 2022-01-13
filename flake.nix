# vmcli flake
#
# If you have Nix installed (https://nixos.org/download.html#nix-quick-install)
# then this enables you to install vmcli via
#
#   nix profile install github:simonchatts/vmcli#.
#
# Note: like all Swift projects using the Apple toolchain, this flake has to be impure,
# since Apple's license does not permit the toolchain to be pinned in nixpkgs.
{
  description = "Run VMs on macOS using Virtualization.framework";
  outputs = { self, nixpkgs }:
    let
      # Metadata.
      pname = "vmcli";
      version = "1.0.4";

      # Build and install.
      install = { stdenv, lib, ... }: stdenv.mkDerivation {
        inherit pname version;
        # Source files - skip relatively big directories out of hygiene.
        src = builtins.filterSource
          (path: _: builtins.match ".*/(.git|docs|\.?build)" path == null) ./.;
        # The build is impure, requiring the Xcode command line tools to be installed.
        configurePhase = ''
          /usr/bin/xcrun --find xctest >/dev/null || (
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            echo "!! You must have Xcode installed to build this flake. Just having the    !!"
            echo "!! 'Xcode Command Line Tools' won't suffice, sorry. You also need to set !!"
            echo "!! the 'Command Line Tools' option in Xcode prefences / 'Locations' tab. !!"
            echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
            exit 1)
          '';
        buildPhase = ''
          (cd vmcli; PATH=/usr/bin xcrun swift build -c release --disable-sandbox)
        '';
        # Install.
        installPhase = ''
          mkdir -p $out/bin
          cp vmcli/.build/release/vmcli $out/bin
          cp vmctl/vmctl.sh $out/bin/vmctl
          chmod +x $out/bin/vmctl
        '';
        # Code signing has to come after fixup phase, since this alters the binary. Also impure.
        postFixup = ''
          /usr/bin/codesign --force --sign - --entitlements vmcli/vmcli.entitlements $out/bin/vmcli
        '';
      };

      # Boilerplate to cover both x86 and arm64.
      systems = [ "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system:
        let pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        }; in f pkgs);
    in
    {
      # Flake outputs.
      overlay = final: prev: { "${pname}" = final.callPackage install { }; };
      packages = forAllSystems (pkgs: { "${pname}" = pkgs."${pname}"; });
      defaultPackage = forAllSystems (pkgs: pkgs."${pname}");
    };
}
