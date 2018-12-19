#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python 3.4.1+ script for use for retrieving jobs from https://bruteforcemovable.com. Use responsibly."""

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

# The following "__future__" imports are used so that Python 2.6-2.7 can exit gracefully
from __future__ import absolute_import, division, print_function, unicode_literals

from errno import ENOENT
from glob import glob
from signal import signal, SIG_IGN, SIGINT
from time import sleep, time
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

if sys.version_info[0:3] >= (3, 0, 0):
    # TODO: Maybe add configuration things in a future MINOR version for this script
    # import configparser
    import urllib.parse

if sys.version_info[0:3] >= (3, 1, 0):
    import importlib

if sys.version_info[0:3] >= (3, 4, 0):
    # Required third party modules are to be found and then subsequently imported here
    import importlib.util  # Thanks, https://stackoverflow.com/a/14050282
    # This is technically TOCTTOU, but at least an ImportError exception would be raised
    # if a module tries to be imported, but does not exist
    # TODO: Evaluate all the potential risks of doing this
    requests_spec = importlib.util.find_spec("requests")
    if requests_spec is not None:
        import requests
    else:
        requests = None
    psutil_spec = importlib.util.find_spec("psutil")
    if psutil_spec is not None:
        import psutil
    else:
        psutil = None
else:
    requests = None
    psutil = None

# Script constants
__version__ = "3.0.0"  # Meant to adhere to Semantic Versioning (MAJOR.MINOR.PATCH)
# -----

# Website constants
BASE_URL = "https://bruteforcemovable.com"
UPDATE_BASE_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/raw/dev"
ISSUE_TRACKER_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/issues"
# -----

# OS constants
# set() is used instead of set literals since Python 2.6 doesn't support them
WINDOWS = sys.platform in set(["win32", "msys", "cygwin"])
MACOS = sys.platform == "darwin"
LINUX = sys.platform.startswith("linux")
SUPPORTED_OS = True if (WINDOWS or MACOS or LINUX) else False
# -----

# File/Directory constants
MISC_DIR = "bfm_seedminer_autolauncher_misc/"
LOG_DIR = MISC_DIR + "logs/"
BFCL = "bfcl"
if WINDOWS:
    BFCL += ".exe"
SEEDMINER_LAUNCHER = "seedminer_launcher3.py"
SEEDMINER_AUTOLAUNCHER = "bfm_seedminer_autolauncher.py"
BM = MISC_DIR + "benchmark"
MN = MISC_DIR + "miner_name"  # TODO: Convert pickled "miner name" files to a bfm_config.ini file to allow easy editing
TM = MISC_DIR + "total_mined"
LOG_PREFIX = MISC_DIR + LOG_DIR + "bfm_seedminer_autolauncher"  # This string is appended later in the script
# -----

# Global variables
if requests is not None:
    s = requests.Session()  # Initialize a Requests Session for potential performance benefits
currentid = None
seedminer_launcher_proc = None
active_job = False
exit_after_job = False
# -----


class ResponseContentTooLargeError(Exception):
    """Define a custom exception which is used when a GET HTTP request's response content is too large."""
    pass


class RemoteJobError(Exception):
    """Define a custom exception which is used when an HTTP request related to jobs
    does not return a "successful" message in its response content."""
    pass


def enter_key_prompt():
    """Prompt a user to press the Enter key.

    The caller is responsible for exiting the script using sys.exit().
    """
    input("Press the Enter key to exit...")


def log_critical_exception(msg):
    """Convenience function for logging an exception at level CRITICAL.

    For logging an exception at level ERROR, use
    logging.exception() instead (including its required "msg" parameter).

    :param msg: Message format string to log.
    """
    logging.critical(msg, exc_info=True)


