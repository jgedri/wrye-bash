#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# GPL License and Copyright Notice ============================================
#  This file is part of Wrye Bash.
#
#  Wrye Bash is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  Wrye Bash is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Wrye Bash; if not, write to the Free Software Foundation,
#  Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
#  Wrye Bash copyright (C) 2005-2009 Wrye, 2010-2019 Wrye Bash Team
#  https://github.com/wrye-bash
#
# =============================================================================

"""
Python script to package up the various Wrye Bash files into archives for
release.  More detailed help can be found by passing the --help or -h
command line arguments.

It is assumed that if you have multiple version of Python installed on your
computer, then you also have Python Launcher for Windows installed.  This
will ensure that this script will be launched with the correct version of
Python, via shebang lines.  Python Launcher for Windows comes with Python
3.3+, but will need to be installed manually otherwise.
"""


# Imports ---------------------------------------------------------------------
from __future__ import print_function

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from contextlib import contextmanager

import build_utils

try:
    import scandir

    _walkdir = scandir.walk
except ImportError:
    _walkdir = os.walk

try:
    # needed for the Installer version to find NSIS
    import _winreg
except ImportError:
    _winreg = False

try:
    # needed for the Standalone version
    import py2exe
except ImportError:
    py2exe = False

try:
    # needed to ensure non-repo file don't get packaged
    import git
except ImportError:
    git = False


# setup some global paths that all functions will use
SCRIPTS_PATH = os.path.dirname(os.path.abspath(__file__))
DIST_PATH = os.path.join(SCRIPTS_PATH, u"dist")
ROOT_PATH = os.path.abspath(os.path.join(SCRIPTS_PATH, u".."))
MOPY_PATH = os.path.join(ROOT_PATH, u"Mopy")
APPS_PATH = os.path.join(MOPY_PATH, u"Apps")

if sys.platform.lower().startswith("linux"):
    EXE_7z = u"7z"
else:
    EXE_7z = os.path.join(MOPY_PATH, u"bash", u"compiled", u"7z.exe")

# global pipe file for log output
LOG_PIPE = None
NSIS_VERSION = "3.04"


class NonRepoAction(object):
    __slots__ = []

    # 'Enum' for options for non-repo files
    MOVE = "MOVE"
    COPY = "COPY"
    NONE = "NONE"


def get_version_info(version, padding=4):
    """
       Generates version strings from the passed parameter.
       Returns the a string used for the 'File Version' property
       of the built WBSA.
       For example, a version of 291 would with default padding
       would return '291.0.0.0'
    """
    v = version.split(u".")
    if len(v) == 2:
        if len(v[1]) == 12 and float(v[1]) >= 201603171733L:  # 2016/03/17 17:33
            v, v1 = v[:1], v[1]
            v.extend((v1[:4], v1[4:8], v1[8:]))
    # If version is too short, pad it with 0's
    abspad = abs(padding)
    delta = abspad - len(v)
    if delta > 0:
        pad = ["0"] * delta
        if padding > 0:
            v.extend(pad)
        else:
            v = pad + v
    # If version is too long, warn and truncate
    if delta < 0:
        lprint(
            "WARNING: The version specified ({version}) has too many"
            " version pieces.  The extra pieces will be truncated."
            "".format(version=version)
        )
        v = v[:abspad]
    # Verify version pieces are actually integers, as non-integer values will
    # cause much of the 'Details' section of the built exe to be non-existant
    newv = []
    error = False
    for x in v:
        try:
            int(x)
            newv.append(x)
        except ValueError:
            error = True
            newv.append(u"0")
    if error:
        lprint(
            "WARNING: The version specified ({version}) does not convert "
            "to integer values.".format(version=version)
        )
    file_version = u".".join(newv)
    lprint("Using file version:", file_version)
    return file_version


def rm(node):
    """Removes a file or directory if it exists"""
    if os.path.isfile(node):
        os.remove(node)
    elif os.path.isdir(node):
        shutil.rmtree(node)


def mv(node, dst):
    """Moves a file or directory if it exists"""
    if os.path.exists(node):
        shutil.move(node, dst)


