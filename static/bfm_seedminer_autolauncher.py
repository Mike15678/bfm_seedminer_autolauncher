#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 3.4.1+ reference implementation for retrieving jobs from https://bruteforcemovable.com."""

# MIT License
#
# Copyright (c) 2018-2019 deadphoenix8091, figgyc, Michael "Mike15678" M., and Valentijn "noirscape" V.
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

# Mini Code Guidelines for contributors:
#   * Try to write in British English; this project has contributors who write in that variant of English
#   * All modules, functions, and classes should have a docstring which corresponds with
#     the reStructuredText (reST) format and PEP 257
#       - In addition, it's best to write a shortened variable/function parameter type right after the reST formatting
#         whenever possible (e.g. "str" for "string", "int" for "integer"); add a colon and then a space
#         after the type to begin your description
#   * It's ok to write informally for comments and print statements, but for docstrings, try to write formally
#   * Comments shouldn't have periods unless there are multiple sentences
#   * Conditionals should only omit its comparison...:
#       - when it would be "grammatically-correct" when its comparison is omitted (e.g. "if Windows:")
#           ^ You shouldn't omit its comparison when you're checking if a variable is empty, for example
#       - when it's comparing a function parameter that has a boolean value
#   * Make sure extra third-party modules are installed and offer to install them if not
#   * Most IO-related functions shouldn't print unless an exception occurs
#   * Use double quotes for strings; avoid single quotes
#   * Try to follow PEP8 whenever possible :)
#   There are probably more guidelines, but just try to follow the style of this script to the best of your ability

# The following "__future__" imports are used so that Python 2.6-2.7 can exit gracefully
from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import logging
import os
import os.path
import pickle
import platform
import re
import shutil
import subprocess
import sys
from errno import ENOENT
from glob import glob
from signal import signal, SIG_IGN, SIGINT
from time import sleep, time
from traceback import print_exc

if sys.version_info[0:2] >= (3, 0):
    # TODO: Maybe add configuration things in a future MINOR version for this script
    # import configparser
    import urllib.parse

if sys.version_info[0:2] >= (3, 1):
    import importlib

if sys.version_info[0:2] >= (3, 6):
    original_mnf_err = ModuleNotFoundError  # The "ModuleNotFoundError" exception was introduced in Python 3.6
else:
    original_mnf_err = None

# Be careful with this as it changes the behaviour!
ModuleNotFoundError = ModuleNotFoundError if sys.version_info[0:2] >= (3, 6) else ImportError

# Thanks, https://github.com/ihaveamac/fuse-3ds/blob/master/fuse3ds/_gui.py#L34 for the exception message parsing code
# This will be helpful for older Python versions which don't have the "ModuleNotFoundError" exception officially defined
try:
    # This is being done to see if pip actually exists for use with auto-installation of modules
    # We're not going to actually use any functions, classes, etc. from it
    import pip
except ModuleNotFoundError as imp_exc:
    if sys.version_info[0:2] >= (3, 6) or "no module named" in imp_exc.args[0].lower():
        pip = None
    else:
        raise
try:
    import psutil
except ModuleNotFoundError as imp_exc:
    if sys.version_info[0:2] >= (3, 6) or "no module named" in imp_exc.args[0].lower():
        psutil = None
    else:
        raise
try:
    import requests
    # If "requests" is successfully imported, we'll check if the "adpaters" submodule exists and subsequently
    # check if it has the "HTTPAdapter" class and then finally import it
    if hasattr(requests, "adapters") and hasattr(requests.adapters, "HTTPAdapter"):
        from requests.adapters import HTTPAdapter
    else:
        HTTPAdapter = None
except ModuleNotFoundError as imp_exc:
    if sys.version_info[0:2] >= (3, 6) or "no module named" in imp_exc.args[0].lower():
        requests = None
        HTTPAdapter = None
    else:
        raise

# Let's bring it back to how it originally was...
if sys.version_info[0:2] >= (3, 6):
    ModuleNotFoundError = original_mnf_err

# Metadata constants
__author__ = "deadphoenix8091, figgyc, Michael \"Mike15678\" M., and Valentijn \"noirscape\" V."
__copyright__ = "Copyright (c) 2018-2019 deadphoenix8091, figgyc, Michael \"Mike15678\" M., " \
                "and Valentijn \"noirscape\" V."
__credits__ = "deadphoenix8091, figgyc, Ian \"ihaveamac\" Burgwin, Iason \"jason0597\" Papadopoulos, " \
              "Michael \"Mike15678\" M., Valentijn \"noirscape\" V., and zoogie"
__license__ = "MIT"
__version__ = "3.0.0"  # Meant to adhere to Semantic Versioning (MAJOR.MINOR.PATCH)
__maintainer__ = "deadphoenix8091 & Michael \"Mike15678\" M."
__email__ = "N/A"
__status__ = "Development"

# Website constants
BASE_URL = "https://bruteforcemovable.com"  # URL used for interacting with jobs
UPDATE_BASE_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/raw/dev"  # URL used for script updates
ISSUE_TRACKER_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/issues"  # URL used for issue tracking

# OS constants
LINUX = sys.platform.startswith("linux")
MACOS = sys.platform == "darwin"
# Guess it's a good idea to support cygwin & msys as well; just make sure you use https://github.com/rprichard/winpty
# so stdout is properly flushed
# set() is used instead of set literals since Python 2.6 doesn't support them
WINDOWS = sys.platform in set(["win32", "cygwin", "msys"])

