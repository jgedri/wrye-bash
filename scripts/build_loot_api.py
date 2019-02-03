#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import platform
import subprocess
import sys
import tempfile
import urllib

import _winreg

LOOT_API_VERSION = "3.1.1"
LOOT_API_REVISION = "f97de90"

SCRIPTS_PATH = os.path.dirname(os.path.abspath(__file__))
MOPY_PATH = os.path.join(SCRIPTS_PATH, "..", "Mopy")
sys.path.append(MOPY_PATH)

try:
    import loot_api
except ImportError:
    print "Importing the loot api failed."
    loot_api = None


def is_os_64bit():
    return platform.machine().endswith("64")


def is_msvc_redist_installed(major, minor, build):
    if is_os_64bit():
        sub_key = "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64"
    else:
        sub_key = "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x86"
    try:
        key_handle = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, sub_key)
        runtime_installed = _winreg.QueryValueEx(key_handle, "Installed")[0]
        installed_major = _winreg.QueryValueEx(key_handle, "Major")[0]
        installed_minor = _winreg.QueryValueEx(key_handle, "Minor")[0]
        installed_build = _winreg.QueryValueEx(key_handle, "Bld")[0]
        if runtime_installed != 0:
            print "Found MSVC 2015 redistributable version {0}.{1}.{2}".format(
                installed_major, installed_minor, installed_build
            )
        return (
            runtime_installed != 0
            and installed_major >= major
            and installed_minor >= minor
            and installed_build >= build
        )
    except WindowsError:
        return False


def install_msvc_redist(dl_dir):
    url = (
        "https://download.microsoft.com/download/6/A/A/"
        "6AA4EDFF-645B-48C5-81CC-ED5963AEAD48/vc_redist.x86.exe"
    )
    dl_file = os.path.join(dl_dir, "vc_redist.x86.exe")
    print "Downloading the MSVC 2015 redistributable..."
    urllib.urlretrieve(url, dl_file)  # fixme XXX: get a progress meter
    print "Installing the MSVC 2015 redistributable..."
    subprocess.call([dl_file, "/quiet"])
    os.remove(dl_file)


def is_loot_api_installed(version, revision):
    return (
        loot_api is not None
        and loot_api.WrapperVersion.string() == version
        and loot_api.WrapperVersion.revision == revision
    )


def install_loot_api(version, revision, dl_dir, destination_path):
    url = (
        "https://github.com/loot/loot-api-python/releases/"
        "download/{0}/loot_api_python-{0}-0-g{1}_master-win32.7z".format(
            version, revision
        )
    )
    archive_path = os.path.join(dl_dir, "archive.7z")
    seven_zip_folder = os.path.join(MOPY_PATH, "bash", "compiled")
    seven_zip_path = os.path.join(seven_zip_folder, "7z.exe")
    loot_api_dll = os.path.join(destination_path, "loot_api.dll")
    loot_api_pyd = os.path.join(destination_path, "loot_api.pyd")

    if os.path.exists(loot_api_dll):
        os.remove(loot_api_dll)
    if os.path.exists(loot_api_pyd):
        os.remove(loot_api_pyd)
    print 'Downloading LOOT API Python wrapper from "{}"...'.format(url)
    urllib.urlretrieve(url, archive_path)  # fixme XXX: get a progress meter
    print "Extracting LOOT API Python wrapper to " + destination_path
    subprocess.call(
        [
            seven_zip_path,
            "e",
            archive_path,
            "-y",
            "-o" + destination_path,
            "*/loot_api.dll",
            "*/loot_api.pyd",
        ]
    )
    os.remove(archive_path)


def main():
    download_dir = tempfile.mkdtemp()

    if is_msvc_redist_installed(14, 0, 24215):
        print "MSVC 2015 Redistributable is already installed."
    else:
        install_msvc_redist(download_dir)

    if is_loot_api_installed(LOOT_API_VERSION, LOOT_API_REVISION):
        print "LOOT API wrapper {}.{} is already installed.".format(
            LOOT_API_VERSION, LOOT_API_REVISION
        )
    else:
        install_loot_api(LOOT_API_VERSION, LOOT_API_REVISION, download_dir, MOPY_PATH)

    os.rmdir(download_dir)


if __name__ == "__main__":
    main()