def cpy(src, dst):
    """Moves a file to a destination, creating the target
       directory as needed."""
    if os.path.isdir(src):
        if not os.path.exists(dst):
            os.makedirs(dst)
    else:
        # file
        dstdir = os.path.dirname(dst)
        if not os.path.exists(dstdir):
            os.makedirs(dstdir)
        shutil.copy2(src, dst)


def lprint(*args, **kwdargs):
    """Helper function to print to both the build log file and the console.
       Needs the print function to work properly."""
    print(*args, **kwdargs)
    if LOG_PIPE:
        kwdargs["file"] = LOG_PIPE
        print("[build_package]:", *args, **kwdargs)
        LOG_PIPE.flush()


def real_sys_prefix():
    if hasattr(sys, "real_prefix"):  # running in virtualenv
        return sys.real_prefix
    elif hasattr(sys, "base_prefix"):  # running in venv
        return sys.base_prefix
    else:
        return sys.prefix


def pack_7z(file_list, archive, list_path):
    with open(list_path, "wb") as out:
        for node in sorted(file_list, key=unicode.lower):
            out.write(node)
            out.write("\n")
    cmd_7z = [EXE_7z, "a", "-mx9", archive, "@%s" % list_path]
    command = subprocess.Popen(cmd_7z, stdout=LOG_PIPE, stderr=LOG_PIPE, cwd=ROOT_PATH)
    command.wait()
    rm(list_path)


def get_git_files(git_folder, version):
    """Using git.exe, parses the repository information to get a list of all
       files that belong in the repository.  Returns a list of files with paths
       relative to the Mopy directory, which can be used to ensure no non-repo
       files get included in the installers.  This function will also print a
       warning if there are non-committed changes.

       :return: a list of all paths that git tracks plus Mopy/Apps (
       preserves case)
    """
    # First, ensure GitPython will be able to call git.  On windows, this means
    # ensuring that the Git/bin directory is in the PATH variable.
    if not git:
        lprint("ERROR: Could not locate GitPython.")
        return False

    try:
        if sys.platform != "win32":
            lprint("ERROR: Only Windows supported!")
            return False

        # Windows, check all the PATH options first
        for path in os.environ["PATH"].split(os.pathsep):
            if os.path.isfile(os.path.join(path, u"git.exe")):
                # Found, no changes necessary
                break
        else:
            # Not found in PATH, try user supplied directory, as well as
            # common install paths
            pfiles = os.path.join(os.environ.get("ProgramFiles", ""), u"Git", u"bin")
            pfilesx64 = os.path.join(os.environ.get("ProgramW6432", ""), u"Git", u"bin")
            for path in (git_folder, pfiles, pfilesx64):
                if os.path.isfile(os.path.join(path, u"git.exe")):
                    # Found it, put the path into PATH
                    os.environ["PATH"] += os.pathsep + path
                    break
            else:
                # git still not found
                lprint(
                    "ERROR: Could not locate git. Try adding the path to "
                    "your git directory to the PATH environment variable."
                )
                return False

        # Git is working good, now use it
        repo = git.Repo(ROOT_PATH)
        if repo.is_dirty():
            lprint(
                "WARNING: Your wrye-bash repository is "
                "dirty (you have uncommitted changes)."
            )

        branch_name = repo.active_branch.name.lower()
        if (
            not branch_name.startswith(("rel-", "release-"))
            or version not in branch_name
        ):
            lprint(
                'WARNING: You are building off branch "{}", which does not '
                "appear to be a release branch for {}.".format(branch_name, version)
            )
        else:
            lprint('Building from branch "{}".'.format(branch_name))

        files = [
            unicode(os.path.normpath(x.path))
            for x in repo.tree().traverse()
            if x.path.lower().startswith(u"mopy")
            and os.path.isfile(os.path.join(ROOT_PATH, x.path))
        ]
        # Special case: we want the Apps folder to be included, even though
        # it's not in the repository
        files.append(os.path.join(u"Mopy", u"Apps"))
        return files
    except Exception:
        lprint("ERROR: An error occurred while attempting to interface with git.")
        traceback.print_exc(file=LOG_PIPE)
        return False


