#!/usr/bin/env python

import os
import sys

from subprocess import Popen


# This is just a hack how to generate modules and it's documentation
# after push to git in the readthedocs.


def make_modules():
    proc = Popen(['make', 'modules'], cwd='docs/')
    (_, err) = proc.communicate()
    return_code = proc.wait()

    if return_code or err:
        raise Exception('Failed to generate modules doc: %s' % err)


if "install" in sys.argv and os.environ.get('READTHEDOCS'):
    make_modules()
