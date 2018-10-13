#!/usr/bin/env python3

import json
import pprint
import crcmod

from argparse import ArgumentParser

from pathlib import Path

import serial
from serial import Serial


DEFAULT_DEVICE = '/dev/ttyS0'
DEFAULT_BAUD_RATE = 3000000
CRC_FN = crcmod.predefined.mkCrcFun('crc-ccitt-false')


def setup_device(port, baudrate):
    # definition from DSDT
    return Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        rtscts=False,
        dsrdtr=False,
        timeout=0,
    )


def crc(pld):
    x = CRC_FN(bytes(pld))
    return [x & 0xff, (x >> 0x08) & 0xff]


def to_int(bytes):
    return int.from_bytes(bytes, byteorder='little')


class Counters:
    PATH = Path(__file__).parent / '.counters.json'

    @staticmethod
    def load():
        if Counters.PATH.is_file():
            with open(Counters.PATH) as fd:
                data = json.load(fd)
                seq = data['seq']
                cnt = data['cnt']
        else:
            seq = 0x00
            cnt = 0x0000

        return Counters(seq, cnt)

    def __init__(self, seq, cnt):
        self.seq = seq
        self.cnt = cnt

    def store(self):
        with open(Counters.PATH, 'w') as fd:
            data = {'seq': self.seq, 'cnt': self.cnt}
            json.dump(data, fd)

    def inc_seq(self):
        self.seq = (self.seq + 1) & 0xFF

    def inc_cnt(self):
        self.cnt = (self.cnt + 1) & 0xFFFF

    def inc(self):
        self.inc_seq()
        self.inc_cnt()


class Command:
    def __init__(self, rtc, riid, rcid):
        self.rtc = rtc
        self.riid = riid
        self.rcid = rcid

    def _write_msg(self, dev, seq, cnt):
        cnt_lo = cnt & 0xff
        cnt_hi = (cnt >> 0x08) & 0xff

        hdr = [0x80, 0x08, 0x00, seq]
        pld = [0x80, self.rtc, 0x01, 0x00, self.riid, cnt_lo, cnt_hi, self.rcid]
        msg = [0xaa, 0x55] + hdr + crc(hdr) + pld + crc(pld)

        return dev.write(bytes(msg))

    def _write_ack(self, dev, seq):
        hdr = [0x40, 0x00, 0x00, seq]
        msg = [0xaa, 0x55] + hdr + crc(hdr) + [0xff, 0xff]

        return dev.write(bytes(msg))

    def _read_ack(self, dev, exp_seq):
        msg = bytes()
        while len(msg) < 0x0A:
            msg += dev.read(0x0A - len(msg))

        # print("received: {}".format(msg.hex()))

        assert msg[0:2] == bytes([0xaa, 0x55])
        assert msg[3:5] == bytes([0x00, 0x00])
        assert msg[6:8] == bytes(crc(msg[2:-4]))
        assert msg[8:] == bytes([0xff, 0xff])

        mty = msg[2]
        seq = msg[5]

        if mty == 0x40:
            assert seq == exp_seq

        return mty == 0x04

    def _read_msg(self, dev, cnt):
        cnt_lo = cnt & 0xff
        cnt_hi = (cnt >> 0x08) & 0xff

        buf = bytes()
        rem = 0x08                          # begin with header length
        while len(buf) < rem:
            buf += dev.read(0x0400)

            # if we got a header, validate it
            if rem == 0x08 and len(buf) >= 0x08:
                hdr = buf[0:8]

                assert hdr[0:3] == bytes([0xaa, 0x55, 0x80])
                assert hdr[-2:] == bytes(crc(hdr[2:-2]))

                rem += hdr[3] + 10          # len(payload) + frame + crc

        hdr = buf[0:8]
        msg = buf[8:hdr[3]+10]
        rem = buf[hdr[3]+10:]

        # print("received: {}".format(hdr.hex()))
        # print("received: {}".format(msg.hex()))

        assert msg[0:8] == bytes([0x80, self.rtc, 0x00, 0x01, self.riid, cnt_lo, cnt_hi, self.rcid])
        assert msg[-2:] == bytes(crc(msg[:-2]))

        seq = hdr[5]
        pld = msg[8:-2]

        return seq, pld, rem

    def _read_clean(self, dev, buf=bytes()):
        buf += dev.read(0x0400)                     # make sure we're not missing some bytes

        while buf:
            # get header / detect message type
            if len(buf) >= 0x08:
                if buf[0:3] == bytes([0xaa, 0x55, 0x40]):               # ACK
                    while len(buf) < 0x0A:
                        buf += dev.read(0x0400)

                    # print("ignored ACK: {}".format(buf[:0x0a].hex()))
                    buf = bytes(buf[0x0a:])

                elif buf[0:3] == bytes([0xaa, 0x55, 0x80]):             # response
                    buflen = 0x0a + buf[3]
                    while len(buf) < buflen:
                        buf += dev.read(0x0400)

                    # print("ignored MSG: {}".format(buf[:buflen].hex()))
                    buf = bytes(buf[buflen:])

                elif buf[0:3] == bytes([0x4e, 0x00, 0x53]):             # control message?
                    while len(buf) < 0x19:
                        buf += dev.read(0x0400)

                    # print("ignored CTRL: {}".format(buf[:0x19].hex()))
                    buf = bytes(buf[0x19:])

                else:                                                   # unknown
                    # print("ignored unknown: {}".format(buf.hex()))
                    assert False

            buf += dev.read(0x0400)

    def run(self, dev, cnt):
        self._read_clean(dev)
        self._write_msg(dev, cnt.seq, cnt.cnt)
        retry = self._read_ack(dev, cnt.seq)

        # retry one time on com failure
        if retry:
            self._write_msg(dev, cnt.seq, cnt.cnt)
            retry = self._read_ack(dev, cnt.seq)

            if retry:
                # print('Communication failure: invalid ACK, try again')
                return

        try:
            seq, pld, rem = self._read_msg(dev, cnt.cnt)
            self._write_ack(dev, seq)
            self._read_clean(dev, rem)
        finally:
            cnt.inc()

        return self._handle_payload(pld)

    def _handle_payload(self, pld):
        return None