def get_non_repo_files(repo_files):
    """Return a list of all files in the Mopy folder that should not be
       included in the installer.  This list can be used to temporarily
       remove these files prior to running the NSIS scripts.
    """
    non_repo = []
    # Get a list of every directory and file actually present
    mopy_files = []
    mopy_dirs = []
    for root, dirs, files in _walkdir(u"Mopy"):
        mopy_files.extend((os.path.join(root, x) for x in files))
        mopy_dirs.extend((os.path.join(root, x) for x in dirs))
    mopy_files = (os.path.normpath(x) for x in mopy_files)
    # We can ignore .pyc and .pyo files, since the NSIS scripts skip those
    mopy_files = (
        x
        for x in mopy_files
        if os.path.splitext(x)[1].lower() not in (u".pyc", u".pyo")
    )
    # We can also ignore Wrye Bash.exe, for the same reason
    mopy_files = (
        x for x in mopy_files if os.path.basename(x).lower() != u"wrye bash.exe"
    )
    # Pick out every file that doesn't belong
    non_repo.extend((x for x in mopy_files if x not in set(repo_files)))

    mopy_dirs = (os.path.normpath(x) for x in mopy_dirs)
    # Pick out every directory that doesn't contain repo files
    non_repo_dirs = []
    for mopy_dir in mopy_dirs:
        for tracked_file in repo_files:
            if tracked_file.lower().startswith(mopy_dir.lower()):
                # It's good to keep
                break
        else:
            # It's not good to keep
            # Insert these at the beginning so they get handled first when
            # relocating
            non_repo_dirs.append(mopy_dir)
    if non_repo_dirs:
        non_repo_dirs.sort(key=unicode.lower)
        parent_dir = non_repo_dirs[0][5:]
        parent_dirs, parent_dir = [parent_dir], parent_dir.lower()
        for skip_dir in non_repo_dirs[1:]:
            new_parent = skip_dir[5:]
            if new_parent.lower().startswith(parent_dir):
                if new_parent[len(parent_dir)] == os.sep:
                    continue  # subdir keep only the top level dir
            parent_dirs.append(new_parent)
            parent_dir = new_parent.lower()
    else:
        parent_dirs = []
    # Lop off the "mopy/" part
    non_repo = (x[5:] for x in non_repo)
    tuple_parent_dirs = tuple(d.lower() + os.sep for d in parent_dirs)
    non_repo = [x for x in non_repo if not x.lower().startswith(tuple_parent_dirs)]
    # Insert parent_dirs at the beginning so they get handled first when relocating
    non_repo = parent_dirs + non_repo
    return non_repo


def move_non_repo_files(file_list, src_path, dst_path):
    """Moves any non-repository files/directories to /tmp"""
    for path in file_list:
        src = os.path.join(src_path, path)
        dst = os.path.join(dst_path, path)
        dirname = os.path.dirname(dst)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        mv(src, dst)


def make_repo_copy(file_list, tmpdir):
    """Create a temporary copy of the necessary repository files to
       have a clean repository for building."""
    root_to_nsis = os.path.join(u"scripts", u"build", u"installer")
    orig_nsis = os.path.join(ROOT_PATH, root_to_nsis)
    temp_nsis = os.path.join(tmpdir, root_to_nsis)
    shutil.copytree(orig_nsis, temp_nsis)
    file_list.append(u"Mopy\\Wrye Bash.exe")
    for path in file_list:
        src = os.path.join(ROOT_PATH, path)
        dst = os.path.join(tmpdir, path)
        cpy(src, dst)


@contextmanager
def clean_repo(non_repo_action, file_list):
    tmpdir = tempfile.mkdtemp()
    clean_root_path = ROOT_PATH
    non_repo_files = get_non_repo_files(file_list)
    try:
        if non_repo_files:
            lprint(
                " WARNING: Non-repository files are "
                "present in your source directory."
            )
            if non_repo_action == NonRepoAction.MOVE:
                lprint(
                    " " * 10 + "You have chosen to move the non-repository "
                               "files out of the source directory temporarily."
                )
                move_non_repo_files(non_repo_files, MOPY_PATH, tmpdir)
            elif non_repo_action == NonRepoAction.COPY:
                lprint(
                    " " * 10 + "You have chosen to make a temporary "
                               "clean copy of the repository to build with."
                )
                make_repo_copy(file_list, tmpdir)
                clean_root_path = tmpdir
            else:
                lprint(
                    " " * 10 + "You have chosen to not relocate them. "
                               "These files will be included in the installer!"
                )
                for fname in non_repo_files:
                    lprint(" ", fname)

        yield clean_root_path

    finally:
        if non_repo_files and non_repo_action == NonRepoAction.MOVE:
            move_non_repo_files(non_repo_files, tmpdir, MOPY_PATH)
        rm(tmpdir)


