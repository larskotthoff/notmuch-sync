import pytest
import json
from plumbum import local, ProcessExecutionError

class ShellResult:
    def __init__(self, returncode, stdout, stderr):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self._data = None
    
    @property
    def data(self):
        if self._data is None:
            try:
                self._data = json.loads(self.stdout.strip())
            except:
                self._data = self.stdout.strip()
        return self._data

class Shell:
    def run(self, *args, **kwargs):
        cmd = local[args[0]]
        if len(args) > 1:
            cmd = cmd[args[1:]]
        
        try:
            retcode, stdout, stderr = cmd.run(**kwargs)
            return ShellResult(retcode, stdout, stderr)
        except ProcessExecutionError as e:
            return ShellResult(e.retcode, e.stdout, e.stderr)

@pytest.fixture
def shell():
    return Shell()