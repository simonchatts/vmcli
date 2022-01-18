#!/usr/bin/env python3

import os, platform, re, shutil, subprocess, tempfile, time, urllib.request

# Where to find ISOs and checksums for Intel/ARM NixOS install CD images.
# For Intel, there is a public managed latest iso. For ARM, we have to
# hand-select a decent Hydra run for now. We only need a recent enough ISO to
# download and install the real packages, so this isn't the end of the world.
URLS = {
    "i386": "https://channels.nixos.org/nixos-21.11/latest-nixos-minimal-x86_64-linux.iso",
    "arm": "https://hydra.nixos.org/build/164067542/download/1/nixos-minimal-21.11.335153.bd11019686a-aarch64-linux.iso",
}

# What to call various files/directories that we download or create
WORK_DIR = "nixos-install"
ISO_FNAME = "nixos-install.iso"
KERNEL = "iso-kernel"
INITRD = "iso-initrd"
DISK_IMG = "disk.img"
BOOT_INSTALL_SCRIPT = "boot-installer"


def download_iso():
    assert platform.system() == "Darwin"
    url = URLS[platform.processor()]
    print("Downloading ISO...")
    percent = None

    def report(chunk, size, total):
        nonlocal percent
        new_percent = int(chunk * size * 100 / total)
        if new_percent != percent:
            percent = new_percent
            print(f"\r[{percent}% downloaded]", end="")

    urllib.request.urlretrieve(url, ISO_FNAME, reporthook=report)
    print(f"\nISO downloaded to {ISO_FNAME}")


def mount_iso(mount_dir):
    print("Mounting ISO...")
    result = subprocess.run(
        ["hdiutil", "attach", "-nomount", ISO_FNAME], check=True, capture_output=True
    )
    disk = result.stdout.decode().split("\n")[0].split()[0]
    time.sleep(1)  # Seems to help on fast M1 macs - mounting too soon doesn't work
    subprocess.run(["mount", "-t", "cd9660", disk, mount_dir], check=True)
    return disk


def unmount_iso(disk, mount_dir):
    print("Unmounting ISO...")
    subprocess.run(["umount", mount_dir], check=True)
    subprocess.run(["hdiutil", "detach", disk], check=True)


def copy_files(mount_dir):
    print("Copying kernel and initrd...")
    # Kernel might be bzImage or Image, depending on architecture
    kernel_path = f"{mount_dir}/boot/bzImage"
    if not os.path.exists(kernel_path):
        kernel_path = f"{mount_dir}/boot/Image"
    shutil.copyfile(kernel_path, KERNEL)
    shutil.copyfile(f"{mount_dir}/boot/initrd", INITRD)
    # Extract kernel command line arguments from grub
    grub_cfg = open(f"{mount_dir}/EFI/boot/grub.cfg").read()
    match = re.search(r"init=[\w/.-]* *root=LABEL=[\w/.-]*", grub_cfg)
    return match.group(0)


def write_boot_install_script(cmdline, disk_size=4):
    print("Creating disk image...")
    subprocess.run(
        ["dd", "if=/dev/zero", f"of={DISK_IMG}", "bs=1g", f"count={disk_size}"],
        check=True,
    )

    print(f"Creating wrapper script wrapper_fname")
    # Create a wrapper to run vmcli on the installer CD
    args = (
        ("--cpu-count", str(disk_size)),
        ("--memory-size", "4096"),
        ("--disk", DISK_IMG),
        ("--cdrom", ISO_FNAME),
        ("--kernel", KERNEL),
        ("--initrd", INITRD),
        ("--cmdline", f'"{cmdline} console=hvc0 loglevel=4"'),
    )
    args = " ".join([" ".join(pair) for pair in args])
    with open(BOOT_INSTALL_SCRIPT, "w") as f:
        f.write(
            f"""#!/bin/sh
cd {os.getcwd()}
echo Booting NixOS install CD, please be patient...
exec vmcli {args}
"""
        )
    os.chmod(BOOT_INSTALL_SCRIPT, 0o755)


def write_vm_conf():
    with open("vm.conf", "w") as f:
        f.write(
            """\
kernel=kernel
initrd=initrd
cmdline=init=/nix/var/nix/profiles/system/init console=hvc0 loglevel=4
cpu-count=4
memory-size=4096
disk=disk.img
"""
        )


def main():
    try:
        os.mkdir(WORK_DIR)
    except FileExistsError:
        pass
    os.chdir(WORK_DIR)
    download_iso()
    mount_dir = tempfile.mkdtemp()
    disk = mount_iso(mount_dir)
    cmdline = copy_files(mount_dir)
    write_boot_install_script(cmdline)
    unmount_iso(disk, mount_dir)
    os.rmdir(mount_dir)
    subprocess.run(["../vmbuilders/install-nixos.exp"], check=True)
    write_vm_conf()
    print("""
Now set $VMCTLDIR to a directory where your VMs will live, create a directory
$VMCTLDIR/<name-of-vm>, and copy the following files into there:

    nixos-install/{disk.img, vm.conf, kernel, initrd}

You can then start the VM with "vmctl start <name-of-vm>", and connect using
either:

 - "vmctl attach <name-of-vm>" to log in via console (exit with "C-a d")
 - "vmctl ip <name-of-vm>" and ssh-ing in as root to that IP address
 - If that fails, do "arp -a" and pick the latest 192.168.64.* IP address

 The disk defaults to only 4G, but you can increase it any time, when the VM is
 powered off, with eg

   dd if=/dev/null of=$VMCTLDIR/<name-of-vm>/disk.img bs=1g count=0 seek=16

for 16G (final parameter).
""")

main()
