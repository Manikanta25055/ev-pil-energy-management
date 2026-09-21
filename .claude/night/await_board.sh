#!/usr/bin/env bash
# Wait for the board to come back, then resume the repeat campaign.
#
# The campaign stopped at 13/36 because the ESP32-S3 left the USB bus entirely.
# That needs a hand on a cable, and once that hand has been applied there is no
# reason the operator should also have to type a command. This watches for the
# part to reappear and starts the resume itself.
#
# It only ever resumes work the operator already asked for, it stops after
# twelve hours rather than waiting forever, and it refuses to start a second
# copy if one is already running.
set -u
cd "/Users/manikantagonugondla/Desktop/EV Drives Improvement"
DEADLINE=$(( $(date +%s) + 12*3600 ))

present() {
    ioreg -p IOUSB -l -w 0 2>/dev/null \
        | grep -qE '"USB Product Name" = "USB JTAG_serial debug unit"' \
        && ls /dev/cu.usbmodem* >/dev/null 2>&1
}

echo "waiting for the board; deadline $(date -r $DEADLINE '+%H:%M')"
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if present; then
        # Two consecutive sightings 20 s apart, so a half-seated cable that
        # enumerates and drops does not start a five-hour campaign.
        sleep 20
        if present; then
            echo "board is back at $(date '+%H:%M'); resuming the repeat campaign"
            if pgrep -f "repeat_campaign.sh" >/dev/null 2>&1; then
                echo "a repeat driver is already running; not starting a second"
                exit 0
            fi
            ./.claude/night/repeat_campaign.sh >> .claude/night/repeat.log 2>&1
            echo "resume finished with rc=$?"
            exit 0
        fi
    fi
    sleep 40
done
echo "BOARD DID NOT RETURN within twelve hours; nothing was resumed"
exit 1