# File/Directory constants
MISC_DIR = "bfm_seedminer_autolauncher_misc/"  # The directory which contains miscellaneous files used with this script
LOG_DIR = MISC_DIR + "logs/"  # The directory which contains log files
BFCL = "bfcl"  # The GPU brute-forcer executable
if WINDOWS:
    BFCL += ".exe"
SEEDMINER_AUTOLAUNCHER = "bfm_seedminer_autolauncher.py"  # The name of this script
SEEDMINER_LAUNCHER = "seedminer_launcher3.py"  # The Python script which calls the GPU brute-forcer
BM = MISC_DIR + "benchmark"  # Stores the benchmark result
MN = MISC_DIR + "miner_name"  # Stores the miner's username
TM = MISC_DIR + "total_mined"  # Stores the number of movable.sed's mined
LOG_FILE = MISC_DIR + LOG_DIR + "bfm_seedminer_autolauncher"  # This string is appended later in the script

# Global variables
if requests is not None and hasattr(requests, "Session"):
    s = requests.Session()  # Initialise a Requests Session for keep-alive, cookie persistence, custom retries, etc.
else:
    s = None
currentid = None  # ID of the current job
seedminer_launcher_proc = None  # The seedminer_launcher3.py subprocess
active_job = False  # TODO: Probably get rid of this
exit_after_job = False  # Set by the miner whilst mining a job, if they choose to do so


class ResponseContentTooLargeError(IOError):
    """Define a custom exception which is used when a GET HTTP request's response content is too large."""
    pass


class RemoteJobError(IOError):
    """Define a custom exception which is used when an HTTP request related to jobs
    does not return a "successful" message in its response content."""
    pass


def print_issue_tracker_message():
    """Print a message instructing a user to report an issue to an issue tracker."""
    # TODO: Make this better
    print("Please report this by making an issue at:\n{}\nPlease also attach this script's "
          "log file (\"{}\") and be sure to state your OS and Python version".format(ISSUE_TRACKER_URL, LOG_FILE))


def exit_prompt():
    """Prompt a user to press the Enter key in preparation to exit.

    The caller is responsible for exiting the script using sys.exit().
    """
    input("Press the Enter key to exit...")


def print_traceback():
    """Convenience function for printing an exception."""
    print_exc()


def print_and_log(msg, log_func, exc_info=False, exit_after_exception=True):
    """Convenience function for printing and then logging (to file), both with a message and optionally a traceback.

    Custom logging should be setup before this function is called.

    :param msg: str: Message format string to print and log.
    :param log_func: func: The logging module function that will be called to log a message.
        Do not pass the parentheses of the function and do not pass the function as a string.
        If logging.exception is passed, then the value passed to the exc_info parameter will be changed to be True
        upon execution of this function.
    :param exc_info: bool: Defaults to False which doesn't print and log a traceback.
        Pass True if would like to print and log a traceback (which should only be done if called
        from an exception handler).
    :param exit_after_exception: bool: Defaults to True which calls exit_prompt() before exiting after an exception
        occurs. Set to False if you don't want this behaviour.
    """
    if log_func == logging.exception:
        exc_info = True
    print(msg)
    if exc_info:
        print_traceback()
    try:
        log_func(msg, exc_info=exc_info)
    except OSError:
        print("An error occurred while logging (to file)...")
        print_traceback()
        if exit_after_exception:
            print("Exiting...")
            exit_prompt()
            sys.exit(1)


def remote_kill_work_request(kill_value):
    """Utilise whatever is defined as BASE_URL and send a "/killWork" GET request with a query string.

    :param kill_value: str: The value for the corresponding "kill" key that is sent.
    :return: A None object only if currentid was assigned as a None object upon calling this function.
    """
    if currentid is None:
        return None
    if kill_value == "y":
        kill_string_to_print = "kill"
    elif kill_value == "n":
        kill_string_to_print = "requeue"
    else:
        # Fallback string
        kill_string_to_print = "interact with"
    try:
        with s.get(BASE_URL + "/killWork", params={"task": currentid, "kill": kill_value}, stream=True, timeout=5) as r:
            r.raise_for_status()
            size = 0
            max_size = 64  # Max GET request size
            expected_response_content = "okay"  # Message the GET requests expects
            for chunk in r.iter_content(chunk_size=32):
                size += len(chunk)
                if size > max_size:
                    raise ResponseContentTooLargeError("The request's response content is greater than {} bytes"
                                                       .format(max_size))
            if r.text != expected_response_content:
                raise RemoteJobError("Server's response content was \"{}\"; "
                                     "expected \"{}\"".format(r.text, expected_response_content))
    except (requests.exceptions.RequestException, ResponseContentTooLargeError, RemoteJobError):
        print_and_log("An error occurred while trying to remotely {} your job...".format(kill_string_to_print),
                      logging.exception)
        print_and_log("Exiting...", logging.info)
        exit_prompt()
        sys.exit(1)


