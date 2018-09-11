#!/usr/bin/env python3

# MIT License
#
# Copyright (c) 2018 figgyc, Valentijn V., deadphoenix8091, Michael M.
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

from __future__ import print_function
try:
    import datetime
except ImportError:
    datetime = None
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
import time
import traceback
try:
    import urllib.parse
except ImportError:
    urllib = None

# Constants
BFM_LOG = "bfm_seedminer_autolauncher.log"  # Newly named log file
BENCHM = "benchmark"
MN = "miner_name"  # Newly named "miner name" file
TM = "total_mined"
BASE_URL = "https://bruteforcemovable.com"
UPDATE_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/blob/master"
CURRENT_VERSION = "2.6.1"  # TODO: 2.6.1 -> 3.0.0
if os.name == 'nt':
    BFM_DIR = "bruteforce_movable_misc\\"  # Escape the escape character
else:
    BFM_DIR = "bruteforce_movable_misc/"


def signal_handler(sig, frame):
    """A signal handler that handles the action of pressing Ctrl + C.

    Note that if bfCL was running, we've already killed it by pressing Ctrl + C.
    """
    global active_job, currentid, on_ctrlc_kill_when_prompt, quit_after_job
    signal.signal(signal.SIGINT, original_sigint)  # This restores the original sigint handler
    if currentid != "" and active_job is True:
        active_job = False
        print("Requeuing job for another person to mine...")
        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
        print("Note that if you would like to kill a job instead,"
              " please let the script run until a job is auto-killed!")
        try:
            input("Press the Enter key to quit")
        except KeyboardInterrupt:
            print("Alright, quitting...")
            time.sleep(1)
            sys.exit(0)
        sys.exit(0)
    elif on_ctrlc_kill_when_prompt is True:
        on_ctrlc_kill_when_prompt = False
        while True:
            try:
                quit_input = input("Would you like to quit after the next job finishes (instead of now)? [y/n]: ")
            except KeyboardInterrupt:
                print("Alright, quitting...")
                time.sleep(1)
                sys.exit(0)
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
    else:
        sys.exit(0)


def python_check():
    """A simple check to see if the Python version being used is supported."""
    if sys.version_info < (3, 0):
        print("Python %s.%s.%s is not supported! Please use Python 3.3.0 or later!" % sys.version_info[0:3])
        try:
            raw_input("Press the Enter key to quit")
        except NameError:  # More or less a workaround for pyflakes
            # If this somehow happens on a real Python installation, uhh....
            raw_input = None
            assert raw_input is None
        sys.exit(1)
    elif sys.version_info < (3, 3):
        print("Python {}.{}.{} is not supported! Please use Python 3.3.0 or later!".format(*sys.version_info))
        input("Press the Enter key to quit")
        sys.exit(1)


def os_and_arch_check():
    """A check that determines if your computer is 64-bit and if the OS is supported."""
    supported_architecture = platform.machine().endswith('64')
    # Yes, it's possible that it can't determine your processor's architecture
    if not supported_architecture and platform.machine() != '':
        print("You are using an unsupported computer architecture: {}!\n"
              "This script only works on 64-bit computers".format(platform.machine()[-2:]))
        print("If you believe to have received this message in mistake, feel free to make a GitHub issue")
        input("Press the Enter to key to quit")
        sys.exit(1)
    supported_os = sys.platform in {'win32', 'cygwin', 'msys', 'linux', 'linux2', 'darwin'}
    if not supported_os:
        print("You are an unsupported Operating System: {}!\n"
              "This script only works on Windows, macOS, and Linux".format(sys.platform()))
        input("Press the Enter to key to quit")
        sys.exit(1)


