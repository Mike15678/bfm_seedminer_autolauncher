#!/usr/bin/env python3

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

try:
    import datetime
except ImportError:
    datetime = None
import errno
import glob
try:
    import logging
except ImportError:
    logging = None
import os
import pickle
try:
    import platform
except ImportError:
    platform = None
try:
    import psutil
except ImportError:
    psutil = None
import re
try:
    import requests
except ImportError:
    requests = None
import shutil
import signal
try:
    import subprocess
except ImportError:
    subprocess = None
import sys
import subprocess
try:
    import sysconfig
except ImportError:
    sysconfig = None
import time
import traceback
try:
    import urllib.parse
except ImportError:
    urllib = None

# Website Constants
BASE_URL = "https://bruteforcemovable.com"
UPDATE_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/raw/master"
CURRENT_VERSION = "3.0.0-dev"  # TODO: 3.0.0-dev -> 3.0.0-beta -> 3.0.0-stable
# psutil stuff is broken, don't run!

# File/Folder Constants
BFM_LOG = "bfm_seedminer_autolauncher.log"  # Newly named log file
BENCHM = "benchmark"
SEEDMINER_AUTOLAUNCHER = "bfm_seedminer_autolauncher.py"
MN = "miner_name"  # Newly named "miner name" file
TM = "total_mined"
BFM_DIR = "bfm_misc/"

# OS Constants
WINDOWS = sys.platform == 'win32'
MACOS = sys.platform == 'darwin'
LINUX = sys.platform == 'linux'
WINDOWS_OR_MACOS = sys.platform in {'win32', 'darwin'}
MACOS_OR_LINUX = sys.platform in {'darwin', 'linux'}


def enter_key_quit_message():
    """Makes a person (hopefully) press the Enter key.

    The caller is responsible for quitting the script.
    """
    input("Press the Enter key to quit...")


def signal_handler(sig, frame):
    """A signal handler that handles the action of pressing Ctrl + C (SIGINT)."""
    # Gotta love our globals :)
    global active_job, currentid, on_ctrlc_kill_when_prompt, quit_after_job
    signal.signal(signal.SIGINT, original_sigint)  # This restores the original sigint handler
    if currentid != "" and active_job is True:
        active_job = False
        psutil_process = get_children_processes(process.pid)
        for proc in psutil_process:
            proc.suspend()
        sent_requeue_url = False
        while True:
            try:
                quit_input = input("Requeue job and quit, or continue job? [r/c]: ")
                if quit_input.lower().startswith('r'):
                    print("Requeuing job...")
                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                    sent_requeue_url = True
                    kill_process_tree(process.pid)
                    print("Note that if you would like to kill a job instead,\n"
                          "please let the script run until a job is auto-killed!")
                    enter_key_quit_message()
                    sys.exit(0)
                elif quit_input.lower().startswith('c'):
                    print("Continuing job...")
                    for proc in psutil_process:
                        proc.resume()
                    signal.signal(signal.SIGINT, signal_handler)
                    break
                else:
                    print("Please enter in a valid choice!")
                    continue
            except KeyboardInterrupt:
                print("Alright, quitting...")
                if not sent_requeue_url:
                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                try:
                    kill_process_tree(process.pid)
                except psutil.Error:
                    pass
                time.sleep(1)
                sys.exit(0)
    elif on_ctrlc_kill_when_prompt is True:
        on_ctrlc_kill_when_prompt = False
        while True:
            try:
                quit_input = input("Would you like to quit after the next job finishes (instead of now)? [y/n]: ")
                if quit_input.lower().startswith("y"):
                    quit_after_job = True
                    signal.signal(signal.SIGINT, signal_handler)
                    break
                elif quit_input.lower().startswith("n"):
                    print("Quitting...")
                    time.sleep(1)
                    sys.exit(0)
                else:
                    print("Please enter in a valid choice!")
                    continue
            except KeyboardInterrupt:
                print("Alright, quitting...")
                time.sleep(1)
                sys.exit(0)
    else:
        sys.exit(0)


