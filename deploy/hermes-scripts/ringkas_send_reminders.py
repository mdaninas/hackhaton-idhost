"""Wrapper tipis -- logika sebenarnya ada di repo (source of truth):
/root/hackhathon/ringkas/send_reminders.py
"""
import sys

sys.path.insert(0, "/root/hackhathon")
from ringkas.send_reminders import main  # noqa: E402

if __name__ == "__main__":
    main()