def requests_module_check():
    """A check that determines if the "requests" module is installed on your computer
    and provides instructions on how to install it.
    """
    if requests is None:
        print('The "requests" module is not installed on this computer!\n'
              'Please install it via pip and then feel free to rerun this script')
        if sys.platform in {'win32', 'darwin'}:
            if sys.version_info < (3, 4):
                print("That being said, it would seem that your computer is running a Python version\n"
                      "that is less than 3.4\n"
                      "This usually means that pip is NOT installed so please consider updating\n"
                      "to the latest Python 3 version")
            if sys.platform == 'win32':
                print("Once that's done, you can open an administrator\n"
                      "command prompt/Powershell window and then enter\n"
                      'in "py -3 -m pip install requests" (without the quotes)')
            elif sys.platform == 'darwin':
                print("Once that's done, you can enter\n"
                      'in "py -3 -m pip install --user requests" (without the quotes)')
            input("Press the Enter key to quit")
        else:
            if sys.platform in {'cygwin', 'msys'}:
                print("For Cygwin-like environments, this can generally be done by\n"
                      'entering in "python3 -m pip install --user requests" (without the quotes)')
            elif sys.platform in {'darwin', 'linux'}:
                print("For Linux/macOS, this can generally be done by\n"
                      'entering in "python3 -m pip install --user requests" (without the quotes)')


def bfcl_process_killer():
    """A function that kills bfCL using your OS's process manager."""
    if sys.platform in {'win32', 'cygwin', 'msys'}:
        subprocess.call(["taskkill", "/IM", "bfcl.exe", "/F"])
    else:
        subprocess.call(["killall", "-9", "bfcl"])


