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

import os
import shutil
import sys
import tempfile

import build_utils

SCRIPTS_PATH = os.path.dirname(os.path.abspath(__file__))
MOPY_PATH = os.path.join(SCRIPTS_PATH, u"..", u"Mopy")
sys.path.append(MOPY_PATH)

try:
    import loot_api
except ImportError:
    import build_loot_api

    build_loot_api.main()
    import loot_api


GAME_DATA = [
    (u"Oblivion", "Oblivion.esm", "oblivion", loot_api.GameType.tes4),
    (u"Skyrim", "Skyrim.esm", "skyrim", loot_api.GameType.tes5),
    (u"Skyrim Special Edition", "Skyrim.esm", "skyrimse", loot_api.GameType.tes5se),
    (u"Fallout3", "Fallout3.esm", "fallout3", loot_api.GameType.fo3),
    (u"FalloutNV", "FalloutNV.esm", "falloutnv", loot_api.GameType.fonv),
    (u"Fallout4", "Fallout4.esm", "fallout4", loot_api.GameType.fo4),
]


def mock_game_install(master_file_name):
    game_path = tempfile.mkdtemp()
    os.mkdir(os.path.join(game_path, u"Data"))
    open(os.path.join(game_path, u"Data", master_file_name), "a").close()
    return game_path


def download_masterlist(repository, destination_path):
    url = u"https://raw.githubusercontent.com/loot/{}/v0.13/masterlist.yaml".format(
        repository
    )
    build_utils.download_file(url, destination_path)


def main():
    print u"Loaded the LOOT API v{0} using wrapper version {1}".format(
        loot_api.Version.string(), loot_api.WrapperVersion.string()
    )

    for game_name, master_name, repository, game_type in GAME_DATA:
        game_install_path = mock_game_install(master_name)

        masterlist_path = os.path.join(game_install_path, u"masterlist.yaml")
        game_dir = os.path.join(MOPY_PATH, u"Bash Patches", game_name)
        taglist_path = os.path.join(game_dir, u"taglist.yaml")
        if not os.path.exists(game_dir):
            print (
                u"Skipping taglist for {} as its output "
                u"directory does not exist".format(game_name)
            )
            continue
        download_masterlist(repository, masterlist_path)
        loot_api.initialise_locale("")
        loot_game = loot_api.create_game_handle(game_type, game_install_path)
        loot_db = loot_game.get_database()
        loot_db.load_lists(masterlist_path)
        loot_db.write_minimal_list(taglist_path, True)
        print u"{} masterlist converted.".format(game_name)

        shutil.rmtree(game_install_path)

    print u"Taglist generator finished."


if __name__ == "__main__":
    main()