def get_nsis_root(cmd_arg):
    """Finds and returns the nsis root folder"""
    if cmd_arg is not None:
        return cmd_arg

    try:
        if _winreg:
            return _winreg.QueryValue(_winreg.HKEY_LOCAL_MACHINE, r"Software\NSIS")
    except WindowsError:
        pass

    local_nsis_path = os.path.join(SCRIPTS_PATH, "build", "nsis")
    if not os.path.isdir(local_nsis_path):
        local_build_path = os.path.dirname(local_nsis_path)
        nsis_url = (
            "https://sourceforge.net/projects/nsis/files/"
            "NSIS%203/{0}/nsis-{0}.zip/download".format(NSIS_VERSION)
        )
        dl_dir = tempfile.mkdtemp()
        nsis_zip = os.path.join(dl_dir, "nsis.zip")
        lprint(" Downloading NSIS {}...".format(NSIS_VERSION))
        build_utils.download_file(nsis_url, nsis_zip)
        with zipfile.ZipFile(nsis_zip) as fzip:
            fzip.extractall(local_build_path)
        os.remove(nsis_zip)
        os.rename(
            os.path.join(local_build_path, "nsis-{}".format(NSIS_VERSION)),
            local_nsis_path,
        )

        inetc_url = "https://nsis.sourceforge.io/mediawiki/images/c/c9/Inetc.zip"
        inetc_zip = os.path.join(dl_dir, "inetc.zip")
        lprint(" Downloading inetc plugin...")
        build_utils.download_file(inetc_url, inetc_zip)
        with zipfile.ZipFile(inetc_zip) as fzip:
            fzip.extract("Plugins/x86-unicode/INetC.dll", local_nsis_path)
        os.remove(inetc_zip)
    return local_nsis_path


def manual_pack(version, file_list):
    """Creates the standard python manual install version"""
    archive = os.path.join(
        DIST_PATH, u"Wrye Bash {} - Python Source.7z".format(version)
    )
    list_path = os.path.join(DIST_PATH, u"manual_list.txt")
    # We want every file for the manual version
    pack_7z(file_list, archive, list_path)


