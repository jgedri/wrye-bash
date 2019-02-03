#!/usr/bin/env python2

import math
import os
import platform
import urllib2


def is_os_64bit():
    return platform.machine().endswith("64")


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
