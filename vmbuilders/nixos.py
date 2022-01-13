#!/usr/bin/env python3

import os, platform, shutil, subprocess, tempfile, urllib.request

# Where to find ISOs and checksums for Intel/ARM NixOS install CD images.
# For Intel, there is a public managed latest iso. For ARM, we have to
# hand-select a decent Hydra run for now. We only need a recent enough ISO to
# download and install the real packages, so this isn't the end of the world.
URLS = {
    "i386": "https://channels.nixos.org/nixos-21.11/latest-nixos-minimal-x86_64-linux.iso",
    "arm": "https://hydra.nixos.org/build/164067542/download/1/nixos-minimal-21.11.335153.bd11019686a-aarch64-linux.iso",
}


def download_iso_to(iso_fname):
    assert platform.system() == "Darwin"
    url = URLS[platform.processor()]
    print("Downloading ISO...")
    urllib.request.urlretrieve(url, iso_fname)


def mount_iso(iso_fname, mount_dir):
    print("Mounting ISO...")
    result = subprocess.run(
        ["hdiutil", "attach", "-nomount", iso_fname], check=True, capture_output=True
    )
    disk = result.stdout.decode().split("\n")[0].split()[0]
    subprocess.run(["mount", "-t", "cd9660", disk, mount_dir], check=True)
    return disk


def copy_files(mount_dir, work_dir):
    print("Copying kernel and initrd...")
    shutil.copyfile(f"{mount_dir}/boot/bzImage", f"{work_dir}/kernel")
    shutil.copyfile(f"{mount_dir}/boot/initrd", f"{work_dir}/initrd")


def unmount_iso(disk, mount_dir):
    print("Unmounting ISO...")
    subprocess.run(["umount", mount_dir])
    subprocess.run(["hdiutil", "detach", disk])


def main():
    work_dir = "nixos-iso"
    try:
        os.mkdir(work_dir)
    except FileExistsError:
        pass
    iso_file = f"{work_dir}/nixos-install.iso"
    download_iso_to(iso_file)
    mount_dir = tempfile.mkdtemp()
    disk = mount_iso(iso_file, mount_dir)
    copy_files(mount_dir, work_dir)
    unmount_iso(disk, mount_dir)
    os.rmdir(mount_dir)
    print("Done")


main()