# https://stackoverflow.com/a/16696317 thx
def download_file(url, local_filename):
    """A function that downloads files and returns the name of the file
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


def program_check():
    """A check that determines if there are any missing programs on your computer."""
    check_failures = 0
    if sys.platform in {'win32', 'cygwin', 'msys'}:
        proc_manager_name = "taskkill"
        bfcl_name = "bfcl.exe"
    else:
        proc_manager_name = "killall"
        bfcl_name = "bfcl"
    check_1 = shutil.which(proc_manager_name)
    if check_1 is None:
        check_failures += 1
        print('Error: Unable to find the program "{}"'.format(proc_manager_name))
    if not os.path.isfile("seedminer_launcher3.py"):
        check_failures += 1
        print('Error: Unable to find the "seedminer_launcher3.py" script in the current directory')
    if not os.path.isfile(bfcl_name):
        check_failures += 1
        print('Error: Unable to find "{}" in the current directory'.format(bfcl_name))

    if check_failures != 0:
        input("Press the Enter key to quit")
        sys.exit(1)


def move_files_if_needed():
    """A function that moves files in the current directory into a new folder if needed."""
    if not os.path.isdir(BFM_DIR):
        print('NOTE: Did not detect a "{}" folder in the current directory!\n'
              'Creating one...'.format(BFM_DIR))
        os.makedirs(BFM_DIR)

    try:
        if os.path.isfile(BFM_LOG):
            os.remove(BFM_LOG)
    except OSError:
        pass  # We'll try again next time
    if os.path.isfile(BENCHM):
        os.rename(BENCHM, BFM_DIR + BENCHM)
    if os.path.isfile("minername"):  # Old "miner name" file
        os.rename("minername", BFM_DIR + MN)
    if os.path.isfile(TM):
        os.rename(TM, BFM_DIR + TM)


def check_for_updates():
    """A function that simply checks for updates to this script
    """
    print("Checking for updates...")
    r0 = s.get(UPDATE_URL + "/static/autolauncher_version")
    if r0.text != CURRENT_VERSION:
        print("Updating...")
        download_file(UPDATE_URL + "/static/bfm_seedminer_autolauncher.py",
                      "bfm_seedminer_autolauncher.py")
        subprocess.call([sys.executable, "bfm_seedminer_autolauncher.py"])
        sys.exit(0)


if __name__ == "__main__":
    # Not constants; just setting these here
    currentid = ""
    active_job = False
    on_ctrlc_kill_when_prompt = False
    quit_after_job = False

    # This can be done on both Python 2 & 3 so let's do this before the Python version check
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal_handler)

    python_check()
    os_and_arch_check()

    program_check()

    move_files_if_needed()

    logging.basicConfig(level=logging.DEBUG, filename=BFM_DIR + 'bfm_autolauncher.log', filemode='w')

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
                      "and copy this script inside of the new 'seedminer' folder\n"
                      "After that's done, feel free to rerun this script")
                input("Press the Enter key to quit")
                sys.exit(0)

    if os.path.isfile("movable.sed"):
        os.remove("movable.sed")

    if os.path.isfile(BFM_DIR + TM):
        with open(BFM_DIR + TM, "rb") as file:
            total_mined = pickle.load(file)
    else:
        total_mined = 0
    print("Total seeds mined previously: {}".format(total_mined))

    print("Updating seedminer db...")
    subprocess.call([sys.executable, "seedminer_launcher3.py", "update-db"])

    if os.path.isfile(BFM_DIR + MN):
        with open(BFM_DIR + MN, "rb") as file:
            miner_name = pickle.load(file)
    else:
        print("No username set, which name would you like to have on the leaderboards?\n"
              "Allowed Characters are: a-Z 0-9 - |")
        while True:
            miner_name = input("Enter your desired name: ")
            if not re.match("^[a-zA-Z0-9_\-|]*$", miner_name):
                print("Invalid character inputted!")
                continue
            else:
                break
        with open(BFM_DIR + MN, "wb") as file:
            pickle.dump(miner_name, file, protocol=3)

    print("Welcome " + miner_name + ", your mining effort is truly appreciated!")

    if os.path.isfile(BFM_DIR + BENCHM):
        with open(BFM_DIR + BENCHM, "rb") as file:
            benchmark_success = pickle.load(file)
        if benchmark_success == 1:
            print("Detected past benchmark! You're good to go!")
        elif benchmark_success == 0:
            print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
            print("If you want, you can rerun the benchmark by deleting the 'benchmark' file"
                  "and by rerunning the script")
            input("Press the Enter key to quit")
            sys.exit(0)
        else:
            print("Either something weird happened or you tried to tamper with the benchmark result")
            print("Feel free to delete the 'benchmark' file and then rerun this script to start a new benchmark")
            input("Press the Enter key to quit")
            sys.exit(1)
    else:
        print("\nBenchmarking...")
        timeTarget = time.time() + 215
        download_file(BASE_URL + "/static/impossible_part1.sed",
                      "movable_part1.sed")
        process = subprocess.call(
            [sys.executable, "seedminer_launcher3.py", "gpu", "0", "5"])
        if process == 101:
            timeFinish = time.time()
        else:
            print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
            print("Please try figuring this out before running this script again")
            input("Press the Enter key to quit")
            sys.exit(1)
        if timeFinish > timeTarget:
            print("\nYour graphics card is too slow to help BruteforceMovable!")
            with open(BFM_DIR + BENCHM, "wb") as file:
                pickle.dump(0, file, protocol=3)
            print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
                  " and then rerun this script to start a new benchmark")
            input("Press the Enter key to quit")
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
                    process = subprocess.Popen(
                        [sys.executable, "seedminer_launcher3.py", "gpu", "0", "80"])
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
                                bfcl_process_killer()
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
                                        + urllib.parse.quote_plus(miner_name), files={
                                         'movable': open('movable.sed', 'rb'), 'msed': open(latest_file, 'rb')})
                            print(ur.text)
                            if ur.text == "success":
                                currentid = ""
                                print("Upload succeeded!")
                                os.remove("movable.sed")
                                os.remove(latest_file)
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
                        input("Press the Enter key to quit")
                        sys.exit(1)
        except Exception:
            active_job = False
            if currentid != "":
                s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                bfcl_process_killer()
                currentid = ""
            print("\nError")
            traceback.print_exc()
            print("Writing exception to 'bfm_autolauncher.log'...")
            logging.exception(datetime.datetime.now())
            print("done")
            print("Waiting 10 seconds...")
            print("press ctrl-c if you would like to quit")
            time.sleep(10)
