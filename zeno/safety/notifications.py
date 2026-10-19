"""
Desktop Notification System for Zeno Autonomous Safety and Background Jobs.
Uses winotify on Windows with a native PowerShell toast fallback.
"""

from __future__ import annotations

import subprocess
import sys


def send_desktop_notification(title: str, message: str) -> bool:
    """
    Display a Windows native desktop notification toast.
    Attempts winotify first; falls back to Windows PowerShell toast.
    """
    if sys.platform != "win32":
        return False

    # 1. Attempt winotify
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="Zeno Desktop Assistant",
            title=title,
            msg=message,
            duration="short",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        return True
    except Exception:
        pass

    # 2. Native Windows PowerShell Toast Fallback
    try:
        safe_title = title.replace('"', '`"')
        safe_msg = message.replace('"', '`"')
        ps_script = (
            f"[void] [System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms');"
            f"$objNotifyIcon = New-Object System.Windows.Forms.NotifyIcon;"
            f"$objNotifyIcon.Icon = [System.Drawing.SystemIcons]::Information;"
            f"$objNotifyIcon.BalloonTipIcon = 'Info';"
            f"$objNotifyIcon.BalloonTipTitle = \"{safe_title}\";"
            f"$objNotifyIcon.BalloonTipText = \"{safe_msg}\";"
            f"$objNotifyIcon.Visible = $True;"
            f"$objNotifyIcon.ShowBalloonTip(5000);"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=5,
        )
        return True
    except Exception:
        return False