def kill_pid_list(list_of_pids, timeout=3):
    """Kill a list of PIDs with psutil.

    :param list_of_pids: list: List of PIDs to kill.
    :param timeout: int: Time (in seconds) given for processes to terminate.
    """
    failed_kills = 0
    for p in list_of_pids:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            # No real issue if it doesn't exist
            try:
                logging.info("A process with PID: {} was not found or no longer exists".format(p), exc_info=True)
            except OSError:
                print("An error occurred while logging (to file)...\nIgnoring...")
        except psutil.AccessDenied:
            # In theory, this shouldn't really happen...
            failed_kills += 1
            list_of_pids.remove(p)  # Remove PID from list of children processes; we'll wait for processes afterwards
            print_and_log("Unable to kill a process with PID: {}".format(p), logging.critical, exc_info=True,
                          exit_after_exception=False)
    # Now we wait for processes to terminate; this excludes processes that raised AccessDenied (see above comment)
    gone, alive = psutil.wait_procs(list_of_pids, timeout=timeout)
    if alive:
        # What else can we do? This shouldn't really happen...
        for p in alive:
            failed_kills += 1
            print_and_log("Unable to kill a process with PID: {}".format(p), logging.critical, exc_info=True,
                          exit_after_exception=False)
    if failed_kills > 0:
        # Note we're not displaying an enter key prompt here
        # This is done to:
        #   1) not let stdout from unkilled processes overwrite the stdout from said prompt
        #   2) on Windows, when the script is run by double-clicking, cause the Python interpreter window to close
        #      which should kill any running processes started by this script
        print_and_log("Unable to kill {} process(es). Exiting...".format(failed_kills), logging.info,
                      exit_after_exception=False)
        sys.exit(1)


def kill_proc_tree(pid, include_parent=True, timeout=3):
    """Kill a process tree (including grandchildren) with psutil.

    :param pid: int: PID of the parent process.
    :param include_parent: bool: Defaults to True which includes the parent process as part
        of the processes to terminate. Set to False if you don't want this behaviour.
    :param timeout: int: Time (in seconds) given for processes to terminate.
    """
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)  # List of PIDs
    if include_parent:
        children.append(parent)
    kill_pid_list(children, timeout=timeout)


def suspend_proc_tree(pid, include_parent=True):
    """Suspend execution of a process tree (including grandchildren) with psutil.

    :param pid: int: PID of the parent process.
    :param include_parent: bool: Defaults to True which includes the parent process as part
        of the processes to suspend. Set to False if you don't want this behaviour.
    """
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)  # List of PIDs
    if include_parent:
        children.append(parent)
    failed_suspends = 0
    for p in children:
        try:
            p.suspend()
        except psutil.NoSuchProcess:
            # No real issue if it's doesn't exist
            try:
                logging.info("A process with PID: {} was not found or no longer exists".format(p), exc_info=True)
            except OSError:
                print("An error occurred while logging (to file)...\nIgnoring...")
        except psutil.AccessDenied:
            # In theory, this shouldn't really happen...
            failed_suspends += 1
            children.remove(p)  # Remove PID from list of children processes
            print_and_log("Unable to suspend a process with PID: {}".format(p), logging.critical, exc_info=True,
                          exit_after_exception=False)
    if failed_suspends > 0:
        # Note we're not displaying an enter key prompt here (see the kill_pid_list() function for info)
        print_and_log("Unable to suspend {} process(es). Killing (currently) non-problematic processes..."
                      .format(failed_suspends), logging.info, exit_after_exception=False)
        kill_pid_list(children, timeout=3)
        print_and_log("Exiting...", logging.info, exit_after_exception=False)
        sys.exit(1)


def resume_proc_tree(pid, include_parent=True):
    """Resume execution of a process tree (including grandchildren) with psutil.

    :param pid: int: PID of the parent process.
    :param include_parent: bool: Defaults to True which includes the parent process as part
        of the processes to resume. Set to False if you don't want this behaviour.
    """
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)  # List of PIDs
    if include_parent:
        children.append(parent)
    failed_resumes = 0  # Weird name, I guess
    for p in children:
        try:
            p.resume()
        except psutil.NoSuchProcess:
            # No real issue if it's doesn't exist
            try:
                logging.info("A process with PID: {} was not found or no longer exists".format(p), exc_info=True)
            except OSError:
                print("An error occurred while logging (to file)...\nIgnoring...")
        except psutil.AccessDenied:
            # In theory, this shouldn't really happen...
            failed_resumes += 1
            children.remove(p)  # Remove PID from list of children processes
            print_and_log("Unable to resume a process with PID: {}".format(p), logging.critical, exc_info=True,
                          exit_after_exception=False)
    if failed_resumes > 0:
        # Note we're not displaying an enter key prompt here (see the kill_pid_list() function for info)
        print_and_log("Unable to resume {} process(es). Killing (currently) non-problematic processes..."
                      .format(failed_resumes), logging.info, exit_after_exception=False)
        kill_pid_list(children, timeout=3)
        print_and_log("Exiting...", logging.info, exit_after_exception=False)
        sys.exit(1)


def exception_cleanup():
    """Cleanup the script on an exception in preparation to exit, if needed."""
    if currentid is not None and seedminer_launcher_proc is not None:
        # Attempting to kill the process tree is more important than trying to remotely requeue
        kill_proc_tree(seedminer_launcher_proc.pid)
        remote_kill_work_request("n")


