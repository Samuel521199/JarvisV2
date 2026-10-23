"""On-demand Windows resource sampling. No agent, child process or model call."""
import ctypes
import os
import threading
import time

_lock=threading.Lock()
_last=None


def sample():
    global _last
    result={'sampled_at':time.time(),'cpu_percent':None,'memory_percent':None,'memory_total':None,'memory_used':None,'gpu_percent':None,'vram_used':None,'gpu_note':'尚无可用的 GPU 计数器；不以估算代替采样'}
    if os.name!='nt':return result
    class Memory(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong) for n in ['total','available','page_total','page_available','virtual_total','virtual_available','extended']]
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);memory=Memory();memory.length=ctypes.sizeof(memory)
    if kernel.GlobalMemoryStatusEx(ctypes.byref(memory)):
        result.update(memory_percent=memory.load,memory_total=memory.total,memory_used=memory.total-memory.available)
    class FileTime(ctypes.Structure):_fields_=[('low',ctypes.c_uint32),('high',ctypes.c_uint32)]
    idle,kern,user=FileTime(),FileTime(),FileTime()
    if kernel.GetSystemTimes(ctypes.byref(idle),ctypes.byref(kern),ctypes.byref(user)):
        values=tuple((v.high<<32)|v.low for v in [idle,kern,user])
        with _lock:
            if _last:
                total=values[1]+values[2]-_last[1]-_last[2]
                if total>0:result['cpu_percent']=round(max(0,min(100,100*(1-(values[0]-_last[0])/total))),1)
            _last=values
    return result