def remote_kill_work_request(kill_value):
    """Utilize whatever is defined as BASE_URL and send a "/killWork" GET request with a query string.

    The script exits if it could not make a successful GET request after three attempts.

    :param kill_value: str: The value for the corresponding "kill" key that is sent.
    :return: A None object only if currentid was assigned as a None object upon calling this function.
    """
    if currentid is None:
        return
    if kill_value == "y":
        kill_string_to_print = "kill"
    elif kill_value == "n":
        kill_string_to_print = "requeue"
    else:
        kill_string_to_print = "interact with"
    remaining_tries = 3
    for i in range(0, 3, 1):
        try:
            r = s.get(BASE_URL + "/killWork", params={"task": currentid, "kill": kill_value}, timeout=5)
            r.raise_for_status()
            if r.text != "okay":
                raise RemoteJobError("Server's response content was \"{}\"".format(r.text))
            break
        except (requests.exceptions.RequestException, RemoteJobError):
            remaining_tries -= 1
            logging.exception("An error occurred while trying to remotely {} your job".format(kill_string_to_print))
            if i == 2:
                logging.info("The script failed to remotely {} your job 3 times. "
                             "Exiting...".format(kill_string_to_print))
                enter_key_prompt()
                sys.exit(1)
            print("The script will try to remotely {} your job {} more "
                  "time(s) before exiting!".format(kill_string_to_print, remaining_tries))
            print("Waiting 10 seconds...")
            sleep(10)
            continue


def kill_proc_tree(pid, include_parent=True, timeout=3):
    """Kill a process tree (including grandchildren) with psutil."""
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    access_denied_exception_occurred = False
    for p in children:
        try:
            p.kill()
        except psutil.NoSuchProcess:
            logging.info("A process with PID: {} was not found or no longer exists".format(p))
        except psutil.AccessDenied:
            access_denied_exception_occurred = True
            log_critical_exception("Unable to kill a process with PID: {}".format(p))
    if access_denied_exception_occurred:
        logging.info("Failed to kill some processes. Exiting...")
        # enter_key_prompt()
        sys.exit(1)
    gone, alive = psutil.wait_procs(children, timeout=timeout)
    if alive:
        # What else can we do? This shouldn't really happen...
        for p in alive:
            logging.critical("Unable to kill a process with PID: {}".format(p))
        logging.info("Failed to kill some processes. Exiting...")
        # enter_key_prompt()
        sys.exit(1)


def suspend_proc_tree(pid, include_parent=True):
    """Suspend execution of a process tree (including grandchildren) with psutil."""
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    access_denied_exception_occurred = False
    for p in children:
        try:
            p.suspend()
        except psutil.NoSuchProcess:
            logging.info("A process with PID: {} was not found or no longer exists".format(p))
        except psutil.AccessDenied:
            access_denied_exception_occurred = True
            log_critical_exception("Unable to suspend a process with PID: {}".format(p))
    if access_denied_exception_occurred:
        logging.info("Failed to suspend some processes. Exiting...")
        # enter_key_prompt()
        sys.exit(1)


def resume_proc_tree(pid, include_parent=True):
    """Resume execution of a process tree (including grandchildren) with psutil."""
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    if include_parent:
        children.append(parent)
    access_denied_exception_occurred = False
    for p in children:
        try:
            p.resume()
        except psutil.NoSuchProcess:
            logging.info("A process with PID: {} was not found or no longer exists".format(p))
        except psutil.AccessDenied:
            access_denied_exception_occurred = True
            log_critical_exception("Unable to resume a process with PID: {}".format(p))
    if access_denied_exception_occurred:
        logging.info("Failed to resume some processes. Exiting...")
        # enter_key_prompt()
        sys.exit(1)


def exception_cleanup():
    """Cleanup the script on an exception in preparation to exit."""
    logging.shutdown()
    if currentid is not None and seedminer_launcher_proc is not None:
        # Attempting to kill the process tree is more important than trying to remotely requeue
        kill_proc_tree(seedminer_launcher_proc.pid)
        remote_kill_work_request("n")


