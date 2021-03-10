import subprocess


def check_call_quiet(cmd, cwd=None):
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=cwd)


def check_output_noerr(cmd, cwd=None):
    return subprocess.check_output(cmd, encoding="utf8", cwd=cwd, stderr=subprocess.DEVNULL).strip()


def check_output_capture_error(cmd, cwd=None):
    return subprocess.check_output(cmd, encoding="utf8", cwd=cwd, stderr=subprocess.STDOUT).strip()