def standalone_build(version, file_version):
    """Builds the standalone exe"""
    # some paths we'll use
    wbsa = os.path.join(SCRIPTS_PATH, u"build", u"standalone")
    reshacker = os.path.join(wbsa, u"Reshacker.exe")
    upx = os.path.join(wbsa, u"upx.exe")
    icon = os.path.join(wbsa, u"bash.ico")
    manifest = os.path.join(wbsa, u"manifest.template")
    script = os.path.join(wbsa, u"setup.template")
    # for l10n
    msgfmt_src = os.path.join(real_sys_prefix(), u"Tools", u"i18n", u"msgfmt.py")
    pygettext_src = os.path.join(real_sys_prefix(), u"Tools", u"i18n", u"pygettext.py")
    msgfmt_dst = os.path.join(MOPY_PATH, u"bash", u"msgfmt.py")
    pygettext_dst = os.path.join(MOPY_PATH, u"bash", u"pygettext.py")
    # output folders/files
    exe = os.path.join(MOPY_PATH, u"Wrye Bash.exe")
    setup = os.path.join(MOPY_PATH, u"setup.py")
    dist = os.path.join(MOPY_PATH, u"dist")

    # check for build requirements
    if not py2exe:
        lprint(" Could not find python module 'py2exe', aborting standalone creation.")
        return False
    if not os.path.isfile(script):
        lprint(
            " Could not find '{}', aborting standalone creation.".format(
                os.path.basename(script)
            )
        )
        return False
    if not os.path.isfile(manifest):
        lprint(
            " Could not find '{}', aborting standalone creation.".format(
                os.path.basename(manifest)
            )
        )
        return False

    # Read in the manifest file
    with open(manifest, "r") as man:
        manifest = '"""\n' + man.read() + '\n"""'

    # Include the game package and subpackages (because py2exe wont
    # automatically detect these)
    packages = "'bash.game'"  # notice the double quotes

    try:
        # Ensure comtypes is generated, so the required files for wx.lib.iewin
        # will get pulled in by py2exe
        lprint(" Generating comtypes...")
        try:
            import wx
            import wx.lib.iewin
        except ImportError:
            lprint(" Could not import comtypes, aborting Standalone creation.")
            return False

        # Write the setup script
        with open(script, "r") as ins:
            script = ins.read()
        script = script % dict(
            version=version,
            file_version=file_version,
            manifest=manifest,
            upx=None,
            upx_compression="-9",
            packages=packages,
        )
        with open(setup, "w") as out:
            out.write(script)

        # Copy the l10n files over
        cpy(msgfmt_src, msgfmt_dst)
        cpy(pygettext_src, pygettext_dst)

        # Call the setup script
        lprint(" Calling py2exe...")
        command = subprocess.Popen(
            [sys.executable, setup, "py2exe", "-q"],
            shell=True,
            stdout=LOG_PIPE,
            stderr=LOG_PIPE,
            cwd=MOPY_PATH,
        )
        command.wait()

        # Copy the exe's to the Mopy folder
        mv(os.path.join(dist, u"Wrye Bash Launcher.exe"), exe)

        # Insert the icon
        lprint(" Adding icon...")
        subprocess.call(
            [
                reshacker,
                "-addoverwrite",
                exe + ",",
                exe + ",",
                icon + ",",
                "ICONGROUP,",
                "MAINICON,",
                "0",
            ],
            stdout=LOG_PIPE,
            stderr=LOG_PIPE,
        )

        # Also copy contents of ResHacker.log to the pipe file
        if LOG_PIPE is not None:
            try:
                with open(os.path.join(wbsa, u"Reshacker.log"), "r") as ins:
                    for line in ins:
                        print(line, file=LOG_PIPE)
            except Exception:
                # Don't care why it failed
                pass

        # Compress with UPX
        lprint(" Compressing with UPX...")
        subprocess.call([upx, "-9", exe], stdout=LOG_PIPE, stderr=LOG_PIPE)
    except:
        # On error, don't keep the built exe's
        rm(exe)
        raise
    finally:
        # Clean up left over files
        rm(msgfmt_dst)
        rm(pygettext_dst)
        rm(dist)
        rm(os.path.join(MOPY_PATH, u"build"))
        rm(os.path.join(wbsa, u"ResHacker.ini"))
        rm(os.path.join(wbsa, u"ResHacker.log"))
        rm(setup)
        rm(os.path.join(MOPY_PATH, u"Wrye Bash.upx"))

    return True


def standalone_pack(version, file_list):
    """Packages the standalone manual install version"""
    archive = os.path.join(
        DIST_PATH, u"Wrye Bash {} - Standalone Executable.7z".format(version)
    )
    # We do not want any python files with the standalone
    # version, and we need to include the built EXEs
    file_list = [
        x
        for x in file_list
        if os.path.splitext(x)[1].lower()
        not in (u".py", u".pyw", u".pyd", u".bat", u".template")
    ]
    file_list.append(u"Mopy\\Wrye Bash.exe")
    list_path = os.path.join(DIST_PATH, u"standalone_list.txt")
    pack_7z(file_list, archive, list_path)


def standalone_clean():
    """Removes standalone exe files that are not needed after packaging"""
    rm(os.path.join(MOPY_PATH, u"Wrye Bash.exe"))