def delete_file(path, not_exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize os.remove() for deleting files in a manner that is very dynamic.

    :param path: str: Name of the file you want to delete.
    :param not_exist_ok: bool: If path_not_exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the file you want to delete does not exist.
        Set to True if you don't want this behaviour.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the not_exist_ok parameter can control).
        Set to False if you don't want this behaviour.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        os.remove(path)
        return True
    except OSError as e:
        # ENOENT is "No such file or directory"
        if not not_exist_ok or (not_exist_ok and e.errno != ENOENT):
            print_and_log("An error occurred while deleting \"{}\"...".format(path), logging.exception,
                          exit_after_exception=False)
            if exit_on_os_err_traceback:
                exception_cleanup()
                exit_prompt()
                sys.exit(1)
        return False


def create_dir(name, mode=0o777, exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize os.makedirs() for creating directories in a manner that is very dynamic.

    :param name: str: Name of the directory you want to create.
    :param mode: oct: Mode of the directory you want to create; the default is 0o777.
    :param exist_ok: bool: If exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the directory you want to create already exists.
        Set to True if you don't want this behaviour.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the exist_ok parameter can control).
        Set to False if you don't want this behaviour.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        os.makedirs(name, mode, exist_ok)
        return True
    except OSError:
        print_and_log("An error occurred while creating \"{}\"...".format(name), logging.exception,
                      exit_after_exception=False)
        if exit_on_os_err_traceback:
            exception_cleanup()
            exit_prompt()
            sys.exit(1)
        return False


def move_file_or_dir(src, dst, not_exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize shutil.move() for moving files in a manner that is very dynamic.

    :param src: str: Origin of the file or directory you want to move.
    :param dst: str: Destination of the file or directory you want to move.
    :param not_exist_ok: bool: If not_exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the src file or directory you want to move does not exist.
        Set to True if you don't want this behaviour.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the not_exist_ok parameter can control).
        Set to False if you don't want this behaviour.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        shutil.move(src, dst)
        return True
    except OSError as e:
        if not not_exist_ok or (not_exist_ok and e.errno != ENOENT):
            print_and_log("An error occurred while moving \"{}\" to \"{}\"...".format(src, dst), logging.exception,
                          exit_after_exception=False)
            if exit_on_os_err_traceback:
                exception_cleanup()
                exit_prompt()
                sys.exit(1)
        return False


# Thanks, https://stackoverflow.com/a/16696317 for the base code
def download_file(url, local_filename, max_size=1048576, exit_on_traceback=True):
    """Download a file using requests.get().

    :param url: str: The URL you want to download a file from.
    :param local_filename: str: Name of the local file to save to.
    :param max_size: int: Maximum size (in bytes) allowed for the request's response content to be received. Defaults
        to 1048576 bytes (1 MiB).
    :param exit_on_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed.
        Set to False if you don't want this behaviour.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        with s.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            size = 0
            with open(local_filename, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024):
                    size += len(chunk)
                    if size > max_size:
                        raise ResponseContentTooLargeError("The request's response content is greater than {} bytes"
                                                           .format(max_size))
                    f.write(chunk)
            return True
    except (requests.exceptions.RequestException, ResponseContentTooLargeError):
        print_and_log("An error occurred while downloading \"{}\"...".format(local_filename), logging.exception,
                      exit_after_exception=False)
        print_and_log("Deleting {} if it exists, as it would most likely be a partial file...".format(local_filename),
                      logging.info, exit_after_exception=False)
        delete_file(local_filename, not_exist_ok=True, exit_on_os_err_traceback=False)
        if exit_on_traceback:
            exception_cleanup()
            exit_prompt()
            sys.exit(1)
        return False
    except OSError:
        print_and_log("An error occurred while writing to \"{}\"...".format(local_filename), logging.exception,
                      exit_after_exception=False)
        print_and_log("Deleting {} if it exists, as it would most likely be a partial file...".format(local_filename),
                      logging.info, exit_after_exception=False)
        delete_file(local_filename, not_exist_ok=True, exit_on_os_err_traceback=False)
        if exit_on_traceback:
            exception_cleanup()
            exit_prompt()
            sys.exit(1)
        return False


def relaunch_seedminer_autolauncher():
    """Restart this script."""
    logging.shutdown()
    try:
        subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
        sys.exit(0)
    except OSError:
        print_and_log("An error occurred while re-launching \"{}\"...".format(SEEDMINER_AUTOLAUNCHER),
                      logging.exception, exit_after_exception=False)
        exit_prompt()
        sys.exit(1)


def update_msed_data_db():
    """Update seedminer's msed_data db.

    There's no "checking for updates", only updating.
    """
    print_and_log("Updating seedminer's msed_data db...", logging.info, exit_after_exception=False)
    try:
        subprocess.call([sys.executable, SEEDMINER_LAUNCHER, "update-db"])
    except OSError:
        logging.exception("An error occurred while launching \"{}\" in order to "
                          "update seedminer's msed_data db...".format(SEEDMINER_LAUNCHER))
        exit_prompt()
        sys.exit(1)


def check_for_updates():
    """Check for updates to this script and to the msed db."""
    # TODO: Move this out of a function
    print("Updating seedminer's msed_data db...")
    try:
        with s.get(UPDATE_BASE_URL + "/static/bfm_seedminer_autolauncher_version", stream=True, timeout=5) as r:
            r.raise_for_status()
            size = 0
            max_size = 512
            for chunk in r.iter_content(chunk_size=256):
                size += len(chunk)
                if size > max_size:
                    raise ResponseContentTooLargeError("The request's response content is greater than {} bytes"
                                                       .format(max_size))
            if __version__ < r.text:
                print("Updating {}...".format(SEEDMINER_AUTOLAUNCHER))
                download_file(UPDATE_BASE_URL + "/static/bfm_seedminer_autolauncher.py",
                              SEEDMINER_AUTOLAUNCHER)
                relaunch_seedminer_autolauncher()
            else:
                print("No \"{}\" update available!".format(SEEDMINER_AUTOLAUNCHER))
                print("Updating seedminer's msed_data db...")
                update_msed_data_db()
    except (requests.exceptions.RequestException, ResponseContentTooLargeError):
        logging.exception("An error occurred while remotely reading \"bfm_seedminer_autolauncher_version\"")
        exception_cleanup()
        exit_prompt()
        sys.exit(1)


def signal_handler(sig, frame):
    """Handle SIGINT.

    sig and frame are to be passed by the calling function, but are not used.
    """
    signal(SIGINT, SIG_IGN)  # This makes Ctrl-C not send SIGINT
    global active_job, currentid, exit_after_job, seedminer_launcher_proc
    del sig, frame  # We don't need these parameters...
    if currentid is not None and seedminer_launcher_proc is not None and active_job is True:
        active_job = False
        suspend_proc_tree(seedminer_launcher_proc.pid)  # This stops stdout from seedminer_launcher3.py, bfCL, etc.
        while True:
            print("Job options menu:\n"
                  "1. Resume job\n"
                  "2. Update seedminer's msed_data db\n"
                  "3. Resume job and exit after it has been completed\n"
                  "4. Requeue job and exit")
            try:
                options_menu_input = input("Enter the number of a corresponding menu option: ")
            except EOFError:  # Only Windows seems to raise this
                print("")
                continue
            if options_menu_input.startswith("1"):
                print("Resuming job...")
                resume_proc_tree(seedminer_launcher_proc.pid)
                break
            elif options_menu_input.startswith("2"):
                update_msed_data_db()
                continue
            elif options_menu_input.startswith("3"):
                exit_after_job = True
                resume_proc_tree(seedminer_launcher_proc.pid)
            elif options_menu_input.startswith("4"):
                print("Requeuing job...")
                remote_kill_work_request("n")
                print("Killing {}'s process tree...".format(SEEDMINER_LAUNCHER))
                kill_proc_tree(seedminer_launcher_proc.pid)
                exit_prompt()
                sys.exit(0)
            else:
                print("Please enter in a valid choice!")
                continue
        signal(SIGINT, signal_handler)
    else:
        sys.exit(0)


def pip_install(modules_to_install):
    """Install module(s) using pip.

    :param modules_to_install: list: Modules that should be installed with pip passed as strings inside of a list.
    :return: int: Exit code of subprocess call. A zero exit code is a
        successful pip install while a non-zero exit code is a failed pip install.
    """
    return subprocess.call([sys.executable, "-m", "pip", "install", "--user", " ".join(modules_to_install)])


def pip_upgrade_install(modules_to_upgrade):
    """Upgrade already installed module(s) using pip.

    :param modules_to_upgrade: list: Modules that should be upgraded with pip passed as strings inside of a list.
    :return: int: Exit code of subprocess call. A zero exit code is a
        successful pip upgrade-install while a non-zero exit code is a failed pip upgrade-install.
    """
    return subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "--user",
                            " ".join(modules_to_upgrade)])


def file_check():
    """A check that determines if there are any missing files on your computer."""
    missing_files = None
    check_failures = 0
    if not os.path.isfile(SEEDMINER_LAUNCHER):
        check_failures += 1
        missing_files = "\"{}\"".format(SEEDMINER_LAUNCHER)
    if not os.path.isfile(BFCL):
        check_failures += 1
    # TODO: Implement this logic in the missing_modules_check() function
    if check_failures > 0:
        missing_files += " and " + BFCL
    else:
        missing_files = "\"{}\"".format(BFCL)
    if check_failures > 0:
        logging.warning("Unable to find \"{}\" in the current directory!".format(missing_files))
        if WINDOWS:
            print("Try disabling your antivirus (if you have one) and then\nredownload ", end="")
        else:
            print("Try redownloading ", end="")
        print("Seedminer from:\n"
              "https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n"
              "extract it, and then copy this script (\"{}\")\n"
              "inside of the new \"seedminer\" folder\n"
              "After that's done, feel free to rerun this script".format(SEEDMINER_AUTOLAUNCHER))
        logging.info("Exiting...")
        exit_prompt()
        sys.exit(1)


def move_files_if_needed():
    """Moves files in the current directory into a new directory if needed.

    New directories are made if they don't already exist.
    """
    move_file_or_dir("benchmark", BM, not_exist_ok=True)
    move_file_or_dir("minername", MN, not_exist_ok=True)
    move_file_or_dir("total_mined", TM, not_exist_ok=True)


def _main():
    """The main functionality of this script."""
    signal(SIGINT, signal_handler)  # Register custom signal handler for SIGINT
    global currentid, seedminer_launcher_proc, active_job, exit_after_job  # Our global variables

    # Retry 3 times on all http:// and https:// requests for a requests Session
    if requests is not None and s is not None and HTTPAdapter is not None:
        # Requests 1.2.1 introduced the max_retries parameter
        s.mount("http://", HTTPAdapter(max_retries=3))
        s.mount("https://", HTTPAdapter(max_retries=3))

    # Friendly Python version check
    if sys.version_info[0:3] < (3, 4, 1):
        try:
            # For Python 2
            input = raw_input
        except NameError:
            pass

        # Positional argument specifiers (i.e. "{<#>}") are needed in Python 2.6 and Python 3.0
        print("Python {0}.{1}.{2} is not supported! Please use Python 3.4.1 or later!".format(sys.version_info[0],
                                                                                              sys.version_info[1],
                                                                                              sys.version_info[2]))
        input("Press the Enter key to exit...")
        sys.exit(1)
    elif sys.executable is None or sys.executable == "":
        # Yes, it's possible that the Python interpreter is unable to retrieve the path to its executable
        print("Unable to determine the path to the Python interpreter automatically!")
        print("Please report this at:\n{}\n"
              "along with your OS type/version and Python version.".format(ISSUE_TRACKER_URL))
        exit_prompt()
        sys.exit(1)

    # Friendly OS/architecture check
    # Thanks, https://stackoverflow.com/a/12578715 for the base code for the architecture check
    os_and_arch_check_fail_count = 0
    if not (WINDOWS or MACOS or LINUX):
        os_and_arch_check_fail_count += 1
        print("You are using an unsupported Operating System or environment: {}\n"
              "This script only works on Windows, macOS, and Linux computers".format(sys.platform))
    if platform.machine().endswith("64") is False and platform.machine() != "":
        # Yes, it's possible that this check cannot determine your OS's architecture... which is fine since we're
        # only checking it to see if we can subprocess bfCL (which is 64-bit)
        os_and_arch_check_fail_count += 1
        print("You are using an unsupported computer architecture: {}-bit\n"
              "This script only works on supported 64-bit Operating Systems".format(platform.machine()[-2:]))
        print("If you believe to have received this message in mistake,\n"
              "feel free to make an issue here:\n"
              "{}".format(ISSUE_TRACKER_URL))
    if os_and_arch_check_fail_count > 0:
        exit_prompt()
        sys.exit(1)

    # TODO: Fix this
    # Friendly third-party module check
    if not hasattr(psutil, "__version__"):
        update_psutil = True
    if not hasattr(requests, "__version__"):
        update_requests = True
    modules_missing_count = 0
    modules_missing_string = ""
    modules_to_install = []
    if psutil is None:
        modules_missing_count += 1
        modules_missing_string += "\"psutil\""
        modules_to_install.append("psutil")
    if requests is None:
        modules_missing_count += 1
        if modules_missing_count > 1:
            modules_missing_string += " and \"requests\""
        else:
            modules_missing_string += "\"requests\""
        modules_to_install.append("requests")
    if modules_missing_count > 0:
        print("You are missing Python modules that are required for this script: {}".format(modules_missing_string))
        while True:
            auto_install_prompt = input("Would you like to automatically install "
                                        "missing Python modules using pip? [y/n]: ")
            if auto_install_prompt.lower().startswith("y"):
                print("Auto-installing {}!".format(modules_missing_string))
                break
            elif auto_install_prompt.lower().startswith("n"):
                print("In that case, please install {} manually through pip".format(modules_missing_string))
                exit_prompt()
                sys.exit(0)

    if pip is None:
        print("Unable to find pip!")
        if WINDOWS or MACOS:
            if WINDOWS:
                os_string = "Windows"
            elif MACOS:
                os_string = "macOS"
            print("This should not really happen on {} since Python 3.4+ includes pip in its binary releases "
                  "by default...\n"
                  "Try reinstalling the latest Python 3 version from https://www.python.org/ and then "
                  "rerun this script".format(os_string))
            exit_prompt()
            sys.exit(1)
        elif LINUX:
            print("In order to install pip, assuming you have curl installed "
                  "(if you don't, install curl through your package manager), "
                  "you can run:\ncurl https://bootstrap.pypa.io/get-pip.py -o get-pip.py\nand then run:\n"
                  "python3 get-pip.py\n"
                  "Then, rerun this script")
            exit_prompt()
            sys.exit(1)

    if LINUX or MACOS:
        if LINUX:
            c_compiler = "gcc"
            how_to_install_c_compiler = "through your package manager"
        elif MACOS:
            c_compiler = "clang"
            how_to_install_c_compiler = "by installing Xcode command-line tools" \
                                        "\nwhich you can generally install by entering in:\n" \
                                        "xcode-select --install\n"
        if (LINUX and shutil.which("gcc") is None) or (MACOS and shutil.which("clang") is None):
            print("Unable to find {0} in your path!\n"
                  "{0} is needed to install psutil; please install {0} {1} "
                  "and then rerun this script".format(c_compiler, how_to_install_c_compiler))
        exit_prompt()
        sys.exit(1)

    if len(modules_to_install) > 0:
        if pip_install(modules_to_install) == 0:
            print("Installed {} successfully!".format(modules_missing_string))
        else:
            print("Could not install {} successfully!\n"
                  "Please manually install them via pip and then feel free to rerun this script"
                  .format(modules_missing_string))
            print("Relaunching {}...".format(SEEDMINER_AUTOLAUNCHER))
            relaunch_seedminer_autolauncher()
    """
    if requests is None and psutil is None:
        if pip_install("psutil requests") == 0:
            print("Installed the \"requests\" and \"psutil\" modules automatically")
            print("Relaunching {}...".format(SEEDMINER_AUTOLAUNCHER))
            relaunch_seedminer_autolauncher()
        else:
            print(
                'The "requests" and "psutil" Python modules are not installed on this computer\n'
                'and could not be automatically installed!\n'
                'Please install them via pip and then feel free to rerun this script')
            modules_to_install = "requests psutil"
    elif requests is None:
        if pip_install("requests") == 0:
            print('Installed the "requests" module automatically')
            print("Relaunching {}...".format(SEEDMINER_AUTOLAUNCHER))
            sleep(1)
            relaunch_seedminer_autolauncher()
        else:
            print('The "requests" module is not installed on this computer and could not be automatically installed!\n'
                  'Please install it via pip and then feel free to rerun this script')
            modules_to_install = "requests"
    elif psutil is None:
        if pip_install("psutil") == 0:
            print('Installed the "psutil" module automatically')
            print("Relaunching {}...".format(SEEDMINER_AUTOLAUNCHER))
            sleep(1)
            relaunch_seedminer_autolauncher()
        else:
            print('The "psutil" module is not installed on this computer and could not be automatically installed!\n'
                  'Please install it via pip and then feel free to rerun this script')
            modules_to_install = "psutil"
    if requests is None or psutil is None:
        if WINDOWS:
            print("For Windows, this can generally be done by\n"
                  'entering in "py -3 -m pip install --user {}" (without the quotes)'.format(modules_to_install))
        else:
            print("For Linux/macOS, this can generally be done by\n"
                  'entering in "python3 -m pip install --user {}" (without the quotes)'.format(modules_to_install))
        enter_key_prompt()
        sys.exit(1)
"""



    file_check()
    create_dir(LOG_DIR, exist_ok=True)  # This creates MISC_DIR as well, if non-existent
    move_files_if_needed()

    log_file_number_increment = 0
    while os.path.isfile(LOG_FILE + "-{}.log".format(log_file_number_increment)):
        log_file_number_increment += 1

    appended_log_file = LOG_FILE + "-{}.log".format(log_file_number_increment)

    # Setup logging to file
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG,
                        filename=appended_log_file, filemode="w")

    """ Does not really work and would be problematic if a subprocess is running
    # Setup logging to console as well
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter("\n%(levelname)s: %(message)s")
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)
    """

    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] != "relaunch_proc"):
        check_for_updates()

    try:
        with open(SEEDMINER_LAUNCHER, "r") as f:
            if "Seedminer v2.1.5" not in f.readline():
                print("You must use this release of Seedminer:\n"
                      "https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n"
                      "if you want to use this script!\n"
                      "Please download and extract it, and copy this script inside of the\n"
                      "new & extracted \"seedminer\" folder\n"
                      "After that's done, feel free to rerun this script")
                exit_prompt()
                sys.exit(0)
    except OSError as e:
        if e.errno == ENOENT:
            print("Unable to find \"{}\"\n"
                  "Try downloading this release of Seedminer:\n"
                  "https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n"
                  "and extract it\n"
                  "Then, copy this script inside of the new & extracted \"seedminer\" folder\n"
                  "After that's done, feel free to rerun this script".format(SEEDMINER_LAUNCHER))
            exit_prompt()
            sys.exit(1)
        else:
            print("An error occurred while reading \"{}\"".format(SEEDMINER_LAUNCHER))
            print_traceback()
            logging.exception("Unable to read \"{}\"".format(SEEDMINER_LAUNCHER))
            exit_prompt()
            sys.exit(1)

    delete_file("movable.sed", not_exist_ok=True)

    try:
        with open(TM, "rb") as f:
            total_mined = pickle.load(f)
    except (OSError, pickle.PickleError) as e:
        if e.errno == ENOENT:
            total_mined = 0
        else:
            print("An error occurred while reading \"{}\"".format(TM))
            print_traceback()
            logging.exception("Unable to read \"{}\"".format(TM))
            exit_prompt()
            sys.exit(1)

    print("Total seeds mined previously: {}".format(total_mined))

    # TODO: Fix this
    if os.path.isfile(MN):
        with open(MN, "rb") as file:
            miner_username = pickle.load(file)
        if not re.match("^[a-zA-Z0-9_\\-|]*$", miner_username):
            print("Invalid character(s) detected in your {} file!".format(miner_username))
            delete_file(MN, not_exist_ok=True)
            print("Re-run this script to choose a new username")
            sys.exit(0)
        if len(miner_username) > 32:
            print("More than 32 characters detected in your {} file!".format(miner_username))
            delete_file(MN, not_exist_ok=True)
            print("Re-run this script to choose a new username")
            sys.exit(0)
    else:
        print("No username set, which name would you like to have on the leaderboard?\n"
              "Maximum length is 32-characters and allowed characters are: a-Z 0-9 - |")
        while True:
            miner_username = input("Enter your desired username: ")
            if len(miner_username) > 32 and not re.match("^[a-zA-Z0-9_\\-|]*$", miner_username):
                print("Both more than 32 characters and invalid characters were inputted!\n"
                      "Allowed characters are: a-Z 0-9 - |\n")
                continue
            if not re.match("^[a-zA-Z0-9_\\-|]*$", miner_username):
                print("Invalid characters inputted!\nAllowed characters are: a-Z 0-9 - |")
                continue
            elif len(miner_username) > 32:
                print("More than 32 characters inputted! Maximum length is 32 characters")
                continue
            else:
                break
        with open(MN, "wb") as file:
            pickle.dump(miner_username, file)

    print("Welcome {}, your mining effort is greatly appreciated!".format(miner_username))

    if os.path.isfile(BM):
        with open(BM, "rb") as file:
            benchmark_success = pickle.load(file)
        if benchmark_success == 1:
            print("Detected past benchmark! You're good to go!")
        elif benchmark_success == 0:
            print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
            print("If you want, you can rerun the benchmark by deleting the 'benchmark' file"
                  "and by rerunning the script")
            exit_prompt()
            sys.exit(0)
        else:
            print("Either something weird happened or you tried to mess with the benchmark result")
            print("Feel free to delete the 'benchmark' file\n"
                  "in your {} directory and then rerun\n"
                  "this script to start a new benchmark".format(MISC_DIR))
            exit_prompt()
            sys.exit(1)
    else:
        print("\nBenchmarking...")
        time_target = time() + 215
        download_file(BASE_URL + "/static/impossible_part1.sed",
                      "movable_part1.sed")
        process = subprocess.call(
            [sys.executable, "seedminer_launcher3.py", "gpu", "0", "5"])
        if process == 101:
            time_finish = time()
        else:
            print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
            print("Please try figuring this out before running this script again")
            exit_prompt()
            sys.exit(1)
        if time_finish > time_target:
            print("\nYour graphics card is too slow to help BruteforceMovable!")
            with open(BM, "wb") as file:
                pickle.dump(0, file)
            print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
                  " and then rerun this script to start a new benchmark")
            exit_prompt()
            sys.exit(0)
        else:
            print("\nYour graphics card is strong enough to help BruteforceMovable!\n")
            with open(BM, "wb") as file:
                pickle.dump(1, file)

    while True:
        try:
            try:
                r = s.get(BASE_URL + "/getWork")
                r.raise_for_status()
            except requests.exceptions.RequestException:
                print("Error. Waiting 30 seconds...")
                sleep(30)
                continue
            if r.text == "nothing":
                print("No work. Waiting 30 seconds...")
                sleep(30)
            else:
                currentid = r.text
                skipUploadBecauseJobBroke = False
                r2 = s.get(BASE_URL + "/claimWork?task=" + currentid)
                if r2.text == "error":
                    print("Device already claimed, trying again...")
                else:
                    print("\nDownloading part1 for device " + currentid)
                    download_file(BASE_URL + '/getPart1?task=' +
                                  currentid, 'movable_part1.sed')
                    print("Bruteforcing " + str(datetime.datetime.now()))
                    kwargs = {}
                    if WINDOWS:
                        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
                    else:
                        kwargs['start_new_session'] = True
                    process = psutil.Popen([sys.executable, "seedminer_launcher3.py", "gpu", "0", "80"], **kwargs)
                    timer = 0
                    while process.poll() is None:
                        # We need to poll for kill more often then we check server
                        # Otherwise, we would waste up to 30 secs after finish
                        active_job = True
                        timer += 1
                        sleep(1)
                        if timer % 30 == 0:
                            r3 = s.get(BASE_URL + '/check?task=' + currentid)
                            if r3.text != "ok":
                                currentid = ""
                                skipUploadBecauseJobBroke = True
                                active_job = False
                                print("\nJob cancelled or expired, killing...")
                                kill_proc_tree(process.pid)
                                print("Press Ctrl-C if you would like to exit")
                                sleep(5)
                                break
                    if process.returncode == 101 and skipUploadBecauseJobBroke is False:
                        skipUploadBecauseJobBroke = True
                        active_job = False
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=y")
                        currentid = ""
                        print("\nJob reached the specified max offset and was killed...")
                        print("Press Ctrl-C if you would like to exit")
                        on_ctrlc_kill_when_prompt = True
                        sleep(5)
                    elif os.path.isfile("movable.sed") and skipUploadBecauseJobBroke is False:
                        active_job = False
                        list_of_msed_data = glob('msed_data_*.bin')
                        latest_file = max(list_of_msed_data, key=os.path.getctime)
                        delete_file(latest_file, not_exist_ok=True)
                        failed_upload_attempts = 0
                        # Try three times and then you're out
                        while failed_upload_attempts < 3:
                            print("\nUploading...")
                            ur = s.post(BASE_URL + '/upload?task=' + currentid + "&minername="
                                        + urllib.parse.quote_plus(miner_username),
                                        files={'movable': open('movable.sed', "rb")})
                            print(ur.text)
                            if ur.text == "success":
                                currentid = None
                                print("Upload succeeded!")
                                total_mined += 1
                                print("Total seeds mined: {}".format(total_mined))
                                with open(TM, "wb") as file:
                                    pickle.dump(total_mined, file)
                                delete_file("movable.sed", not_exist_ok=True)
                                if exit_after_job is True:
                                    print("\nExiting by earlier request...")
                                    sleep(1)
                                    sys.exit(0)
                                print("Press Ctrl-C if you would like to exit")
                                sleep(5)
                                break
                            else:
                                failed_upload_attempts += 1
                                if failed_upload_attempts == 3:
                                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                                    currentid = None
                                    print("The script failed to upload files three times...")
                                    exit_prompt()
                                    sys.exit(1)
                                print("Upload failed! The script will try to\n"
                                      "upload completed files {} more time(s)"
                                      " before exiting".format(3 - failed_upload_attempts))
                                print("Waiting 10 seconds...")
                                print("Press Ctrl-C if you would like to exit")
                                sleep(10)
                    elif os.path.isfile("movable.sed") is False and skipUploadBecauseJobBroke is False:
                        remote_kill_work_request("n")
                        currentid = None
                        try:
                            os.remove(BM)
                        except OSError:
                            pass
                        print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly!\n"
                              "Please try figuring this out before running this script again")
                        exit_prompt()
                        sys.exit(1)
        except Exception:
            active_job = False

            print("\nAn unexpected error occurred!")
            print_traceback()
            print("Writing exception to '{}'...".format(appended_log_file))
            logging.exception("An unexpected error occurred!")
            exit_prompt()
            sys.exit(1)


if __name__ == '__main__':
    _main()
