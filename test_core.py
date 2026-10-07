from core import *
S = DEFAULT_SETTINGS
assert parse_time("4:05 PM")==16*60+5 and parse_time("16:05")==965 and parse_time("4p")==960
assert parse_time("03/22/2026 06:57 AM")==417 and parse_time("12:30 AM")==30 and parse_time("x") is None
assert hours_between("4:00 PM","12:30 AM")==8.5
assert tip_hours_between("4:00 PM","11:40 PM","11:00 PM")==7.0
assert tip_hours_between("5:00 PM","12:15 AM","11:00 PM")==6.0
assert tip_hours_between("5:00 PM","10:00 PM","11:00 PM")==5.0
assert detect_shift("9:40 AM","Saturday",S)=="Brunch" and detect_shift("7:00 AM","Monday",S)=="Morning" and detect_shift("3:55 PM","Monday",S)=="Dinner"
P={"Server":{"department":"FOH","tip_points":10},"Busser":{"department":"FOH","tip_points":5},
   "Bartender":{"department":"FOH","tip_points":5,"receives_bar_tips":True},
   "Barback":{"department":"FOH","tip_points":2,"bar_tip_share_pct":20},"Kitchen":{"department":"BOH","tip_points":0}}
E=[{"id":"a","position":"Server","shift":"Dinner","time_in":"4:00 PM","time_out":"11:45 PM"},
   {"id":"b","position":"Server","shift":"Dinner","time_in":"5:00 PM","time_out":"12:30 AM"},
   {"id":"c","position":"Busser","shift":"Dinner","time_in":"4:00 PM","time_out":"9:00 PM"},
   {"id":"d","position":"Bartender","shift":"Dinner","time_in":"4:00 PM","time_out":"11:00 PM"},
   {"id":"e","position":"Barback","shift":"Dinner","time_in":"6:00 PM","time_out":"11:00 PM"},
   {"id":"k","position":"Kitchen","shift":"Dinner","time_in":"3:00 PM","time_out":"10:00 PM"}]
r=split_shift_tips(E,1000,300,P,S)
for k,v in r["rows"].items(): print(k,v)
print(r)
tot=sum(v["total"] for v in r["rows"].values()); assert abs(tot-1300)<0.001, tot
E[2]["tip_override"]=50
r=split_shift_tips(E,1000,300,P,S); tot=sum(v["total"] for v in r["rows"].values()); assert abs(tot-1300)<0.001
print("override ok", r["rows"]["c"], r["rows"]["a"])
m={"id":"m","position":"Server","shift":"Morning","time_in":"7:00 AM","time_out":"10:00 AM","hours_manual":3.5}
assert auto_tip_hours(m,S)==3.5
m={"id":"m","position":"Server","shift":"Dinner","time_in":"4:00 PM","time_out":"11:30 PM","hours_manual":7.0}
assert auto_tip_hours(m,S)==6.42, auto_tip_hours(m,S)   # tip clock starts 4:05 PM
D=lambda i,o:auto_tip_hours({"shift":"Dinner","time_in":i,"time_out":o},S)
assert D("3:55 PM","10:53 PM")==D("4:01 PM","10:53 PM")==D("4:05 PM","10:53 PM")==6.8
assert D("4:08 PM","10:53 PM")==6.75 and D("3:23 PM","11:59 PM")==6.92
assert auto_tip_hours({"shift":"Brunch","time_in":"9:00 AM","time_out":"4:00 PM"},S)==7.0
print("ALL OK")
