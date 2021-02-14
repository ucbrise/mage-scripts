import os.path
import subprocess
import sys

def exec_sync(ip_address, command, check_exitcode = False):
    result = subprocess.run(("ssh", "-q", "-o", "StrictHostKeyChecking=no", "-i", "mage", "mage@{0}".format(ip_address), command))
    if result.returncode == 255:
        print("Got return code 255 from ssh: check your Internet connection")
        sys.exit(1)
    if check_exitcode:
        result.check_returncode()
    return result

def exec_async(ip_address, command, get_output = True):
    stdout_arg = None
    stderr_arg = None
    if get_output:
        stdout_arg = subprocess.PIPE
        stderr_arg = subprocess.PIPE
    result = subprocess.Popen(("ssh", "-q", "-o", "StrictHostKeyChecking=no", "-i", "mage", "mage@{0}".format(ip_address), command), stdout = stdout_arg, stderr = stderr_arg)
    return result

def copy_to(ip_address, directory, local_location, remote_location = "~"):
    assert local_location.strip() != ""
    assert remote_location.strip() != ""
    command = ("scp", "-q", "-o", "StrictHostKeyChecking=no", "-i", "mage", local_location, "mage@{0}:{1}".format(ip_address, remote_location))
    if directory:
        command = ("scp", "-q", "-o", "StrictHostKeyChecking=no", "-r") + command[4:]
    subprocess.run(command, check = True)

def copy_from(ip_address, directory, remote_location, local_location = "."):
    assert local_location.strip() != ""
    assert remote_location.strip() != ""
    command = ("scp", "-q", "-o", "StrictHostKeyChecking=no", "-i", "mage", "mage@{0}:{1}".format(ip_address, remote_location), local_location)
    if directory:
        command = ("scp", "-q", "-o", "StrictHostKeyChecking=no", "-r") + command[4:]
    subprocess.run(command, check = True)

def exec_script(ip_address, local_location, args = "", sync = True):
    remote_name = os.path.join("~", os.path.basename(local_location))
    remote_command = remote_name
    if args.strip() != "":
        remote_command = remote_command + " " + args
    copy_to(ip_address, False, local_location, remote_name)
    if sync:
        return exec_sync(ip_address, remote_command)
    else:
        return exec_async(ip_address, remote_command)
