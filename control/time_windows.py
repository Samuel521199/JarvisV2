"""Fixed-offset quiet windows shared by standing text and mailbox work."""
from datetime import datetime,timezone


def quiet(config,now):
    start,end=config['quiet_start'],config['quiet_end']
    if start==end:return False
    local=datetime.fromtimestamp(now+config['utc_offset_minutes']*60,timezone.utc)
    minute=local.hour*60+local.minute
    return start<=minute<end if start<end else minute>=start or minute<end
