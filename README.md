# Surface-Fakedev
Prerequirements:
python3 (should be installed already), python3-crcmod, python3-serial

```
sudo apt get install python3-crcmod python3-serial
```
Mimics battery devices in /etc/fakedev (workaround until a battery module is available)
Download zip file and unpack in your home directory. Make it excecutable. "sh" won't work (too much bash stuff in there).
```
chmod 755 install.sh
```
Run install.sh as root
```
sudo ./install.sh
```
This will create
1. a cronjob in "/etc/cron.d/power-status running every minute
2. copies the file "pwr-cron.sh" to "/sbin" execed by cron
3. copies the file "power-status.py" to "/usr/bin/" which will be execed
by "pwr-cron.sh"
The install script will ask for the # of batteries installed in your surface system. 1 or 2 are supported.
The "pwr-cron.sh" script will create the directories "/etc/fakedev/power_supply/BAT1" BAT2 (if 2 batteries)
and ADP1 (the AC power supply). This mimics "/sys/class/power_supply/" which cannot be created from user space.
Inside the fakedev directories the "power-status.py" python3 script will create the uevent files, where you
can point your battery monitor to (possible with i3status). Other DE's will need a workaround via i.e. gnome shell.
I cannot provide this. The entry in your i3status.conf is as follows
```
battery 1 { 
        # format = "%status %percentage %remaining %emptytime"
        # format = " %percentage"
        format = " %status %percentage"
        format_down = "No battery"
        last_full_capacity = true
        integer_battery_capacity = true
        # status_chr = ""
        status_chr = "⚡"
        # status_bat = "bat"
        # status_bat = "☉"
        status_bat = "" 
        # status_unk = "?"
        status_unk = ""
        # status_full = ""
        status_full = "☻" 
        low_threshold = 15
        path = "/etc/fakedev/power_supply/BAT1/uevent"  <-------------
}
```
A solution for gnome can be found here: https://github.com/jakeday/linux-surface/issues/28#issuecomment-428876786
At this time it has a little glitch and won't work with only one battery. Work around this by creating a link:
```
sudo ln -s /etc/fakedev/power_supply/BAT1/uevent /etc/fakedev/power_supply/BAT2/uevent
```
It will then show 2 batteries.
The python script is originally from @qzed's proof of concept and can be found here:
https://gist.github.com/qzed/01a93568efb863f1b7887f0f375c03fc
I only modified it to fit the output to the uevent file format. I don't no anything about python
so please bare with me. The script works that's all we need for now.

I strongly advise to test the power-status.py script before installation.
Just run it from the directory you unzipped it as root. Make sure to change the ttyS0 to ttyS4 if running
on a Surface Book. Just run install.sh w/o root against the wall. It will however create the "power-status.py" script.
```
./install.sh
or
./install.sh ttyS4
```
then
```
sudo ./power-status.py adp1.uevent
sudo ./power-status.py bat1.uevent
```
if two batteries
```
sudo ./power-status.py bat2.uevent
```
The install.sh script now supports an argument. Either "ttyS0" or "ttyS4". Defaults to "ttyS0" if no argument given.
```
sudo ./install.sh ttyS0
or
sudo ./install.sh ttyS4
```
Of course, there is no guarantee for anything. Use on your own risk.
