#!/bin/bash
TTY=ttyS0
if [ ! -z $1 ]
then
    case $1 in
        ttyS0);;
        ttyS4) TTY=$1;;
        *) ;;
    esac
fi
FAKEDEV_FILES=("/sbin/pwr-cron.sh" "/usr/bin/power-status.py" "/etc/cron.d/power-status")
echo "Setting up fakedevices for Battery status"
echo "This will create devices in /etc/fakedev"
echo -n "How many batteries are in this device? [1|2]: "
read NOB
case $NOB in
    1) sed 's/\[MARK\]/# /' < pwr-cron.template > pwr-cron.sh;;
    2) sed 's/\[MARK\]//' < pwr-cron.template > pwr-cron.sh;;
    *) echo "Not supported - exiting"
       exit 1
    ;;
esac
chmod 744 pwr-cron.sh
sed 's/\[MARK\]/'$TTY'/' < power-status.template > power-status.py
for file in ${FAKEDEV_FILES[*]}
do
    if [ -f $file ]
    then
        echo -n "file $file exists. Overwrite ? [Yes|no]: "
        read choice
        case $choice in
            n|N|no|NO|No) continue;;
            *) ;;
        esac
    fi
    echo "copying" `basename $file` `dirname $file`/
    cp `basename $file` `dirname $file`/
    stat=$?
    [ $stat -ne 0 ] && echo "failed" || echo "success"
done
