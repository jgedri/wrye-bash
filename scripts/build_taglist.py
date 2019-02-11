# -*- coding: utf-8 -*-
#
# =============================================================================
#
# Taglist Generator
#
# This script generates taglist.yaml files in Mopy/Bashed Patches game
# subdirectories using the LOOT API and masterlists. The LOOT API Python module
# must be installed in the Mopy folder (use the build_loot_api.py script).
# The script will skip generating taglists for any games that do not have a
# folder in Mopy/Bashed Patches that matches the first tuple element in the
# gamesData tuples below, so if adding a taglist for a new game, create the
# folder first.
#
# Usage:
#   build_taglist.py
#
# =============================================================================

import argparse
import logging
import os
import shutil
import sys
import tempfile

import build_loot_api
import build_utils

SCRIPTS_PATH = os.path.dirname(os.path.abspath(__file__))
MOPY_PATH = os.path.join(SCRIPTS_PATH, u"..", u"Mopy")
sys.path.append(MOPY_PATH)

try:
    import loot_api
except ImportError:
    loot_api = None


def setup_parser(parser):
    parser.add_argument(
        "-mv",
        "--masterlist-version",
        default="0.13",
        help="Which loot masterlist version to download.",
    )


def mock_game_install(master_file_name):
    game_path = tempfile.mkdtemp()
    os.mkdir(os.path.join(game_path, u"Data"))
    open(os.path.join(game_path, u"Data", master_file_name), "a").close()
    return game_path


def download_masterlist(repository, version, dl_path):
    url = "https://raw.githubusercontent.com/loot/{}/v{}/masterlist.yaml".format(
        repository, version
    )
    logging.info("Downloading {} masterlist from {}".format(repository, url))

    logging.debug("Downloading {} masterlist to {}".format(repository, dl_path))
    build_utils.download_file(url, dl_path)


def main(args):
    logging.debug(
        u"Loaded the LOOT API v{} using wrapper version {}".format(
            loot_api.Version.string(), loot_api.WrapperVersion.string()
        )
    )

    game_data = [
        (u"Oblivion", "Oblivion.esm", "oblivion", loot_api.GameType.tes4),
        (u"Skyrim", "Skyrim.esm", "skyrim", loot_api.GameType.tes5),
        (u"Skyrim Special Edition", "Skyrim.esm", "skyrimse", loot_api.GameType.tes5se),
        (u"Fallout3", "Fallout3.esm", "fallout3", loot_api.GameType.fo3),
        (u"FalloutNV", "FalloutNV.esm", "falloutnv", loot_api.GameType.fonv),
        (u"Fallout4", "Fallout4.esm", "fallout4", loot_api.GameType.fo4),
    ]

    for game_name, master_name, repository, game_type in game_data:
        game_install_path = mock_game_install(master_name)

        masterlist_path = os.path.join(game_install_path, u"masterlist.yaml")
        game_dir = os.path.join(MOPY_PATH, u"Bash Patches", game_name)
        taglist_path = os.path.join(game_dir, u"taglist.yaml")
        if not os.path.exists(game_dir):
            logging.error(
                u"Skipping taglist for {} as its output "
                u"directory does not exist".format(game_name)
            )
            continue
        download_masterlist(repository, args.masterlist_version, masterlist_path)

        loot_api.initialise_locale("")
        loot_game = loot_api.create_game_handle(game_type, game_install_path)
        loot_db = loot_game.get_database()
        loot_db.load_lists(masterlist_path)
        loot_db.write_minimal_list(taglist_path, True)
        logging.info(u"{} masterlist converted.".format(game_name))

        shutil.rmtree(game_install_path)


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(
        description="Generate and update taglists for supported games."
    )
    build_utils.setup_common_parser(argparser)
    setup_parser(argparser)

    if loot_api is None:
        loot_group = argparser.add_argument_group(
            title="loot api arguments",
            description="LOOT API could not be found and will be installed.",
        )
        build_loot_api.setup_parser(loot_group)

    parsed_args = argparser.parse_args()

    build_utils.setup_log(
        logging.getLogger(),
        verbosity=parsed_args.verbosity,
        logfile=parsed_args.logfile,
    )

    if loot_api is None:
        build_loot_api.main(parsed_args)

    main(parsed_args)
