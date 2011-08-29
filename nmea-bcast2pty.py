#!/usr/bin/env python

import string
import select, socket 
import sys, os, time, signal, pty, termios # fcntl, array, struct
from operator import xor

class FakePTY():
    "A FakePTY is a pty with a test log ready to be cycled to it."
    def __init__(self, speed=4800, databits=8, parity='N', stopbits=1):
        # Allow Serial: header to be overridden by explicit spped.
        self.speed = speed
        baudrates = {
            0: termios.B0,
            50: termios.B50,
            75: termios.B75,
            110: termios.B110,
            134: termios.B134,
            150: termios.B150,
            200: termios.B200,
            300: termios.B300,
            600: termios.B600,
            1200: termios.B1200,
            1800: termios.B1800,
            2400: termios.B2400,
            4800: termios.B4800,
            9600: termios.B9600,
            19200: termios.B19200,
            38400: termios.B38400,
            57600: termios.B57600,
            115200: termios.B115200,
            230400: termios.B230400,
        }
        speed = baudrates[speed]	# Throw an error if the speed isn't legal
        (self.fd, self.slave_fd) = os.openpty()
        self.byname = os.ttyname(self.slave_fd)
        print os.ttyname(self.slave_fd), os.ttyname(self.fd)
        (iflag, oflag, cflag, lflag, ispeed, ospeed, cc) = termios.tcgetattr(self.slave_fd)
        cc[termios.VMIN] = 1
        cflag &= ~(termios.PARENB | termios.PARODD | termios.CRTSCTS)
        cflag |= termios.CREAD | termios.CLOCAL
        iflag = oflag = lflag = 0
        iflag &=~ (termios.PARMRK | termios.INPCK)
        cflag &=~ (termios.CSIZE | termios.CSTOPB | termios.PARENB | termios.PARODD)
        if databits == 7:
            cflag |= termios.CS7
        else:
            cflag |= termios.CS8
        if stopbits == 2:
            cflag |= termios.CSTOPB
        if parity == 'E':
            iflag |= termios.INPCK
            cflag |= termios.PARENB
        elif parity == 'O':
            iflag |= termios.INPCK
            cflag |= termios.PARENB | termios.PARODD
        ispeed = ospeed = speed
        termios.tcsetattr(self.slave_fd, termios.TCSANOW,
                          [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])
    def read(self):
        "Discard control strings written by gpsd."
        # A tcflush implementation works on Linux but fails on OpenBSD 4.
        termios.tcflush(self.fd, termios.TCIFLUSH)
        # Alas, the FIONREAD version also works on Linux and fails on OpenBSD.
        #try:
        #    buf = array.array('i', [0])
        #    fcntl.ioctl(self.master_fd, termios.FIONREAD, buf, True)
        #    n = struct.unpack('i', buf)[0]
        #    os.read(self.master_fd, n)
        #except IOError:
        #    pass

    def write(self, line):
        os.write(self.fd, line)

    def drain(self):
        "Wait for the associated device to drain (e.g. before closing)."
        termios.tcdrain(self.fd)

if __name__ == '__main__':
    nmeaPort = 9052  # where do you expect to get a msg?
    aisPort = 9060  # where do you expect to get a msg?
    # bufferSize = 1024 # whatever you need
    bufferSize = 4096 # whatever you need

    nmeaSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    nmeaSocket.bind(('<broadcast>', nmeaPort))
    nmeaSocket.setblocking(0)

    aisSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    aisSocket.bind(('<broadcast>', aisPort))
    aisSocket.setblocking(0)

    fake = FakePTY()

    while True:
        readResult, writeResult, errorResult = select.select([nmeaSocket, aisSocket],[],[])
        msgs = [];
        # print(len(readResult))
        for res in readResult:
            pkg = res.recv(bufferSize)
            # print pkg
            msgs.extend(pkg.split('\n'))

        for msg in msgs:
            msg = msg.replace('\r', '')
            if msg:
                # print msg

                # write original msg
                # fake.write(msg + '\n\r')

                # Hack number 2 - Add missing field "Radio Channel Code"
                if 0 <= msg.find('!AIVDM'):
                    # print res
                    msgFields = msg.split(',')
                    msgFields.insert(4, 'A')
                    msg = string.join(msgFields, ',')
                    # print res

                # Hack number 1 - Calculate correct checksum (without last symbol *)
                # rewrite checksumm
                msg1 = msg[1:msg.index('*')]
                nmea = map(ord, msg1)
                checksum = reduce(xor, nmea)
                oldchksm = msg[msg.index('*'):len(msg)]
                # if oldchksm != checksum: print "***"
                msg = msg[0]+msg1+"*"+hex(checksum)[2:4]+"\r\n"
                # print msg

                fake.write(msg)