class Gbos(Command):
    def __init__(self):
        super().__init__(0x11, 0x00, 0x0d)

    def _handle_payload(self, pld):
        return {
            'Base Status': hex(pld[0]),
        }


class Psr(Command):
    def __init__(self, bat):
        super().__init__(0x02, bat, 0x0d)

    def _handle_payload(self, pld):
        pwr_state = to_int(pld[0:3])
        print("POWER_SUPPLY_ONLINE={}".format(pwr_state))
        return {
            'Power Source': hex(to_int(pld[0:3])),
        }


class Sta(Command):
    def __init__(self, bat):
        super().__init__(0x02, bat, 0x01)

    def _handle_payload(self, pld):
        # print("payload: {}".format(pld.hex()))
        return {
            'Battery Status': hex(to_int(pld[0:3])),
        }


class Bst(Command):
    def __init__(self, bat):
        super().__init__(0x02, bat, 0x03)

    def _handle_payload(self, pld):
        # print("payload: {}".format(pld.hex()))
        return {
            'State': hex(to_int(pld[0:3])),
            'Present Rate': hex(to_int(pld[4:7])),
            'Remaining Capacity': hex(to_int(pld[8:11])),
            'Present Voltage': hex(to_int(pld[12:15])),
        }


class Bix(Command):
    def __init__(self, bat):
        super().__init__(0x02, bat, 0x02)

    def _handle_payload(self, pld):
        # print("payload: {}".format(pld.hex()))
        return {
            'Revision': hex(pld[0]),
            'Power Unit': hex(to_int(pld[1:4])),
            'Design Capacity': hex(to_int(pld[5:8])),
            'Last Full Charge Capacity': hex(to_int(pld[9:12])),
            'Bat Present': hex(to_int(pld[13:16])),
            'Design Voltage': hex(to_int(pld[17:20])),
            'Design Capacity of Warning': hex(to_int(pld[21:24])),
            'Design Capacity of Low': hex(to_int(pld[25:28])),
            'Cycle Count': hex(to_int(pld[29:32])),
            'Measurement Accuracy': hex(to_int(pld[33:36])),
            'Max Sampling Time': hex(to_int(pld[37:40])),
            'Min Sampling Time': hex(to_int(pld[41:44])),
            'Max Averaging Interval': hex(to_int(pld[45:48])),
            'Min Averaging Interval': hex(to_int(pld[49:52])),
            'Capacity Granularity 1': hex(to_int(pld[53:56])),
            'Capacity Granularity 2': hex(to_int(pld[57:60])),
            'Model Number': pld[61:81].decode().rstrip('\0'),
            'Serial Number': pld[82:92].decode().rstrip('\0'),
            'Technology': pld[93:97].decode().rstrip('\0'),
            'Manufacturer': pld[98:118].decode().rstrip('\0'),
        }

