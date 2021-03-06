#!/usr/bin/env python3

from maintenance_windows import Timestamp

t1 = Timestamp("Wed", "08", "45")
t2 = t1.next(30)
assert t2.get_time() == "09:15"
assert t2.get_day_and_time() == "Wed:09:15"
assert t2.get_day_name() == "Wednesday"
assert t2.get_cron() == "15 9 ? * WED *"

t1 = Timestamp("Sun", "22", "37")
t2 = t1.next(70)
assert t2.get_day_and_time() == "Sun:23:47"

t3 = t2.next(25)
assert t3.get_time() == "00:12"
assert t3.get_day_and_time() == "Mon:00:12"
assert t3.get_day_name() == "Monday"
assert t3.get_cron() == "12 0 ? * MON *"

t4 = t3.next(1440)  # 1,440 minutes = 24 hours
assert t4.get_day_and_time() == "Tue:00:12"
assert t4.get_cron() == "12 0 ? * TUE *"

print("All tests OK")
