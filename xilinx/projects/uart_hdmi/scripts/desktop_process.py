"""Launch legacy desktop tools from a packaged Windows terminal/app.

Use the documented desktop app process policy so DLL lookup includes PATH.
This changes only the new process; no registry, system DLL or tool files change.
https://learn.microsoft.com/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
"""
import ctypes as c
from ctypes import wintypes as w
import os
from pathlib import Path
import subprocess
import sys
import time


def run(command, cwd, output):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if os.name != 'nt':
        return subprocess.run(command, cwd=cwd).returncode
    k = c.WinDLL('kernel32', use_last_error=True)
    size = w.UINT(0)
    if k.GetCurrentPackageFullName(c.byref(size), None) == 15700:
        return subprocess.run(command, cwd=cwd).returncode
    import msvcrt
    class SI(c.Structure):
        _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR), ('title', w.LPWSTR),
                    ('x', w.DWORD), ('y', w.DWORD), ('xs', w.DWORD), ('ys', w.DWORD),
                    ('xc', w.DWORD), ('yc', w.DWORD), ('fill', w.DWORD), ('flags', w.DWORD),
                    ('show', w.WORD), ('reserved_size', w.WORD), ('reserved2', c.c_void_p),
                    ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]
    class SIX(c.Structure):
        _fields_ = [('si', SI), ('attributes', c.c_void_p)]
    class PI(c.Structure):
        _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]
    k.InitializeProcThreadAttributeList.argtypes = [c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)]
    k.UpdateProcThreadAttribute.argtypes = [c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t, c.c_void_p, c.c_void_p]
    k.DeleteProcThreadAttributeList.argtypes = [c.c_void_p]
    k.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD, c.c_void_p, w.LPCWSTR, c.c_void_p, c.POINTER(PI)]
    k.SetHandleInformation.argtypes = [w.HANDLE, w.DWORD, w.DWORD]
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    k.GetExitCodeProcess.argtypes = [w.HANDLE, c.POINTER(w.DWORD)]
    k.CloseHandle.argtypes = [w.HANDLE]
    length = c.c_size_t()
    k.InitializeProcThreadAttributeList(None, 1, 0, c.byref(length))
    attributes = c.create_string_buffer(length.value)
    if not k.InitializeProcThreadAttributeList(attributes, 1, 0, c.byref(length)):
        raise c.WinError(c.get_last_error())
    policy = w.DWORD(1)  # PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_ENABLE_PROCESS_TREE
    if not k.UpdateProcThreadAttribute(attributes, 0, 0x20012, c.byref(policy), 4, None, None):
        raise c.WinError(c.get_last_error())
    commandline = subprocess.list2cmdline([str(arg) for arg in command])
    if Path(command[0]).suffix.lower() in ('.bat', '.cmd'):
        commandline = f'{os.environ.get("COMSPEC", "C:/Windows/System32/cmd.exe")} /d /s /c "{commandline}"'
    print('Using Windows desktop tool compatibility launcher', flush=True)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb', buffering=0) as log, open(os.devnull, 'rb') as stdin:
        si = SIX(); si.si.cb = c.sizeof(si); si.attributes = c.cast(attributes, c.c_void_p)
        si.si.flags = 0x100
        si.si.stdout = si.si.stderr = msvcrt.get_osfhandle(log.fileno())
        si.si.stdin = msvcrt.get_osfhandle(stdin.fileno())
        for handle in (si.si.stdout, si.si.stdin):
            if not k.SetHandleInformation(handle, 1, 1):
                raise c.WinError(c.get_last_error())
        pi = PI()
        if not k.CreateProcessW(None, c.create_unicode_buffer(commandline), None, None, True,
                                0x08080000, None, str(cwd), c.byref(si), c.byref(pi)):
            raise c.WinError(c.get_last_error())
        k.DeleteProcThreadAttributeList(attributes)
        try:
            with output.open('rb') as reader:
                while True:
                    done = k.WaitForSingleObject(pi.process, 500) == 0
                    chunk = reader.read()
                    if chunk:
                        print(chunk.decode('utf-8', errors='replace'), end='', flush=True)
                    if done:
                        break
            code = w.DWORD()
            if not k.GetExitCodeProcess(pi.process, c.byref(code)):
                raise c.WinError(c.get_last_error())
            return code.value
        finally:
            k.CloseHandle(pi.thread)
            k.CloseHandle(pi.process)
