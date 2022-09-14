# vmcli flake - IMPURE, requires xcode tools to be installed
{
  description = "Run VMs on macOS using Virtualization.framework";
  outputs = { self, nixpkgs }:
    let
      # Metadata
      pname = "vmcli";
      version = "1.0.4";

      # Build and install
      install = { stdenv, lib, ... }: stdenv.mkDerivation {
        inherit pname version;
        src = builtins.filterSource
          (path: _: builtins.match ".*/(vmcli|vmctl)($|/Sources.*|/.*\.(swift|resolved|entitlements|sh))" path != null)
          ./.;
        installPhase = ''
          # This is IMPURE and requires xcode tools to be installed
          PATH=$PATH:/usr/bin
          (cd vmcli; swift build -c release --disable-sandbox)
          mkdir -p $out/bin
          cp vmcli/.build/release/vmcli $out/bin
          cp vmctl/vmctl.sh $out/bin/vmctl
          chmod +x $out/bin/{vmcli,vmctl}
          codesign -s - --entitlements vmcli/vmcli.entitlements $out/bin/vmcli
        '';
      };

      # Boilerplate to cover both x86 and arm64
      systems = [ "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system:
        let pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        }; in f pkgs);
    in
    {
      # Flake outputs
      overlay = final: prev: { "${pname}" = final.callPackage install { }; };
      packages = forAllSystems (pkgs: { "${pname}" = pkgs."${pname}"; });
      defaultPackage = forAllSystems (pkgs: pkgs."${pname}");
    };
}
