"""User-scoped DPAPI vault. Non-Windows development never persists secrets."""
import base64
import ctypes
import json
import os
import threading
from pathlib import Path

_lock=threading.RLock()
_ephemeral={}


class SecretStorageError(RuntimeError):pass


def atomic_json(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    try:
        with temporary.open('w',encoding='utf-8') as file:
            json.dump(data,file,ensure_ascii=False);file.flush();os.fsync(file.fileno())
        if os.name!='nt':temporary.chmod(0o600)
        temporary.replace(path)
    finally:temporary.unlink(missing_ok=True)


def protect(value, decrypt=False):
    if os.name!='nt':raise SecretStorageError('Trvalé ukládání klíčů vyžaduje Windows DPAPI.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    source=ctypes.create_string_buffer(value)
    incoming=Blob(len(value),ctypes.cast(source,ctypes.POINTER(ctypes.c_ubyte)));outgoing=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; no machine-wide encryption or plaintext fallback.
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,
                       ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    if not function(ctypes.byref(incoming),None,None,None,None,1,ctypes.byref(outgoing)):
        raise SecretStorageError('Windows nemohl otevřít úložiště klíčů pro tohoto uživatele.')
    try:return ctypes.string_at(outgoing.data,outgoing.size)
    finally:kernel.LocalFree(ctypes.cast(outgoing.data,ctypes.c_void_p))


class Vault:
    def __init__(self,root):self.path=Path(root)/'credentials.dpapi.json'

    def _read(self):
        if not self.path.exists():return {}
        try:
            data=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError()
            return data
        except (OSError,ValueError):
            raise SecretStorageError('Úložiště klíčů je poškozené. Soubor nebyl přepsán.') from None

    def get(self,provider):
        with _lock:
            if os.name!='nt':return _ephemeral.get((str(self.path),provider),'')
            value=self._read().get(provider)
            try:return protect(base64.b64decode(value,validate=True),True).decode() if value else ''
            except (ValueError,TypeError):raise SecretStorageError('Uložený klíč nelze přečíst. Nahraď ho v Nastavení; původní soubor nebyl automaticky přepsán.') from None

    def set(self,provider,key):
        with _lock:
            if os.name!='nt':
                if key:_ephemeral[(str(self.path),provider)]=key
                else:_ephemeral.pop((str(self.path),provider),None)
                return
            data=self._read()
            if key:data[provider]=base64.b64encode(protect(key.encode())).decode()
            else:data.pop(provider,None)
            atomic_json(self.path,data)

    def contains(self,provider):
        with _lock:
            return bool(self._read().get(provider)) if os.name=='nt' else bool(_ephemeral.get((str(self.path),provider)))
