#!/usr/bin/env python3

import datetime
import glob
import logging
import os
import pickle
import requests
import signal
import subprocess
import sys
import time
import traceback
import re
import urllib.parse

os.makedirs("bfm", exist_ok=True) # Creates bfm info dir, doing this before setting up logging so that logs can be written to this dir.
logging.basicConfig(level=logging.DEBUG, filename='bfm/bfm_autolauncher.log', filemode='w')

s = requests.Session() 
baseurl = "https://bruteforcemovable.com"
currentid = ""
currentVersion = "2.6.1"
ctrc_kills_al_script = True
active_job = False
os_name = os.name


def signal_handler(sig, frame):
    # If bfCL was running, we've already killed it by pressing Ctr + C
    global active_job
    global currentid
    if currentid != "" and active_job is True:
        active_job = False
        while True:
            try:
                cancel = input("Kill job or requeue? [k/r]: ")
            except:
                s.get(baseurl + "/killWork?task=" + currentid + "&kill=n")
                sys.exit(1)
            p = ""
            if cancel.lower().strip() == "r":
                p = "n"
            elif cancel.lower().strip() == "k":
                p = "y"
            if p != "":
                s.get(baseurl + "/killWork?task=" + currentid + "&kill=" + p)
                while True:
                    try:
                        quit_input = input("Would you like to mine another job? [y/n]: ")
                    except:
                        sys.exit(1)
                    if quit_input.lower().strip() == "y":
                        currentid = ""
                        break
                    elif quit_input.lower().strip() == "n":
                        print("Exiting...")
                        time.sleep(1)
                        sys.exit(0)
                    else:
                        print("Please enter in a valid choice!")
                        continue
                break
            else:
                print("Please enter in a valid choice!")
                continue
    elif ctrc_kills_al_script is True:
        sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def process_killer():
    global ctrc_kills_al_script  # o no
    ctrc_kills_al_script = False
    if os_name == 'nt':
        process.send_signal(signal.CTRL_C_EVENT)  # dammit, Windows
    else:
        process.send_signal(signal.SIGINT)  # POSIX ftw
    time.sleep(0.25)  # What's before this takes a while apparently...
    ctrc_kills_al_script = True


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
r0 = s.get(baseurl + "/static/autolauncher_version")
if r0.text != currentVersion:
    print("Updating...")
    download_file(baseurl + "/static/bfm_seedminer_autolauncher.py",
                  "bfm_seedminer_autolauncher.py")
    subprocess.call([sys.executable, "bfm_seedminer_autolauncher.py"])
    sys.exit(0)

if os.path.isfile("bfm/bfm_autolauncher_exception.log"):
    try:
        os.remove("bfm/bfm_autolauncher_exception.log")
    except OSError:
        pass  # We'll try again next time

with open('seedminer_launcher3.py') as f:
    line_num = 0
    for line in f:
        line_num += 1
        if line_num != 1:
            continue
        elif 'Seedminer v2.1.5' in line:
            break
        else:
            print("You must use this release of Seedminer: https://github.com/Mike15678/seedminer/releases/tag/v2.1.5"
                  " if you want to use this script!")
            print("Please download and extract it, and copy this script inside of the new 'seedminer' folder")
            print("After that's done, feel free to rerun this script")
            input("Press the Enter key to exit")
            sys.exit(0)

if os.path.isfile("movable.sed"):
    os.remove("movable.sed")

if os.path.isfile("bfm/total_mined"):
    with open("bfm/total_mined", "rb") as file:
        total_mined = pickle.load(file)
else:
    total_mined = 0
print("Total seeds mined previously: {}".format(total_mined))

print("Updating seedminer db...")
subprocess.call([sys.executable, "seedminer_launcher3.py", "update-db"])

miner_name = ""
if os.path.isfile("bfm/minername"):
    with open("bfm/minername", "rb") as file:
        miner_name = pickle.load(file)
else:
    miner_name = input("No username set, which name would you like to have on the leaderboards? \n (Allowed Characters a-Z 0-9 - _ | ): ")
    with open("bfm/minername", "wb") as file:
        pickle.dump(miner_name, file)
		
miner_name = re.sub('[^a-zA-Z0-9\_\-\|]+' ,'', miner_name)
print("Welcome " + miner_name + ", really appreciate your mining effort!")