def python_check():
    """A simple check to see if the Python version being used is supported.

    If the Python version is supported, then a check will make sure that "sys.executable" points
    to a valid Python interpreter path.
    """
    if sys.version_info < (3, 0):  # This check should work with Python 2.0.0+
        sys.stdout.write("Python %s.%s.%s is not supported!"
                         " Please use Python 3.3.0 or later!\n" % sys.version_info[0:3])
        try:
            raw_input("Press the Enter key to quit...")
        except NameError:  # More or less a workaround for pyflakes
            # If this somehow happens on a real Python installation, uhh...
            raw_input = None
            assert raw_input is None
            time.sleep(5)
        sys.exit(1)
    elif sys.version_info < (3, 4, 1):
        print("Python {}.{}.{} is not supported! Please use Python 3.4.1 or later!".format(*sys.version_info))
        enter_key_quit_message()
        sys.exit(1)
    elif sys.executable is None or sys.executable == '':
        print("Error: Unable to determine the path to the Python interpreter!")
        print("Try reinstalling Python 3 and see if you still receive this error message.")
        enter_key_quit_message()
        sys.exit(1)


def arch_and_os_check():
    """An experimental check that determines if your computer is 64-bit and if the OS is supported."""
    computer_architecture = platform.machine()
    supported_architecture = computer_architecture.endswith('64')
    # Yes, it's possible that it can't determine your processor's architecture
    if not supported_architecture and computer_architecture != '':
        print("You are using an unsupported computer architecture ({}-bit)!\n"
              "This script only works on 64-bit (Windows, macOS, and Linux) computers.".format(platform.machine()[-2:]))
        print("If you believe to have received this message in mistake,\n"
              "feel free to make a GitHub issue here:\n"
              "https://github.com/Mike15678/bfm_seedminer_autolauncher/issues")
        enter_key_quit_message()
        sys.exit(1)
    supported_os = sys.platform in {'win32', 'darwin', 'linux'}
    if not supported_os:
        print("You are using an unsupported Operating System\n"
              "or environment ({})!\n"
              "This script only works on (64-bit) Windows, macOS, and Linux computers.".format(sys.platform))
        enter_key_quit_message()
        sys.exit(1)