class UeventBat:
    def __init__(self, bat):
        self.bix = Bix(bat)
        self.bst = Bst(bat)

    def run(self, dev, cnt):
        bix = self.bix.run(dev, cnt)
        bst = self.bst.run(dev, cnt)

        state = int(bst['State'], 0)
        bat_present = int(bix['Bat Present'], 0)
        technology = bix['Technology']
        cycles = int(bix['Cycle Count'], 0)
        vol_design = int(bix['Design Voltage'], 0)
        vol = int(bst['Present Voltage'], 0)
        rate = int(bst['Present Rate'], 0)
        cap_design = int(bix['Design Capacity'], 0)
        full_cap = int(bix['Last Full Charge Capacity'], 0)
        low_cap = int(bix['Design Capacity of Low'], 0)
        rem_cap = int(bst['Remaining Capacity'], 0)
        model = bix['Model Number']
        serial = bix['Serial Number']
        manufacturer = bix['Manufacturer']
        if full_cap <= 0:
            rem_perc = 0
        else:
            rem_perc = int(rem_cap / full_cap * 100)

        bat_states = {
            0: 'None',
            1: 'Discharging',
            2: 'Charging',
            4: 'Critical',
            5: 'Critical (Discharging)',
            6: 'Critical (Charging)',
        }

        bat_state = bat_states[state]

        print("POWER_SUPPLY_STATUS={}".format(bat_state))
        print("POWER_SUPPLY_PRESENT={}".format(bat_present))
        print("POWER_SUPPLY_TECHNOLOGY={}".format(technology))
        print("POWER_SUPPLY_CYCLE_COUNT={}".format(cycles))
        print("POWER_SUPPLY_VOLTAGE_MIN_DESIGN={}".format(vol_design))
        print("POWER_SUPPLY_VOLTAGE_NOW={}".format(vol))
        print("POWER_SUPPLY_POWER_NOW={}".format(rate))
        print("POWER_SUPPLY_ENERGY_FULL_DESIGN={}".format(cap_design))
        print("POWER_SUPPLY_ENERGY_FULL={}".format(full_cap))
        print("POWER_SUPPLY_ENERGY_NOW={}".format(rem_cap))
        print("POWER_SUPPLY_ENERGY_LOW={}".format(low_cap))
        print("POWER_SUPPLY_CAPACITY={}".format(rem_perc))
        print("POWER_SUPPLY_MODEL_NAME={}".format(model))
        print("POWER_SUPPLY_MANUFACTURER={}".format(manufacturer))
        print("POWER_SUPPLY_SERIAL_NUMBER={}".format(serial))
        
class PrettyBat:
    def __init__(self, bat):
        self.bix = Bix(bat)
        self.bst = Bst(bat)

    def run(self, dev, cnt):
        bix = self.bix.run(dev, cnt)
        bst = self.bst.run(dev, cnt)

        state = int(bst['State'], 0)
        vol = int(bst['Present Voltage'], 0)
        rem_cap = int(bst['Remaining Capacity'], 0)
        full_cap = int(bix['Last Full Charge Capacity'], 0)
        rate = int(bst['Present Rate'], 0)

        bat_states = {
            0: 'None',
            1: 'Discharging',
            2: 'Charging',
            4: 'Critical',
            5: 'Critical (Discharging)',
            6: 'Critical (Charging)',
        }

        bat_state = bat_states[state]
        bat_vol = vol / 1000

        if full_cap <= 0:
            bat_rem_perc = '<unavailable>'
        else:
            bat_rem_perc = "{}%".format(int(rem_cap / full_cap * 100))

        if state == 0x00 or rate == 0:
            bat_rem_life = '<unavailable>'
        else:
            bat_rem_life = "{:.2f}h".format(rem_cap / rate)
        
        bname="dev"
        return {
            'State': bat_state,
            'Voltage': "{}V".format(bat_vol),
            'Percentage': bat_rem_perc,
            'Remaining ': bat_rem_life,
        }


COMMANDS = {
    'lid0.gbos': Gbos(),
    'adp1._psr': Psr(0x01),
    'bat1._sta': Sta(0x01),
    'bat1._bst': Bst(0x01),
    'bat1._bix': Bix(0x01),
    'bat2._sta': Sta(0x02),
    'bat2._bst': Bst(0x02),
    'bat2._bix': Bix(0x02),

    'bat1.pretty': PrettyBat(0x01),
    'bat2.pretty': PrettyBat(0x02),
    'adp1.uevent': Psr(0x01),
    'bat1.uevent': UeventBat(0x01),
    'bat2.uevent': UeventBat(0x02),
}


def main():
    cli = ArgumentParser(description='Surface Book 2 / Surface Pro (2017) embedded controller requests.')
    cli.add_argument('-d', '--device', default=DEFAULT_DEVICE, metavar='DEV', help='the UART device')
    cli.add_argument('-b', '--baud', default=DEFAULT_BAUD_RATE, type=lambda x: int(x, 0), metavar='BAUD', help='the baud rate')
    cli.add_argument('-c', '--cnt', type=lambda x: int(x, 0), help='overwrite CNT')
    cli.add_argument('-s', '--seq', type=lambda x: int(x, 0), help='overwrite SEQ')
    commands = cli.add_subparsers()

    for cmd in COMMANDS.keys():
        parser = commands.add_parser(cmd, help="run request '{}'".format(cmd.upper()))
        parser.set_defaults(command=cmd)

    args = cli.parse_args()

    dev = setup_device(args.device, args.baud)
    cmd = COMMANDS.get(args.command)

    cnt = Counters.load()
    if args.seq is not None:
        cnt.seq = args.seq
    if args.cnt is not None:
        cnt.cnt = args.cnt

    try:
        res = cmd.run(dev, cnt)
        pwr_supply_name = args.command.upper()
        print("POWER_SUPPLY_NAME={}".format(pwr_supply_name.split('.')[0]))

        # print()
        # pprint.pprint(res)

    finally:
        cnt.store()


if __name__ == '__main__':
    main()
