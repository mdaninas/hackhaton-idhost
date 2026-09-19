"""Wrapper tipis -- logika sebenarnya ada di repo (source of truth):
/root/hackhathon/ringkas/daily_summary.py
"""
import sys

sys.path.insert(0, "/root/hackhathon")
from ringkas.daily_summary import main  # noqa: E402

if __name__ == "__main__":
    main()