def missing_module_check():
    """A check that determines if the "requests" and "psutil" modules are installed on your computer
    and provides instructions on how to install them if not.
    """
    modules_to_install = None
    if requests is None and psutil is None:
        if pip_install("requests psutil") is 0:
            print('Installed the "requests" and "psutil" modules automatically.\n'
                  'Please rerun this script.')
            logging.shutdown()  # This is an important function I've been not using this whole time
            try:
                subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
            except OSError as e:
                if e.errno == errno.ENOENT:
                    print('Unable to find "{}" in the current directory!'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
                else:
                    print('Error while trying to re-launch "{}"'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
            sys.exit(0)
        else:
            print('The "requests" and "psutil" Python modules are not installed on this computer and could not be automatically installed!\n'
                  'Please install them via pip and then feel free to rerun this script')
            modules_to_install = "requests psutil"
    elif requests is None:
        if pip_install("requests") is 0:
            print('Installed the "requests" module automatically.\n'
                  'Please rerun this script.')
            logging.shutdown()  # This is an important function I've been not using this whole time
            try:
                subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
            except OSError as e:
                if e.errno == errno.ENOENT:
                    print('Unable to find "{}" in the current directory!'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
                else:
                    print('Error while trying to re-launch "{}"'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
            sys.exit(0)
        else:
            print('The "requests" module is not installed on this computer and could not be automatically installed!\n'
                  'Please install it via pip and then feel free to rerun this script')
            modules_to_install = "requests"
    elif psutil is None:
        if pip_install("psutil") is 0:
            print('Installed the "psutil" module automatically.\n'
                  'Please rerun this script.')
            logging.shutdown()  # This is an important function I've been not using this whole time
            try:
                subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
            except OSError as e:
                if e.errno == errno.ENOENT:
                    print('Unable to find "{}" in the current directory!'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
                else:
                    print('Error while trying to re-launch "{}"'.format(SEEDMINER_AUTOLAUNCHER))
                    raise
            sys.exit(0)
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
        enter_key_quit_message()
        sys.exit(1)

def pip_multi_install(modules_to_install)
    """Install the list of modules passed under "modules_to_install" with pip.
    
    Parameters:
        modules_to_install (str): Modules that should be installed with pip. Should be a space separated str.
        
    Returns:
        int: Exit code of subprocess call.
    """
    return subprocess.call([sys.executable, "-m", "pip", "install", "--user", module_to_install ])

def get_children_processes(parent_process_pid):
    """Determines the children started by a parent process
    and then returns them."""
    parent = psutil.Process(parent_process_pid)
    children = parent.children(recursive=True)
    return children


def kill_process_tree(pid, including_parent=True):
    """Kills a parent process and its children using psutil."""
    parent = psutil.Process(pid)
    children = parent.children(recursive=True)
    psutil.wait_procs(children, timeout=5)
    if including_parent:
        parent.kill()
        parent.wait(5)


# https://stackoverflow.com/a/16696317 thx
def download_file(url, local_filename):
    """Downloads files and returns the name of the file
    that is saved locally.
    """
    # NOTE the stream=True parameter
    r1 = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f1:
        for chunk in r1.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f1.write(chunk)
                # f1.flush() commented by recommendation from J.F.Sebastian
    return local_filename


def file_check():
    """A check that determines if there are any missing files on your computer."""
    check_failures = 0
    if WINDOWS:
        bfcl_name = 'bfcl.exe'
    else:
        bfcl_name = 'bfcl'
    if not os.path.isfile(bfcl_name):
        check_failures += 1
        print('Error: Unable to find "{}" in the current directory.\n'
              'Try disabling your antivirus (if you have one) and then\n'
              'redownload Seedminer:\n'
              'https://github.com/Mike15678/seedminer/releases/tag/v2.1.5\n'
              'and extract it,\n'
              'and then copy this script ("{}")\n'
              'inside of the new "seedminer" folder\n'
              "After that's done, feel free to rerun this script".format(bfcl_name, SEEDMINER_AUTOLAUNCHER))
    if check_failures != 0:
        enter_key_quit_message()
        sys.exit(1)


def make_bfm_dir_if_needed():
    """Make a bfm_directory if it doesn't already exist."""
    try:
        if not os.path.isdir(BFM_DIR):
            os.makedirs(BFM_DIR, exist_ok=True)
    except OSError:
        print('\nError while creating "{}" directory!'.format(BFM_DIR))
        raise


def move_files_if_needed():
    """Moves files in the current directory into a new directory if needed.

    New directories are made if they don't already exist."""
    try:
        if os.path.isfile(BENCHM):
            os.renames(BENCHM, BFM_DIR + BENCHM)
    except OSError:
        print('\nError while moving "benchmark" file!')
        raise
    try:
        if os.path.isfile("minername"):  # Old "miner name" file
            os.renames("minername", BFM_DIR + MN)
    except OSError:
        print('\nError while moving and renaming "minername" file')
        raise
    try:
        if os.path.isfile(TM):
            os.renames(TM, BFM_DIR + TM)
    except OSError:
        print('\nError while moving "total_mined" file')
        raise
    try:
        if os.path.isfile("bfm_autolauncher.log"):
            os.renames("bfm_autolauncher.log", BFM_DIR + BFM_LOG)
    except OSError:
        print('\nError while moving and renaming "bfm_autolauncher.log" file.\n'
              'This is normal if you just updated the script.')


def check_for_updates():
    """Checks for updates to this script and for the msed db."""
    print("Checking for updates...")
    r0 = s.get(UPDATE_URL + "/static/autolauncher_version")
    if r0.text != CURRENT_VERSION:
        print("Updating seedminer_autolauncher script...")
        download_file(UPDATE_URL + "/static/" + SEEDMINER_AUTOLAUNCHER,
                      SEEDMINER_AUTOLAUNCHER)
        logging.shutdown()  # This is an important function I've been not using this whole time
        try:
            subprocess.call([sys.executable, SEEDMINER_AUTOLAUNCHER])
        except OSError as e:
            if e.errno == errno.ENOENT:
                print('Unable to find "{}" in the current directory!'.format(SEEDMINER_AUTOLAUNCHER))
                raise
            else:
                print('Error while trying to re-launch "{}"'.format(SEEDMINER_AUTOLAUNCHER))
                raise
        sys.exit(0)
    else:
        print("No script update available!")
        print("Updating seedminer db...")
        subprocess.call([sys.executable, "seedminer_launcher3.py", "update-db"])


if __name__ == "__main__":
    # Not constants; just setting these here
    currentid = ""
    process = None
    active_job = False
    on_ctrlc_kill_when_prompt = False
    quit_after_job = False

    # This can be done on both Python 2 & 3 so let's do this before the Python version check
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal_handler)

    python_check()
    arch_and_os_check()
    missing_module_check()
    file_check()

    make_bfm_dir_if_needed()
    move_files_if_needed()

    logging.basicConfig(level=logging.DEBUG, filename=BFM_DIR + BFM_LOG, filemode='w')

    s = requests.Session()

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
                enter_key_quit_message()
                sys.exit(0)

    try:
        if os.path.isfile("movable.sed"):
            os.remove("movable.sed")
    except OSError as e_mov:
        if e_mov.errno != errno.ENOENT:
            print('Unable to delete "movable.sed" from the current directory!')
            raise

    if os.path.isfile(BFM_DIR + TM):
        with open(BFM_DIR + TM, "rb") as file:
            total_mined = pickle.load(file)
    else:
        total_mined = 0
    print("Total seeds mined previously: {}".format(total_mined))

    if os.path.isfile(BFM_DIR + MN):
        with open(BFM_DIR + MN, "rb") as file:
            miner_username = pickle.load(file)
        if not re.match("^[a-zA-Z0-9_\-|]*$", miner_username):
            print('Invalid character(s) detected in {} file!'.format(miner_username))
            try:
                os.remove(BFM_DIR + MN)
            except OSError as e_mun:
                if e_mun.errno != errno.ENOENT:
                    print('Unable to delete "{}" file!')
                    raise
            print("Re-run this script to choose a new username")
            sys.exit(1)
    else:
        print("No username set, which name would you like to have on the leaderboards?\n"
              "Allowed Characters are: a-Z 0-9 - |")
        while True:
            miner_username = input("Enter your desired name: ")
            if not re.match("^[a-zA-Z0-9_\-|]*$", miner_username):
                print("Invalid character inputted!")
                continue
            else:
                break
        with open(BFM_DIR + MN, "wb") as file:
            pickle.dump(miner_username, file, protocol=3)

    print("Welcome " + miner_username + ", your mining effort is truly appreciated!")

    if os.path.isfile(BFM_DIR + BENCHM):
        with open(BFM_DIR + BENCHM, "rb") as file:
            benchmark_success = pickle.load(file)
        if benchmark_success == 1:
            print("Detected past benchmark! You're good to go!")
        elif benchmark_success == 0:
            print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
            print("If you want, you can rerun the benchmark by deleting the 'benchmark' file"
                  "and by rerunning the script")
            enter_key_quit_message()
            sys.exit(0)
        else:
            print("Either something weird happened or you tried to mess with the benchmark result")
            print("Feel free to delete the 'benchmark' file\n"
                  "in your {} directory and then rerun\n"
                  "this script to start a new benchmark".format(BFM_DIR))
            enter_key_quit_message()
            sys.exit(1)
    else:
        print("\nBenchmarking...")
        time_target = time.time() + 215
        download_file(BASE_URL + "/static/impossible_part1.sed",
                      "movable_part1.sed")
        process = subprocess.call(
            [sys.executable, "seedminer_launcher3.py", "gpu", "0", "5"])
        if process == 101:
            time_finish = time.time()
        else:
            print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
            print("Please try figuring this out before running this script again")
            enter_key_quit_message()
            sys.exit(1)
        if time_finish > time_target:
            print("\nYour graphics card is too slow to help BruteforceMovable!")
            with open(BFM_DIR + BENCHM, "wb") as file:
                pickle.dump(0, file, protocol=3)
            print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
                  " and then rerun this script to start a new benchmark")
            enter_key_quit_message()
            sys.exit(0)
        else:
            print("\nYour graphics card is strong enough to help BruteforceMovable!\n")
            with open(BFM_DIR + BENCHM, "wb") as file:
                pickle.dump(1, file, protocol=3)

    while True:
        try:
            try:
                r = s.get(BASE_URL + "/getWork")
            except:
                print("Error. Waiting 30 seconds...")
                time.sleep(30)
                continue
            if r.text == "nothing":
                print("No work. Waiting 30 seconds...")
                time.sleep(30)
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
                    if WINDOWS:
                        process = psutil.Popen(
                            [sys.executable, "seedminer_launcher3.py", "gpu", "0", "80"], creationflags=0x00000200)
                    else:
                        signal.signal(signal.SIGINT, signal.SIG_IGN)
                        process = psutil.Popen(
                            [sys.executable, "seedminer_launcher3.py", "gpu", "0", "80"], preexec_fn=os.setpgrp)
                        signal.signal(signal.SIGINT, signal_handler)
                    timer = 0
                    while process.poll() is None:
                        # We need to poll for kill more often then we check server
                        # Otherwise, we would waste up to 30 secs after finish
                        active_job = True
                        timer += 1
                        time.sleep(1)
                        if timer % 30 == 0:
                            r3 = s.get(BASE_URL + '/check?task=' + currentid)
                            if r3.text != "ok":
                                currentid = ""
                                skipUploadBecauseJobBroke = True
                                active_job = False
                                print("\nJob cancelled or expired, killing...")
                                kill_process_tree(process.pid)
                                print("press ctrl-c if you would like to quit")
                                on_ctrlc_kill_when_prompt = True
                                time.sleep(5)
                                break
                    if process.returncode == 101 and skipUploadBecauseJobBroke is False:
                        skipUploadBecauseJobBroke = True
                        active_job = False
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=y")
                        currentid = ""
                        print("\nJob reached the specified max offset and was killed...")
                        print("press ctrl-c if you would like to quit")
                        on_ctrlc_kill_when_prompt = True
                        time.sleep(5)
                    elif os.path.isfile("movable.sed") and skipUploadBecauseJobBroke is False:
                        active_job = False
                        # seedhelper2 has no msed database but we upload these anyway so zoogie can have them
                        # * means all if need specific format then *.csv
                        list_of_files = glob.glob('msed_data_*.bin')
                        latest_file = max(list_of_files, key=os.path.getctime)
                        failed_upload_attempts = 0
                        # Try three times and then you're out
                        while failed_upload_attempts < 3:
                            print("\nUploading...")
                            ur = s.post(BASE_URL + '/upload?task=' + currentid + "&minername="
                                        + urllib.parse.quote_plus(miner_username), files={
                                         'movable': open('movable.sed', 'rb'), 'msed': open(latest_file, 'rb')})
                            print(ur.text)
                            if ur.text == "success":
                                currentid = ""
                                print("Upload succeeded!")
                                try:
                                    os.remove("movable.sed")
                                except OSError as e_mov2:
                                    if e_mov2 != errno.ENOENT:
                                        print('Unable to delete "movable.sed" from current directory!')
                                        raise
                                try:
                                    os.remove(latest_file)
                                except OSError as e_lf:
                                    if e_lf != errno.ENOENT:
                                        print('Unable to delete "msed_data_*.bin" from current directory!')
                                        raise
                                total_mined += 1
                                print("Total seeds mined: {}".format(total_mined))
                                with open(BFM_DIR + TM, "wb") as file:
                                    pickle.dump(total_mined, file, protocol=3)
                                if quit_after_job is True:
                                    print("\nQuiting by earlier request...")
                                    time.sleep(1)
                                    sys.exit(0)
                                print("press ctrl-c if you would like to quit")
                                on_ctrlc_kill_when_prompt = True
                                time.sleep(5)
                                break
                            else:
                                failed_upload_attempts += 1
                                if failed_upload_attempts == 3:
                                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                                    currentid = ""
                                    print("The script failed to upload files three times; Quitting...")
                                    sys.exit(1)
                                print("Upload failed! The script will try to\n"
                                      "upload completed files {} more time(s)"
                                      " before quitting".format(3 - failed_upload_attempts))
                                print("Waiting 10 seconds...")
                                print("press ctrl-c if you would like to quit")
                                time.sleep(10)
                    elif os.path.isfile("movable.sed") is False and skipUploadBecauseJobBroke is False:
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                        currentid = ""
                        if os.path.isfile(BFM_DIR + BENCHM):
                            os.remove(BFM_DIR + BENCHM)
                        print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
                        print("Please try figuring this out before running this script again")
                        enter_key_quit_message()
                        sys.exit(1)
        except Exception:
            active_job = False
            if currentid != "" and process is not None:
                s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                kill_process_tree(process.pid)
                currentid = ""
            print("\nError")
            traceback.print_exc()
            print("Writing exception to 'bfm_autolauncher.log'...")
            logging.exception(datetime.datetime.now())
            print("done")
            print("Waiting 10 seconds...")
            print("press ctrl-c if you would like to quit")
            time.sleep(10)