if os.path.isfile("bfm/benchmark"):
    with open("bfm/benchmark", "rb") as file:
        benchmark_success = pickle.load(file)
    if benchmark_success == 1:
        print("Detected past benchmark! You're good to go!")
    elif benchmark_success == 0:
        print("Detected past benchmark! Your graphics card was too slow to help BruteforceMovable!")
        print("If you want, you can rerun the benchmark by deleting the 'benchmark' file and by rerunning the script")
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
    download_file(baseurl + "/static/impossible_part1.sed",
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
        with open("bfm/benchmark", "wb") as file:
            pickle.dump(0, file)
        print("If you ever get a new graphics card, feel free to delete the 'benchmark' file"
              " and then rerun this script to start a new benchmark")
        input("Press the Enter key to exit")
        sys.exit(0)
    else:
        print("\nYour graphics card is strong enough to help BruteforceMovable!\n")
        with open("bfm/benchmark", "wb") as file:
            pickle.dump(1, file)

while True:
    try:
        try:
            r = s.get(baseurl + "/getWork")
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
            r2 = s.get(baseurl + "/claimWork?task=" + currentid)
            if r2.text == "error":
                print("Device already claimed, trying again...")
            else:
                print("\nDownloading part1 for device " + currentid)
                download_file(baseurl + '/getPart1?task=' +
                              currentid, 'movable_part1.sed')
                print("Bruteforcing " + str(datetime.datetime.now()))
                process = subprocess.Popen(
                    [sys.executable, "seedminer_launcher3.py", "gpu", "0", "80"])
                timer = 0
                while process.poll() is None:
                    # we need to poll for kill more often then we check server because we would waste up to 30 secs after finish
                    active_job = True
                    timer += 1
                    time.sleep(1)
                    if timer % 30 == 0:
                        r3 = s.get(baseurl + '/check?task=' + currentid)
                        if r3.text != "ok":
                            currentid = ""
                            skipUploadBecauseJobBroke = True
                            active_job = False
                            print("\nJob cancelled or expired, killing...")
                            process_killer()
                            print("press ctrl-c if you would like to quit")
                            time.sleep(5)
                            break
                if process.returncode == 101 and skipUploadBecauseJobBroke is False:
                    skipUploadBecauseJobBroke = True
                    active_job = False
                    s.get(baseurl + "/killWork?task=" + currentid + "&kill=y")
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
                        ur = s.post(baseurl + '/upload?task=' + currentid + "&minername=" + urllib.parse.quote_plus(miner_name), files={
                                    'movable': open('movable.sed', 'rb'), 'msed': open(latest_file, 'rb')})
                        print(ur.text)
                        if ur.text == "success":
                            currentid = ""
                            print("Upload succeeded!")
                            os.remove("movable.sed")
                            os.remove(latest_file)
                            total_mined += 1
                            print("Total seeds mined: {}".format(total_mined))
                            with open("bfm/total_mined", "wb") as file:
                                pickle.dump(total_mined, file)
                            print("press ctrl-c if you would like to quit")
                            time.sleep(5)
                            break
                        else:
                            failed_upload_attempts += 1
                            if failed_upload_attempts == 3:
                                s.get(baseurl + "/killWork?task=" + currentid + "&kill=n")
                                currentid = ""
                                print("The script failed to upload files three times; exiting...")
                                sys.exit(1)
                            print("Upload failed! The script will try to upload completed files {} more time(s) before exiting".format(3 - failed_upload_attempts))
                            print("Waiting 10 seconds...")
                            print("press ctrl-c if you would like to quit")
                            time.sleep(10)
                elif os.path.isfile("movable.sed") is False and skipUploadBecauseJobBroke is False:
                    s.get(baseurl + "/killWork?task=" + currentid + "&kill=n")
                    currentid = ""
                    if os.path.isfile("bfm/benchmark"):
                        os.remove("bfm/benchmark")
                    print("It seems that the graphics card brute-forcer (bfCL) wasn't able to run correctly")
                    print("Please try figuring this out before running this script again")
                    input("Press the Enter key to exit")
                    sys.exit(1)
    except Exception:
        active_job = False
        if currentid != "":
            s.get(baseurl + "/killWork?task=" + currentid + "&kill=n")
            process_killer()
            currentid = ""
        print("\nError")
        traceback.print_exc()
        print("Writing exception to 'bfm_autolauncher.log'...")
        logging.exception(datetime.datetime.now())
        print("done")
        print("Waiting 10 seconds...")
        print("press ctrl-c if you would like to quit")
        time.sleep(10)
