# Surface-Fakedev
Description:
-
This mimics battery devices in /etc/fakedev (workaround until a battery module is available).
Pleas read carefully all the way to the end.
I strongly advise to test the power-status.py script before installation. Just run install.sh w/o root. It will fail but however create the "power-status.py" script if fed with the correct arguments. The script is tested running on SurfacPro 5 series but success has also been seen on Surface Book 4. It is tested on Ubuntu > 18 and Manjaro > 17 on kernels down to 4.9 series and latest 4.19rc. I used always Python3.7 but it should also work with 3.5

Prerequirements:
-
python3 (should be installed already), python3-crcmod, python3-serial
```
sudo apt get install python3-crcmod python3-serial
```
Test before installation for the serial port.
```
$ dmesg | grep ttyS
[    5.426845] dw-apb-uart.2: ttyS0 at MMIO 0xa1336000 (irq = 20, base_baud = 3000000) is a 16550A

$ sudo cat /proc/tty/driver/serial
serinfo:1.0 driver revision:
0: uart:16550A mmio:0xA1336000 irq:20 tx:510 rx:2130
1: uart:unknown port:000002F8 irq:3
2: uart:unknown port:000003E8 irq:4
3: uart:unknown port:000002E8 irq:3
```
If there are no results you cannot use this package unless you get an uart-driver attached to it. Your results do not have to match the examples above. The second ouput can be used to check if there is communication (tx and rx) happening on the device.


Installation:
-
Download zip file and unpack in your home directory. Make install.sh excecutable. "sh ./install.sh" won't work (too much bash stuff in there).
```
chmod 755 install.sh
```
Run install.sh as root. Examples: (Note: run w/o root just to create the power-status.py script first, no files will be copied)
```
sudo ./install.sh               # default. reads from /dev/ttyS4 at 3000000 baud
sudo ./install.sh ttyS0         # reads from /dev/ttyS0 at 3000000 baud
sudo ./install.sh ttyS4 1800000 # reads from /dev/ttyS4 at 1800000 baud
```
If you need to change the baud rate you MUST give the ttyS[N] as first argument. Use the values you found with the dmesg command. You will then be asked for the Number of batteries. If ran w/o root, ignore the following messages and just hit enter.

This will create
1. a cronjob in "/etc/cron.d/power-status running every minute
2. copies the file "pwr-cron.sh" to "/sbin" executed by cron
3. copies the file "power-status.py" to "/usr/bin/" which will be executed by "pwr-cron.sh"

The "pwr-cron.sh" script will create the directories "/etc/fakedev/power_supply/BAT1" BAT2 (if 2 batteries)
and ADP1 (the AC power supply). This mimics "/sys/class/power_supply/" which cannot be created from user space.
Inside the fakedev directories the "power-status.py" python3 script will create the uevent files, where you
can point your battery monitor to (possible with i3status). Other DE's will need a workaround via i.e. gnome shell.
I cannot provide this. The entry in your i3status.conf is as follows
```
order += "battery all"

battery all { 
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
        path = "/etc/fakedev/power_supply/BAT%d/uevent"  <-------------
}
```
A solution for gnome like DEs can be found here: https://github.com/jakeday/linux-surface/issues/28#issuecomment-428876786 At this time it has a little glitch and won't work with only one battery. Work around this by creating a link:
```
sudo ln -s /etc/fakedev/power_supply/BAT1/uevent /etc/fakedev/power_supply/BAT2/uevent
```
It will then show 2 batteries.

The python script is originally from @qzed's proof of concept and can be found here: https://gist.github.com/qzed/01a93568efb863f1b7887f0f375c03fc I only modified it to fit the output to the uevent file format. I don't no anything about python so please bare with me.

The python script will create a file in "/tmp" named "surface-ec-counters.json".

Of course, there is no guarantee for anything. Use on your own risk.