def installer_build(nsis_path, non_repo_action, version, file_list, file_version):
    """Compiles the NSIS script, creating the installer version"""
    script_path = os.path.join(SCRIPTS_PATH, u"build", u"installer", u"main.nsi")
    if not os.path.exists(script_path):
        lprint(
            "ERROR: Could not find nsis script '{}', "
            "aborting installer creation.".format(script_path)
        )
        return

    try:
        nsis_root = get_nsis_root(nsis_path)
        nsis_path = os.path.join(nsis_root, "makensis.exe")
        inetc_path = os.path.join(nsis_root, "Plugins", "x86-unicode", "inetc.dll")
        if not os.path.isfile(nsis_path):
            lprint("ERROR: Could not find 'makensis.exe', aborting installer creation.")
            return
        if not os.path.isfile(inetc_path):
            lprint(
                "ERROR: Could not find NSIS Inetc "
                "plugin, aborting installer creation."
            )
            return

        with clean_repo(non_repo_action, file_list) as clean_root_path:
            root_to_mopy = os.path.relpath(MOPY_PATH, ROOT_PATH)
            root_to_script = os.path.relpath(script_path, ROOT_PATH)
            clean_mopy = os.path.join(clean_root_path, root_to_mopy)
            clean_script = os.path.join(clean_root_path, root_to_script)

            # Build the installer
            lprint(" Calling makensis.exe...")
            ret = subprocess.call(
                [
                    nsis_path,
                    "/NOCD",
                    "/DWB_NAME=Wrye Bash {}".format(version),
                    "/DWB_FILEVERSION={}".format(file_version),
                    # pass the correct mopy dir for the script
                    # to copy the right files in the installer
                    "/DWB_CLEAN_MOPY={}".format(clean_mopy),
                    clean_script,
                ],
                shell=True,
                stdout=LOG_PIPE,
                stderr=LOG_PIPE,
            )
            if ret != 0:
                lprint(
                    "ERROR: makensis exited with error code {}. Check the "
                    "output log for errors in the NSIS script.".format(ret)
                )
                return

    except KeyboardInterrupt:
        raise
    except Exception:
        lprint("ERROR: Error calling creating installer, aborting creation.")
        traceback.print_exc(file=LOG_PIPE)


