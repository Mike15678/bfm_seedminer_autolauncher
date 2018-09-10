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
BFM_LOG = "bfm_autolauncher.log"
BENCHM = "benchmark"
MN = "miner_name"  # Newly named "miner name" file
TM = "total_mined"
BASE_URL = "https://bruteforcemovable.com"
UPDATE_URL = "https://github.com/Mike15678/bfm_seedminer_autolauncher/blob/master"
CURRENT_VERSION = "2.6.1"  # 2.6.1 -> 3.0.0


def signal_handler(sig, frame):
    """A signal handler that handles the action of pressing Ctrl + C.

    Note that if bfCL was running, we've already killed it by pressing Ctrl + C.
    """
    global active_job, currentid
    signal.signal(signal.SIGINT, original_sigint)
    if currentid != "" and active_job is True:
        active_job = False
        print("Requeuing job...")
        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
        print("Note that if you would like to kill a job instead,"
              " please let the script run until it is auto-killed!")
        while True:
            try:
                quit_input = input("Would you like to mine another job? [y/n]: ")
            except KeyboardInterrupt:
                print("Alright, exiting...")
                time.sleep(1)
                sys.exit(0)
            if quit_input.lower().startswith("y"):
                currentid = ""
                signal.signal(signal.SIGINT, signal_handler)
                break
            elif quit_input.lower().startswith("n"):
                print("Exiting...")
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
        print("Python %s.%s.%s is not supported! Please use Python 3.2.0 or later!" % sys.version_info[0:3])
        raw_input("Press the Enter key to exit...")
        sys.exit(1)
    elif sys.version_info < (3, 2):
        print("Python {}.{}.{} is not supported! Please use Python 3.2.0 or later!".format(*sys.version_info))
        input("Press the Enter key to exit...")
        sys.exit(1)


def os_and_arch_check():
    """A check that determines if your computer is 64-bit and if the OS is supported."""
    supported_architecture = platform.machine().endswith('64')
    # Yes, it's possible that it can't determine your processor's architecture
    if not supported_architecture and platform.machine() != '':
        print("You are using an unsupported computer architecture: {}!\n"
              "This script only works on 64-bit computers".format(platform.machine()[-2:]))
        print("If you believe to have received this message in mistake, feel free to make a GitHub issue")
        input("Press the Enter to key to exit...")
        sys.exit(1)
    supported_os = sys.platform in {'win32', 'cygwin', 'msys', 'linux', 'linux2', 'darwin'}
    if not supported_os:
        print("You are an unsupported Operating System: {}!\n"
              "This script only works on Windows, macOS, and Linux".format(sys.platform()))
        input("Press the Enter to key to exit...")
        sys.exit(1)


def requests_module_check():
    """A simple check that determines if the "requests" module is installed on your computer."""
    pass


