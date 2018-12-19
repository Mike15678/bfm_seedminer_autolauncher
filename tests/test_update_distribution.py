# -*- coding: utf-8 -*-
"""Test to make sure that the remote repository is distributing updates correctly."""

# MIT License
#
# Copyright (c) 2018 figgyc, Valentijn "noirscape" V., deadphoenix8091, Michael "Mike15678" M.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from static import bfm_seedminer_autolauncher


def remote_version_string():
    """Read and return the contents of the "bfm_seedminer_autolauncher_version" file.

    :return: str: Version string.
    """
    with open("static/bfm_seedminer_autolauncher_version", "r") as f:
        return f.read()


def first_line_of_changelog():
    """Read and return the first line of "changelog.txt".

    :return: str: First line of the changelog.
    """
    with open("static/changelog.txt", "r") as f:
        return f.readline()


def test_client_and_remote_version_strings():
    """Test to make sure that both "bfm_seedminer_autolauncher.py" and "bfm_seedminer_autolauncher_version" have
    the same version strings."""
    assert bfm_seedminer_autolauncher.__version__ == remote_version_string()


def test_changelog_contains_correct_version_string():
    """Test to make sure that the first line of "changelog.txt" contains the version string
    from the "bfm_seedminer_autolauncher_version" file."""
    assert remote_version_string() in first_line_of_changelog()
