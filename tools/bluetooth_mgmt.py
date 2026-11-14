# SPDX-License-Identifier: MIT
"""Small synchronous client for Linux's stable Bluetooth MGMT control socket."""
import socket
import struct
import time


READ_INFO = 0x0004
READ_CONFIG_INFO = 0x0037
SET_PUBLIC_ADDRESS = 0x0039
PUBLIC_ADDRESS = 0x00000002


class Management:
    def __init__(self, deadline):
        self.deadline = deadline
        self.socket = socket.socket(socket.AF_BLUETOOTH,
                                    socket.SOCK_RAW | socket.SOCK_CLOEXEC, 1)
        try:
            self.socket.bind((0xffff, 3))  # HCI_DEV_NONE, HCI_CHANNEL_CONTROL
        except BaseException:
            self.socket.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.socket.close()

    def call(self, opcode, index, payload=b''):
        self.socket.send(struct.pack('<HHH', opcode, index, len(payload)) + payload)
        deadline = min(self.deadline, time.monotonic() + 7)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('Bluetooth MGMT reply timed out')
            self.socket.settimeout(remaining)
            packet = self.socket.recv(4096)
            if len(packet) < 6:
                raise RuntimeError('truncated Bluetooth MGMT event')
            event, reply_index, length = struct.unpack_from('<HHH', packet)
            if len(packet) != 6 + length:
                raise RuntimeError('invalid Bluetooth MGMT event length')
            if event not in (1, 2) or reply_index != index:
                continue
            if length < 3:
                raise RuntimeError('truncated Bluetooth MGMT command reply')
            reply_opcode, status = struct.unpack_from('<HB', packet, 6)
            if reply_opcode == opcode:
                return status, packet[9:]

    def info(self, index):
        status, data = self.call(READ_INFO, index)
        if status:
            return None
        if len(data) < 17:
            raise RuntimeError('truncated Bluetooth controller information')
        return ':'.join(f'{b:02x}' for b in data[:6][::-1])

    def missing_options(self, index):
        status, data = self.call(READ_CONFIG_INFO, index)
        if status:
            return None
        if len(data) != 10:
            raise RuntimeError('invalid Bluetooth configuration information')
        return struct.unpack_from('<I', data, 6)[0]

    def set_address(self, index, address):
        status, _ = self.call(SET_PUBLIC_ADDRESS, index,
                              bytes.fromhex(address.replace(':', ''))[::-1])
        if status:
            raise RuntimeError(f'controller rejected factory address (MGMT status 0x{status:02x})')
