#!/usr/bin/env python2

import logging
import math
import os
import sys
import urllib2

BUILD_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build.log")


# verbosity:
#  30 - quiet (warnings and above)
#  20 - regular (info and above)
#  10 - verbose (all messages)
def setup_log(logger, verbosity=20, logfile=BUILD_LOG):
    logger.setLevel(0)

    file_handler = logging.FileHandler(logfile, mode="w")
    file_formatter = logging.Formatter("[%(module)s]: %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_formatter = logging.Formatter("%(message)s")
    stdout_handler.setFormatter(stdout_formatter)
    stdout_handler.setLevel(verbosity)
    logger.addHandler(stdout_handler)


# sets up common parser options
def setup_common_parser(parser):
    parser.add_argument(
        "-l", "--logfile", default=BUILD_LOG, help="Where to store the build log."
    )
    verbose_group = parser.add_mutually_exclusive_group()
    verbose_group.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        const=10,
        dest="verbosity",
        help="Print all output to console.",
    )
    verbose_group.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=30,
        dest="verbosity",
        help="Do not print any output to console.",
    )
    parser.set_defaults(verbosity=20)


def convert_bytes(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "{}{}".format(s, size_name[i])


def download_file(url, fpath):
    file_name = os.path.basename(fpath)
    response = urllib2.urlopen(url)
    meta = response.info()
    file_size = int(meta.getheaders("Content-Length")[0])
    converted_size = convert_bytes(file_size)

    file_size_dl = 0
    block_sz = 8192
    with open(fpath, "wb") as dl_file:
        while True:
            buff = response.read(block_sz)
            if not buff:
                break

            file_size_dl += len(buff)
            dl_file.write(buff)
            percentage = file_size_dl * 100.0 / file_size
            status = "{0:>20}  -----  [{3:6.2f}%] {1:>10}/{2}".format(
                file_name, convert_bytes(file_size_dl), converted_size, percentage
            )
            status = status + chr(8) * (len(status) + 1)
            print status,
    print
