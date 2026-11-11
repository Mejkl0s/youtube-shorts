"""Bundled sidecar entry: one private loopback socket, no external web server."""
import json
import os
from pathlib import Path
import socket
import sys


def main():
    if not os.environ.get('RANK_DESKTOP_TOKEN') or not os.environ.get('RANK_DESKTOP_ADMIN_TOKEN'):
        raise SystemExit('Desktop backend requires a private parent session.')
    directory=Path(os.environ['RANK_DATA_DIR']).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    os.environ.update(RANK_DESKTOP_MODE='1',RANK_LOCAL_MODE='1',RANK_FREE_ONLY='1',STUDIO_PUBLIC='0',STUDIO_PASSWORD='',
                      PIPER_MODEL_DIR=str(directory/'models'),PYTHONUTF8='1')
    # Environment API keys are not imported into the desktop provider vault.
    for key in list(os.environ):
        if key.endswith('_API_KEY') or key in ('STUDIO_USERNAME','OPENAI_BASE_URL'):os.environ.pop(key,None)
    os.environ['RANK_BUNDLED_OCR']='0'
    if getattr(sys,'frozen',False):
        resources=Path(sys._MEIPASS)
        os.environ['PATH']=str(resources/'bin')+os.pathsep+os.environ.get('PATH','')
        bundled=resources/'ocr'
        if (bundled/'tesseract.exe').is_file():
            os.environ['PATH']=str(bundled)+os.pathsep+os.environ['PATH']
            os.environ['TESSDATA_PREFIX']=str(bundled/'tessdata')
            os.environ['RANK_BUNDLED_OCR']='1'
    else:sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
    if os.name=='nt' and os.environ['RANK_BUNDLED_OCR']!='1':
        ocr=Path(os.environ.get('ProgramFiles','C:\\Program Files'))/'Tesseract-OCR'
        if (ocr/'tesseract.exe').is_file():os.environ['PATH']=str(ocr)+os.pathsep+os.environ.get('PATH','')
    import uvicorn
    from backend import main as backend
    from backend import desktop_api,desktop_models
    server=uvicorn.Server(uvicorn.Config(backend.app,host='127.0.0.1',port=0,log_level='warning',access_log=False))
    desktop_api.shutdown_callback=lambda:setattr(server,'should_exit',True)
    import threading
    stopped=threading.Event()
    def watch_parent():
        parent=int(os.environ.get('RANK_DESKTOP_PARENT_PID','0'))
        if not parent:return
        handle=None
        if os.name=='nt':
            import ctypes
            kernel=ctypes.WinDLL('kernel32',use_last_error=True)
            kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];kernel.OpenProcess.restype=ctypes.c_void_p
            kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];kernel.CloseHandle.argtypes=[ctypes.c_void_p]
            handle=kernel.OpenProcess(0x100000,False,parent)
        try:
            while not stopped.wait(1):
                alive=(handle and kernel.WaitForSingleObject(handle,0)==258) if os.name=='nt' else os.getppid()==parent
                if not alive:
                    backend.work.cancel_all();desktop_models.shutdown();server.should_exit=True;break
        finally:
            if handle:kernel.CloseHandle(handle)
    threading.Thread(target=watch_parent,name='desktop-parent',daemon=True).start()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen(128)
        print('RANK_STUDIO_READY='+json.dumps({'port':listener.getsockname()[1]}),flush=True)
        try:server.run(sockets=[listener])
        finally:stopped.set();desktop_models.shutdown();backend.executor.shutdown(wait=True,cancel_futures=True)


if __name__=='__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    if sys.argv[1:3]==['-m','yt_dlp']:
        # Frozen sys.executable is this sidecar, not a general Python interpreter.
        # Keep existing cancellable yt-dlp subprocess calls working in a bundle.
        import yt_dlp
        yt_dlp.main(sys.argv[3:])
    else:main()
