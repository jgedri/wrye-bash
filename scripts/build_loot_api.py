#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import platform
import subprocess
import sys
import tempfile

import _winreg
import build_utils

LOOT_API_VERSION = "3.1.1"
LOOT_API_REVISION = "f97de90"

SCRIPTS_PATH = os.path.dirname(os.path.abspath(__file__))
MOPY_PATH = os.path.join(SCRIPTS_PATH, "..", "Mopy")
sys.path.append(MOPY_PATH)

try:
    import loot_api
except ImportError:
    loot_api = None


def setup_parser(parser):
    parser.add_argument(
        "-lv",
        "--loot-version",
        default=LOOT_API_VERSION,
        help="Which version of the LOOT Python API to use.",
    )
    parser.add_argument(
        "-lr",
        "--loot-revision",
        default=LOOT_API_REVISION,
        help="Which revision of the LOOT Python API to use.",
    )
    parser.add_argument(
        "-lm",
        "--loot-msvc",
        help="The url of the msvc redistributable to download and install. "
        "If this is given then this redist is always installed "
        "regardless of the current one.",
    )


def is_msvc_redist_installed(major, minor, build):
    if platform.machine().endswith("64"):  # check if os is 64bit
        sub_key = "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x64"
    else:
        sub_key = "SOFTWARE\\Microsoft\\VisualStudio\\14.0\\VC\\Runtimes\\x86"
    logging.debug("Using MSVC registry key: {}".format(sub_key))
    try:
        key_handle = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, sub_key)
        runtime_installed = _winreg.QueryValueEx(key_handle, "Installed")[0]
        installed_major = _winreg.QueryValueEx(key_handle, "Major")[0]
        installed_minor = _winreg.QueryValueEx(key_handle, "Minor")[0]
        installed_build = _winreg.QueryValueEx(key_handle, "Bld")[0]
        if runtime_installed != 0:
            msg = "Found MSVC Redistributable version {0}.{1}.{2}".format(
                installed_major, installed_minor, installed_build
            )
            logging.info(msg)
        return (
            runtime_installed != 0
            and installed_major >= major
            and installed_minor >= minor
            and installed_build >= build
        )
    except WindowsError as exc:
        logging.debug("WindowsError during MSVC registry search: " + str(exc))
        return False


def install_msvc_redist(dl_dir, url=None):
    if url is None:
        url = (
            "https://download.microsoft.com/download/6/A/A/"
            "6AA4EDFF-645B-48C5-81CC-ED5963AEAD48/vc_redist.x86.exe"
        )
    logging.info("Downloading MSVC Redist from {}".format(url))
    dl_file = os.path.join(dl_dir, "vc_redist.exe")

    logging.debug("Downloading MSVC Redist to {}".format(dl_file))
    build_utils.download_file(url, dl_file)

    logging.info("Installing the MSVC redistributable...")
    command = [dl_file, "/quiet"]
    logging.debug("Running command '{}'".format(" ".join(command)))
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
    archive_path = os.path.join(dl_dir, "loot_api.7z")
    seven_zip_folder = os.path.join(MOPY_PATH, "bash", "compiled")
    seven_zip_path = os.path.join(seven_zip_folder, "7z.exe")
    loot_api_dll = os.path.join(destination_path, "loot_api.dll")
    loot_api_pyd = os.path.join(destination_path, "loot_api.pyd")

    if os.path.exists(loot_api_dll):
        os.remove(loot_api_dll)
    if os.path.exists(loot_api_pyd):
        os.remove(loot_api_pyd)

    logging.info("Downloading LOOT API Python wrapper from {}".format(url))
    logging.debug("Downloading MSVC Redist to {}".format(archive_path))
    build_utils.download_file(url, archive_path)

    logging.info("Extracting LOOT API Python wrapper to " + destination_path)
    command = [
        seven_zip_path,
        "e",
        archive_path,
        "-y",
        "-o" + destination_path,
        "*/loot_api.dll",
        "*/loot_api.pyd",
    ]
    logging.debug("Running command {}".format(" ".join(command)))
    subprocess.call(command, stdout=subprocess.PIPE)

    os.remove(archive_path)


def main(args):
    download_dir = tempfile.mkdtemp()

    # if url is given in command line, always dl and install
    if not is_msvc_redist_installed(14, 0, 24215) or args.loot_msvc is not None:
        install_msvc_redist(download_dir, args.loot_msvc)

    if is_loot_api_installed(args.loot_version, args.loot_revision):
        logging.info(
            "Found LOOT API wrapper version {}.{}".format(
                args.loot_version, args.loot_revision
            )
        )
    else:
        install_loot_api(args.loot_version, args.loot_revision, download_dir, MOPY_PATH)

    os.rmdir(download_dir)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        description="Downloads and sets up the LOOT Python API."
    )
    build_utils.setup_common_parser(argparser)
    setup_parser(argparser)
    parsed_args = argparser.parse_args()

    build_utils.setup_log(
        logging.getLogger(),
        verbosity=parsed_args.verbosity,
        logfile=parsed_args.logfile,
    )

    main(parsed_args)