def main():
    parser = argparse.ArgumentParser(
        description="""
        Packaging script for Wrye Bash, used to create the release modules.

        If you need more detailed help beyond what is listed below, use the
        --tutorial or -t switch.

        You must use at least Python 2.7.12.
        """
    )
    parser.add_argument(
        "-r",
        "--release",
        default=None,
        action="store",
        type=str,
        dest="version",
        help="Specifies the release number for Wrye Bash that you are packaging.",
    )
    wbsa_group = parser.add_mutually_exclusive_group()
    wbsa_group.add_argument(
        "-w",
        "--wbsa",
        action="store_true",
        default=False,
        dest="wbsa",
        help="Build and package the standalone version of Wrye Bash",
    )
    wbsa_group.add_argument(
        "-e",
        "--exe",
        action="store_true",
        default=False,
        dest="exe",
        help="""Create the WBSA exe.  This option does not package it into the
                standalone archive.""",
    )
    parser.add_argument(
        "-m",
        "--manual",
        action="store_true",
        default=False,
        dest="manual",
        help="Package the manual install Python version of Wrye Bash",
    )
    parser.add_argument(
        "-i",
        "--installer",
        action="store_true",
        default=False,
        dest="installer",
        help="Build the installer version of Wrye Bash.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        default=False,
        dest="all",
        help="""Build and package all version of Wrye Bash. This is equivalent
                to -w -i -m""",
    )
    parser.add_argument(
        "-n",
        "--nsis",
        default=None,
        dest="nsis",
        help="""Specify the path to the NSIS root directory.  Use this if the
                script cannot locate NSIS automatically.""",
    )
    parser.add_argument(
        "-g",
        "--git",
        default='',
        dest="git",
        help="""Specify the path to the git bin directory.  Use this if the
                script cannot locate git automatically.""",
    )
    parser.add_argument(
        "--non-repo",
        default=NonRepoAction.MOVE,
        action="store",
        choices=[NonRepoAction.MOVE, NonRepoAction.COPY, NonRepoAction.NONE],
        help="""If non-repository files are detected during packaging the
        *installer* version, the packaging script will deal with them in the
        following way: {MOVE} - move the non-repository files out of the
        source directory, then restore them after (recommended).  {COPY} -
        make a copy of the repository files into a temporary directory,
        then build from there (slower).  {NONE} - do nothing, causing those
        files to be included in the installer(HIGHLY DISCOURAGED).""".format(
            COPY=NonRepoAction.COPY, MOVE=NonRepoAction.MOVE, NONE=NonRepoAction.NONE
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        dest="verbose",
        help="""Verbose mode.  Directs output from 7z, py2exe, etc. to the
                console instead of the build log""",
    )
    parser.add_argument(
        "-l",
        "--view-logfile",
        default=False,
        action="store_true",
        dest="view_log",
        help="""If specified, and verbose mode is not enabled, opens the log
                file for viewing after completion of the packaging script.""",
    )

    # Parse command line, show help if invalid arguments are present
    try:
        args, extra = parser.parse_known_args()
    except SystemExit as e:
        if e.code:
            parser.print_help()
        return
    if len(extra) > 0:
        parser.print_help()
        return
    if sys.version_info[0:3] < (2, 7, 12):
        lprint("You must run at least Python 2.7.12 to use this script.")
        lprint("Your Python:", sys.version)
        return
    if not args.version:
        print("No release version specified, please enter it now.")
        args.version = raw_input(">")

    print(sys.version)

    # See if Mopy/Apps is already present, if it is, we won't
    # remove it at the end
    apps_present = os.path.isdir(APPS_PATH)

    global LOG_PIPE
    try:
        # fixme XXX: contextmanagers?
        # Setup output log
        if args.verbose:
            LOG_PIPE = None
        else:
            log_file = os.path.join(SCRIPTS_PATH, "build.log")
            LOG_PIPE = open(log_file, "w")

        # If no build arguments passed, it's the same as --all
        if (
            not args.wbsa and not args.manual and not args.installer and not args.exe
        ) or args.all:
            # Build everything
            args.wbsa = True
            args.manual = True
            args.installer = True

        # Create the Mopy/Apps folder if it's not present
        if apps_present:
            apps_temp = os.path.join(SCRIPTS_PATH, u"apps_temp")
            rm(apps_temp)
            os.makedirs(apps_temp)
            lprint("Moving your Apps folder to {}".format(apps_temp))
            shutil.move(APPS_PATH, apps_temp)
        os.makedirs(APPS_PATH)

        # Get repository files
        all_files = get_git_files(args.git, args.version)
        if all_files is False:
            lprint("GitPython is not set up correctly, aborting.")
            return

        # Add the LOOT API binaries to all_files
        loot_dll = os.path.join(u'Mopy', u'loot_api.dll')
        loot_pyd = os.path.join(u'Mopy', u'loot_api.pyd')
        if not os.path.exists(loot_dll) or not os.path.exists(loot_pyd):
            import build_loot_api
            build_loot_api.main()
        all_files.append(loot_dll)
        all_files.append(loot_pyd)

        file_version = get_version_info(args.version)

        # clean and create distributable directory
        if os.path.exists(DIST_PATH):
            shutil.rmtree(DIST_PATH)
        try:
            # Sometimes in Windows, if the dist directory was open in Windows
            # Explorer, this will cause an OSError: Accessed Denied, while
            # Explorer is renavigating as a result of the deletion.  So just
            # wait a second and try again.
            os.makedirs(DIST_PATH)
        except OSError:
            time.sleep(1)
            os.makedirs(DIST_PATH)

        if args.manual:
            lprint("Creating Python archive distributable...")
            manual_pack(args.version, all_files)

        exe_made = False

        if args.exe or args.wbsa or args.installer:
            lprint("Building standalone exe...")
            exe_made = standalone_build(args.version, file_version)

        if args.wbsa and exe_made:
            lprint("Creating standalone distributable...")
            standalone_pack(args.version, all_files)

        if args.installer:
            lprint("Creating installer distributable...")
            if exe_made:
                installer_build(
                    args.nsis, args.non_repo, args.version, all_files, file_version
                )
            else:
                lprint(" Standalone exe not found, aborting installer creation.")

    except KeyboardInterrupt:
        lprint("Build aborted by user.")
    except Exception as e:
        print("Error:", e)
        traceback.print_exc()
    finally:
        # Clean up Mopy/Apps if it was not present to begin with
        if apps_present:
            backapps = os.path.join(apps_temp, u"Apps")
            for lnk in glob.glob(backapps + os.sep + u"*"):
                shutil.copy(lnk, os.path.join(MOPY_PATH, u"Apps"))
            # shutil.move(backapps, mopy)
            rm(apps_temp)
        else:
            rm(APPS_PATH)
        if not args.exe:
            # Clean up the WBSA exe's if necessary
            standalone_clean()

        if not args.verbose:
            if LOG_PIPE:
                LOG_PIPE.close()
                if args.view_log:
                    os.startfile(log_file)


if __name__ == "__main__":
    main()