def delete_file(path, path_not_exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize os.remove() for deleting files in a manner that is very dynamic.

    :param path: str: Name of the file you want to delete.
    :param path_not_exist_ok: bool: If path_not_exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the file you want to delete does not exist.
        Set to True if you don't want this behavior.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the path_not_exist_ok parameter can control).
        Set to False if you don't want this behavior.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        os.remove(path)
        return True
    except OSError as e:
        # ENOENT is "No such file or directory"
        if not path_not_exist_ok or (path_not_exist_ok and e.errno != ENOENT):
            logging.exception("An error occurred while deleting \"{}\"".format(path))
            if exit_on_os_err_traceback:
                exception_cleanup()
                enter_key_prompt()
                sys.exit(1)
        return False


def create_dir(name, mode=0o777, exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize os.makedirs() for creating directories in a manner that is very dynamic.

    :param name: str: Name of the directory you want to create.
    :param mode: octal: Mode of the directory you want to create; the default is 0o777.
    :param exist_ok: bool: If exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the directory you want to create already exists.
        Set to True if you don't want this behavior.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the exist_ok parameter can control).
        Set to False if you don't want this behavior.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        os.makedirs(name, mode, exist_ok)
        return True
    except OSError:
        logging.exception("An error occurred while creating \"{}\"".format(name))
        if exit_on_os_err_traceback:
            exception_cleanup()
            enter_key_prompt()
            sys.exit(1)
        return False


def move_file_or_dir(src, dst, src_not_exist_ok=False, exit_on_os_err_traceback=True):
    """Utilize shutil.move() for moving files in a manner that is very dynamic.

    :param src: str: Origin of the file or directory you want to move.
    :param dst: str: Destination of the file or directory you want to move.
    :param src_not_exist_ok: bool: If src_not_exist_ok is False (the default), a traceback for an OSError exception
        is printed regardless if the src file or directory you want to move does not exist.
        Set to True if you don't want this behavior.
    :param exit_on_os_err_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed (which the src_not_exist_ok parameter can control).
        Set to False if you don't want this behavior.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        shutil.move(src, dst)
        return True
    except OSError as e:
        if not src_not_exist_ok or (src_not_exist_ok and e.errno != ENOENT):
            logging.exception("An error occurred while moving \"{}\" to \"{}\"".format(src, dst))
            if exit_on_os_err_traceback:
                exception_cleanup()
                enter_key_prompt()
                sys.exit(1)
        return False


def download_file(url, local_filename, exit_on_traceback=True):  # https://stackoverflow.com/a/16696317 thx
    """Download a file using requests.get().

    :param url: str: The URL you want to download a file from.
    :param local_filename: str: Name of the local file to save to.
    :param exit_on_traceback: bool: Defaults to True which prompts and then exits the script only
        if a traceback for an OSError exception was printed.
        Set to False if you don't want this behavior.
    :return: bool: True if operation was successful, False if not.
    """
    try:
        with requests.get(url, stream=True, timeout=5) as r:
            r.raise_for_status()
            try:
                with open(local_filename, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024):
                        f.write(chunk)
                return True
            except OSError:
                logging.exception("An error occurred while writing to \"{}\"".format(local_filename))
                if exit_on_traceback:
                    exception_cleanup()
                    enter_key_prompt()
                    sys.exit(1)
                return False
    except requests.exceptions.RequestException:
        logging.exception("An error occurred while downloading \"{}\"".format(local_filename))
        if exit_on_traceback:
            exception_cleanup()
            enter_key_prompt()
            sys.exit(1)
        return False


def relaunch_seedminer_autolauncher():
    """Restart this script."""
    logging.shutdown()
    try:
        subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
        sys.exit(0)
    except OSError:
        print("\nAn error occurred while re-launching \"{}\"".format(SEEDMINER_AUTOLAUNCHER))
        enter_key_prompt()
        sys.exit(1)


def update_msed_data_db():
    """Update seedminer's msed_data db.

    There's no "checking", only updating.
    """
    print("Updating seedminer's msed_data db...")
    try:
        subprocess.call([sys.executable, SEEDMINER_LAUNCHER, "update-db"])
    except OSError:
        logging.exception("An error occurred while launching \"{}\" in order to "
                          "update seedminer's msed_data db".format(SEEDMINER_LAUNCHER))
        enter_key_prompt()
        sys.exit(1)


def check_for_updates():
    """Check for updates to this script and to the msed db."""
    print("Checking for updates...")
    try:
        with s.get(UPDATE_BASE_URL + "/static/bfm_seedminer_autolauncher_version", stream=True, timeout=5) as r:
            r.raise_for_status()
            size = 0
            max_size = 1024
            for chunk in r.iter_content(chunk_size=512):
                size += len(chunk)
                if size > max_size:
                    raise ResponseContentTooLargeError("The response content is greater than {} bytes".format(max_size))
            if __version__ < r.text:
                print("Updating {}...".format(SEEDMINER_AUTOLAUNCHER))
                download_file(UPDATE_BASE_URL + "/static/bfm_seedminer_autolauncher.py",
                              SEEDMINER_AUTOLAUNCHER)
                relaunch_seedminer_autolauncher()
            else:
                print("No \"{}\" update available!".format(SEEDMINER_AUTOLAUNCHER))
                update_msed_data_db()
    except (requests.exceptions.RequestException, ResponseContentTooLargeError):
        logging.exception("An error occurred while remotely reading \"bfm_seedminer_autolauncher_version\"")
        exception_cleanup()
        enter_key_prompt()
        sys.exit(1)


def signal_handler(sig, frame):
    """Handle SIGINT.

    sig and frame are to be passed by the calling function, but are not used.
    """
    signal(SIGINT, SIG_IGN)  # This makes Ctrl-C not send SIGINT
    global active_job, currentid, exit_after_job, seedminer_launcher_proc
    del sig, frame  # We don't need these parameters...
    if currentid is not None and active_job is True:
        active_job = False
        suspend_proc_tree(seedminer_launcher_proc.pid)  # This stops stdout from seedminer_launcher3.py, bfCL, etc.
        while True:
            try:
                print("Job options menu:\n"
                      "1. Resume job\n"
                      "2. Update seedminer's msed_data db\n"
                      "3. Resume job and exit after it has finished\n"
                      "4. Requeue job and exit")
                options_menu_input = input("Enter the number of a corresponding menu option: ")
            except EOFError:
                # Pressing Ctrl-C while SIGINT is ignored causes an EOFError on input()
                print("\nPlease enter in a valid choice!")
                continue
            if options_menu_input.startswith('1'):
                print("Continuing job...")
                resume_proc_tree(seedminer_launcher_proc.pid)
                break
            elif options_menu_input.startswith('2'):
                print("Updating your msed_data db...")
                update_msed_data_db()
                continue
            elif options_menu_input.startswith('3'):
                resume_proc_tree(seedminer_launcher_proc.pid)

            elif options_menu_input.startswith('4'):
                print("Requeuing job...")
                remote_kill_work_request("n")
                print("Killing {}'s process tree...".format(SEEDMINER_LAUNCHER))
                kill_proc_tree(seedminer_launcher_proc.pid)
                enter_key_prompt()
                sys.exit(0)
            else:
                print("Please enter in a valid choice!")
                continue
    else:
        sys.exit(0)


def python_check():
    """Check that the Python version being used is supported.

    If the Python version is supported, then a check will make sure that "sys.executable" points
    to a valid Python interpreter path.
    """
    supported_python_version = "3.4.1"
    if sys.version_info[0:3] < (3, 4, 1):
        # Positional argument specifiers are needed in Python 2.6 and Python 3.0
        print("Python {0}.{1}.{2} is not supported! Please use Python {3} or later!".format(sys.version_info[0],
                                                                                            sys.version_info[1],
                                                                                            sys.version_info[2],
                                                                                            supported_python_version))
        input("Press the Enter key to exit...")
        enter_key_prompt()
        sys.exit(1)
    elif sys.executable is None or sys.executable == '':
        # Yes, it's possible that Python is unable to retrieve the path to its executable
        print("Unable to determine the path to the Python interpreter automatically!")
        print("Please report this at:\n{}\n"
              "along with your OS type and Python version.".format(ISSUE_TRACKER_URL))
        enter_key_prompt()
        sys.exit(1)


def arch_and_os_check():
    """Check that the computer being used is 64-bit its OS is supported."""
    computer_architecture = platform.machine()
    supported_architecture = computer_architecture.endswith('64')
    # Yes, it's possible that it cannot determine your processor's architecture
    if not supported_architecture and computer_architecture != '':
        print("You are using an unsupported computer architecture: {}-bit\n"
              "This script only works on 64-bit (Windows, macOS, and Linux) computers.".format(platform.machine()[-2:]))
        print("If you believe to have received this message in mistake,\n"
              "feel free to make a GitHub issue here:\n"
              "{}".format(ISSUE_TRACKER_URL))
        enter_key_prompt()
        sys.exit(1)
    if not SUPPORTED_OS:
        print("You are using an unsupported Operating System or environment:\n{}\n"
              "This script only works on (64-bit) Windows, macOS, "
              "and Linux computers.".format(sys.platform))
        enter_key_prompt()
        sys.exit(1)


def missing_module_check():
    """A check that determines if the "requests" and "psutil" modules are installed on your computer
    and provides instructions on how to install them if not."""
    modules_to_install = None
    if not requests_found and not psutil_found:
        if pip_install("requests psutil") == 0:
            print('Installed the "requests" and "psutil" modules automatically')
            print("Relaunching {}...".format(SEEDMINER_AUTOLAUNCHER))
            sleep(1)
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
                  'entering in "py -3 -m pip install --user {}" (without the quote)'.format(modules_to_install))
        else:
            print("For Linux/macOS, this can generally be done by\n"
                  'entering in "python3 -m pip install --user {}" (without the quotes)'.format(modules_to_install))
        enter_key_prompt()
        sys.exit(1)


def pip_install(modules_to_install):
    """Installs module(s) using pip.

    :param modules_to_install: str: Modules that should be installed with pip. If installing
        multiple modules, each module in the str should be separated with a space.
        For example, to install psutil and requests, the string that should
        be passed is "requests psutil".
    :return: int: Exit code of subprocess call. A zero exit code is a
        successful pip install while a non-zero exit code is a failed pip install.
    """
    return subprocess.call([sys.executable, "-m", "pip", "install", "--user", modules_to_install])


def file_check():
    """A check that determines if there are any missing files on your computer."""
    missing_files = None
    check_failures = 0
    if not os.path.isfile(SEEDMINER_LAUNCHER):
        check_failures += 1
        missing_files = SEEDMINER_LAUNCHER
    if not os.path.isfile(BFCL):
        check_failures += 1
        # TODO: Implement this logic in the missing_modules_check() function
        if check_failures > 0:
            missing_files += ' and ' + BFCL
        else:
            missing_files = BFCL
    if check_failures > 0:
        print('Unable to find "{}" in the current directory.'.format(missing_files))
        print('Try disabling your antivirus (if you have one) and then\n'
              'redownload Seedminer:\n'
              'https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n'
              'and extract it,\n'
              'and then copy this script ("{}")\n'
              'inside of the new "seedminer" folder\n'
              "After that's done, feel free to rerun this script".format(SEEDMINER_AUTOLAUNCHER))
        enter_key_prompt()
        sys.exit(1)


def make_bfm_dir_if_needed():
    """Makes a bfm directory if it doesn't already exist."""
    try:
        os.makedirs(MISC_DIR, exist_ok=True)
    except OSError:
        print('\nError while creating a "{}" directory!'.format(MISC_DIR))
        raise


def make_log_dir_if_needed():
    """Makes a log directory if it doesn't already exist."""
    try:
        os.makedirs(LOG_DIR)
    except OSError:
        print('\nError while creating a "{}" directory!'.format(LOG_DIR))
        raise


def move_files_if_needed():
    """Moves files in the current directory into a new directory if needed.

    New directories are made if they don't already exist."""
    move_file_or_dir("benchmark", BM, src_not_exist_ok=True)
    move_file_or_dir("minername", MN, src_not_exist_ok=True)
    move_file_or_dir("total_mined", TM, src_not_exist_ok=True)


def delete_log_files_prompt():
    """A prompt that attempts to delete unnecessary log files.

    This prompt only appears if there are tens of log files.
    """
    # TODO: Fix this
    if log_file_number_increment % 10 == 0:
        print('There are currently {} log files inside of your "{}" directory'.format(
            log_file_number_increment, LOG_DIR))
        while True:
            log_file_input = input("Would you like to delete all except the most recent log file? [y/n]: ")
            if log_file_input.lower().startswith('y'):
                for log_file in glob(LOG_PREFIX + '-*.log'):
                    if delete_file(log_file, delete_ok=True, do_exit=False) is False:
                        while True:
                            exit_input = input("Would you like to exit? [y/n]: ")
                            if exit_input.lower().startswith('y'):
                                print("Exiting...")
                                sleep(1)
                                sys.exit(1)
                            elif exit_input.lower().startswith('n'):
                                break
                            else:
                                print("Please input a valid choice!")
                                continue
                break
            elif log_file_input.lower().startswith('n'):
                break
            else:
                print("Please input a valid choice!")
                continue


def main():
    """The main functionality of this script."""
    signal(SIGINT, signal_handler)  # Register custom signal handler for SIGINT
    global currentid, seedminer_launcher_proc, active_job, exit_after_job

    python_check()
    arch_and_os_check()
    missing_module_check()
    file_check()
    create_dir(LOG_DIR, exist_ok=True)  # This creates MISC_DIR as well, if non-existent
    move_files_if_needed()

    log_file_number_increment = 0
    while os.path.isfile(LOG_PREFIX + "-{}.log".format(log_file_number_increment)):
        log_file_number_increment += 1

    appended_log_file = LOG_PREFIX + "-{}.log".format(log_file_number_increment)

    # Setup logging to file
    logging.basicConfig(format="%(asctime)s %(levelname)s: %(message)s", level=logging.DEBUG,
                        filename=appended_log_file, filemode='w')

    # Setup logging to console as well
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    formatter = logging.Formatter("\n%(levelname)s: %(message)s")
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    check_for_updates()

    with open('seedminer_launcher3.py') as f:
        line_num = 0
        for line in f:
            line_num += 1
            if line_num != 1:
                continue
            elif 'Seedminer v2.1.5' in line:
                break
            else:
                print("You must use this release of Seedminer:\n"
                      "https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n"
                      "if you want to use this script!")
                print("Please download and extract it,\n"
                      'and copy this script ("{}")\n'
                      'inside of the new "seedminer" folder\n'
                      "After that's done, feel free to rerun this script".format(SEEDMINER_AUTOLAUNCHER))
                enter_key_prompt()
                sys.exit(0)

    delete_file("movable.sed", path_not_exist_ok=True, exit_on_=False)

    if os.path.isfile(TM):
        with open(TM, 'rb') as file:
            total_mined = pickle.load(file)
    else:
        total_mined = 0
    print("Total seeds mined previously: {}".format(total_mined))

    if os.path.isfile(MN):
        with open(MN, 'rb') as file:
            miner_username = pickle.load(file)
        if not re.match("^[a-zA-Z0-9_\\-|]*$", miner_username):
            print('Invalid character(s) detected in your {} file!'.format(miner_username))
            delete_file(MN, path_not_exist_ok=True)
            print("Re-run this script to choose a new username")
            sys.exit(0)
    else:
        print("No username set, which name would you like to have on the leaderboards?\n"
              "Allowed Characters are: a-Z 0-9 - |")
        while True:
            miner_username = input("Enter your desired name: ")
            if not re.match("^[a-zA-Z0-9_\\-|]*$", miner_username):
                print("Invalid character inputted!\nAllowed Characters are: a-Z 0-9 - |")
                continue
            else:
                break
        with open(MN, 'wb') as file:
            pickle.dump(miner_username, file)

    print("Welcome {}, your mining effort is truly appreciated!".format(miner_username))

    if os.path.isfile(BM):
        with open(BM, 'rb') as file:
            benchmark_success = pickle.load(file)
        if benchmark_success == 1:
            print("Detected past benchmark! You're good to go!")
        elif benchmark_success == 0:
            print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
            print("If you want, you can rerun the benchmark by deleting the 'benchmark' file"
                  "and by rerunning the script")
            enter_key_prompt()
            sys.exit(0)
        else:
            print("Either something weird happened or you tried to mess with the benchmark result")
            print("Feel free to delete the 'benchmark' file\n"
                  "in your {} directory and then rerun\n"
                  "this script to start a new benchmark".format(MISC_DIR))
            enter_key_prompt()
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
            enter_key_prompt()
            sys.exit(1)
        if time_finish > time_target:
            print("\nYour graphics card is too slow to help BruteforceMovable!")
            with open(BM, 'wb') as file:
                pickle.dump(0, file)
            print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
                  " and then rerun this script to start a new benchmark")
            enter_key_prompt()
            sys.exit(0)
        else:
            print("\nYour graphics card is strong enough to help BruteforceMovable!\n")
            with open(BM, 'wb') as file:
                pickle.dump(1, file)

    while True:
        try:
            file_check()
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
                                kill_pro_tree(process.pid)
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
                        delete_file(latest_file, path_not_exist_ok=True)
                        failed_upload_attempts = 0
                        # Try three times and then you're out
                        while failed_upload_attempts < 3:
                            print("\nUploading...")
                            ur = s.post(BASE_URL + '/upload?task=' + currentid + "&minername="
                                        + urllib.parse.quote_plus(miner_username),
                                        files={'movable': open('movable.sed', 'rb')})
                            print(ur.text)
                            if ur.text == "success":
                                currentid = ""
                                print("Upload succeeded!")
                                total_mined += 1
                                print("Total seeds mined: {}".format(total_mined))
                                with open(TM, 'wb') as file:
                                    pickle.dump(total_mined, file)
                                delete_file("movable.sed", path_not_exist_ok=True)
                                if exit_after_job is True:
                                    print("\nExiting by earlier request...")
                                    sleep(1)
                                    sys.exit(0)
                                print("Press Ctrl-C if you would like to exit")
                                on_ctrlc_kill_when_prompt = True
                                sleep(5)
                                break
                            else:
                                failed_upload_attempts += 1
                                if failed_upload_attempts == 3:
                                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                                    currentid = ""
                                    print("The script failed to upload files three times...")
                                    enter_key_prompt()
                                    sys.exit(1)
                                print("Upload failed! The script will try to\n"
                                      "upload completed files {} more time(s)"
                                      " before exiting".format(3 - failed_upload_attempts))
                                print("Waiting 10 seconds...")
                                print("Press Ctrl-C if you would like to exit")
                                sleep(10)
                    elif os.path.isfile("movable.sed") is False and skipUploadBecauseJobBroke is False:
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                        currentid = ""
                        try:
                            os.remove(BM)
                        except OSError:
                            pass
                        print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
                        print("Please try figuring this out before running this script again")
                        enter_key_prompt()
                        sys.exit(1)
        except Exception:
            active_job = False

            print("\nAn unexpected error occurred!")
            print_traceback()
            print("Writing exception to '{}'...".format(appended_log_file))
            logging.exception("An unexpected error occurred!")
            enter_key_prompt()
            sys.exit(1)


if __name__ == '__main__':
    main()