if __name__ == "__main__":
    python_check()
    os_and_arch_check()
    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal_handler)

    if os.name == 'nt':
        bfm_dir = "bruteforce_movable_misc\\"  # Escape the escape character
    else:
        bfm_dir = "bruteforce_movable_misc/"

    if not os.path.isdir(bfm_dir):
        os.makedirs(bfm_dir)

    try:
        if os.path.isfile(BFM_LOG):
            os.remove(BFM_LOG)
    except OSError:
        pass  # We'll try again next time
    if os.path.isfile(BENCHM):
        os.rename(BENCHM, bfm_dir + BENCHM)
    if os.path.isfile("minername"):  # Old "miner name" file
        os.rename("minername", bfm_dir + MN)
    if os.path.isfile(TM):
        os.rename(TM, bfm_dir + TM)

    logging.basicConfig(level=logging.DEBUG, filename=bfm_dir + 'bfm_autolauncher.log', filemode='w')

    s = requests.Session()
    currentid = ""
    active_job = False


    def bfcl_process_killer():
        if os.name == 'nt':
            subprocess.call(["taskkill", "/IM", "bfcl.exe", "/F"])
        else:
            subprocess.call(["killall", "-9", "bfcl"])


    # https://stackoverflow.com/a/16696317 thx
    def download_file(url, local_filename):
        # NOTE the stream=True parameter
        r1 = requests.get(url, stream=True)
        with open(local_filename, 'wb') as f1:
            for chunk in r1.iter_content(chunk_size=1024):
                if chunk:  # filter out keep-alive new chunks
                    f1.write(chunk)
                    # f1.flush() commented by recommendation from J.F.Sebastian
        return local_filename


    print("Checking for updates...")
    r0 = s.get(UPDATE_URL + "/static/autolauncher_version")
    if r0.text != CURRENT_VERSION:
        print("Updating...")
        download_file(UPDATE_URL + "/static/bfm_seedminer_autolauncher.py",
                      "bfm_seedminer_autolauncher.py")
        subprocess.call([sys.executable, "bfm_seedminer_autolauncher.py"])
        sys.exit(0)

    with open('seedminer_launcher3.py') as f:
        line_num = 0
        for line in f:
            line_num += 1
            if line_num != 1:
                continue
            elif 'Seedminer v2.1.5' in line:
                break
            else:
                print("You must use this release of Seedminer:"
                      " https://github.com/Mike15678/seedminer/releases/tag/v2.1.5"
                      " if you want to use this script!")
                print("Please download and extract it, and copy this script inside of the new 'seedminer' folder")
                print("After that's done, feel free to rerun this script")
                input("Press the Enter key to exit")
                sys.exit(0)

    if os.path.isfile("movable.sed"):
        os.remove("movable.sed")

    if os.path.isfile("total_mined"):
        with open("total_mined", "rb") as file:
            total_mined = pickle.load(file)
    else:
        total_mined = 0
    print("Total seeds mined previously: {}".format(total_mined))

    print("Updating seedminer db...")
    subprocess.call([sys.executable, "seedminer_launcher3.py", "update-db"])

    miner_name = ""
    if os.path.isfile("minername"):
        with open("minername", "rb") as file:
            miner_name = pickle.load(file)
    else:
        miner_name = input("No username set, which name would you like to have on the leaderboards?\n"
                           "(Allowed Characters a-Z 0-9 - _ | ): ")
        with open("minername", "wb") as file:
            pickle.dump(miner_name, file, protocol=3)

    miner_name = re.sub('[^a-zA-Z0-9_\-|]+', '', miner_name)
    print("Welcome " + miner_name + ", your mining effort is truly appreciated!")

    if os.path.isfile("benchmark"):
        with open("benchmark", "rb") as file:
            benchmark_success = pickle.load(file)
        if benchmark_success == 1:
            print("Detected past benchmark! You're good to go!")
        elif benchmark_success == 0:
            print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
            print("If you want, you can rerun the benchmark by deleting the 'benchmark' file"
                  "and by rerunning the script")
            input("Press the Enter key to exit")
            sys.exit(0)
        else:
            print("Either something weird happened or you tried to tamper with the benchmark result")
            print("Feel free to delete the 'benchmark' file and then rerun this script to start a new benchmark")
            input("Press the Enter key to exit")
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
            input("Press the Enter key to exit")
            sys.exit(1)
        if timeFinish > timeTarget:
            print("\nYour graphics card is too slow to help BruteforceMovable!")
            with open("benchmark", "wb") as file:
                pickle.dump(0, file, protocol=3)
            print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
                  " and then rerun this script to start a new benchmark")
            input("Press the Enter key to exit")
            sys.exit(0)
        else:
            print("\nYour graphics card is strong enough to help BruteforceMovable!\n")
            with open("benchmark", "wb") as file:
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
                                time.sleep(5)
                                break
                    if process.returncode == 101 and skipUploadBecauseJobBroke is False:
                        skipUploadBecauseJobBroke = True
                        active_job = False
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=y")
                        currentid = ""
                        print("\nJob reached the specified max offset and was killed...")
                        print("press ctrl-c if you would like to quit")
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
                            ur = s.post(BASE_URL + '/upload?task=' + currentid + "&minername=" + urllib.parse.quote_plus(miner_name), files={
                                        'movable': open('movable.sed', 'rb'), 'msed': open(latest_file, 'rb')})
                            print(ur.text)
                            if ur.text == "success":
                                currentid = ""
                                print("Upload succeeded!")
                                os.remove("movable.sed")
                                os.remove(latest_file)
                                total_mined += 1
                                print("Total seeds mined: {}".format(total_mined))
                                with open("total_mined", "wb") as file:
                                    pickle.dump(total_mined, file, protocol=3)
                                print("press ctrl-c if you would like to quit")
                                time.sleep(5)
                                break
                            else:
                                failed_upload_attempts += 1
                                if failed_upload_attempts == 3:
                                    s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                                    currentid = ""
                                    print("The script failed to upload files three times; exiting...")
                                    sys.exit(1)
                                print("Upload failed! The script will try to upload completed files {} more time(s) before exiting".format(3 - failed_upload_attempts))
                                print("Waiting 10 seconds...")
                                print("press ctrl-c if you would like to quit")
                                time.sleep(10)
                    elif os.path.isfile("movable.sed") is False and skipUploadBecauseJobBroke is False:
                        s.get(BASE_URL + "/killWork?task=" + currentid + "&kill=n")
                        currentid = ""
                        if os.path.isfile("benchmark"):
                            os.remove("benchmark")
                        print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
                        print("Please try figuring this out before running this script again")
                        input("Press the Enter key to exit")
                        sys.exit(1)
        except Exception as e:
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
