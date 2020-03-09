import sys
import serial
import time
import struct
import string
import msvcrt

EDM_START = b'\xAA'
EDM_STOP = b'\x55'
CONNECT_EVENT = b'\x00\x11'
DISCONNECT_EVENT = b'\x00\x21'
DATA_EVENT = b'\x00\x31'
DATA_COMMAND = b'\x00\x36'
AT_EVENT = b'\x00\x41'
AT_REQUEST = b'\x00\x44'
AT_CONFIRMATION = b'\x00\x45'
RESEND_CONNECT_EVENT_COMMAND = b'\x00\x56'
IPHONE_EVENT = b'\x00\x61'
START_EVENT = b'\x00\x71'

BLUETOOTH = 1
IPv4 = 2
IPv6 = 3

SPP = 0
DUN = 1
SPS = 14


def consume_keypress():
    while msvcrt.kbhit():
        msvcrt.getch()

def send_at_command(com, cmd):
    # Send at command
    com.write(cmd.encode() + b'\r')
    com.flush()

    # Search the response for the sent at command to be sure
    # that it has been sent before we proceed
    r = com.read()

    while str.find(r.decode(), cmd) < 0:
        r = r + com.read()

    # Read response until OK or ERROR received
    while r.find(b'OK') < 0 and r.find(b'ERROR') < 0:
        r = r + com.read()

    if r.find(b'ERROR') > 0:
        print(('ERROR: {}'.format(cmd)))
        sys.exit()

    return r

def wait_for_startup(com):
    # Read response until +STARTUP received
    r = com.read()

    while r.find(b'+STARTUP') < 0:
        r = r + com.read()

    return r

def check_for_incoming_edm_packet(com):
    # Read response until EDM_START received
    r = b''
    while r.find(EDM_START) < 0:
        ch = com.read()
        if not ch:
            return
        r = r + ch

    # Read the EDM packet
    payload_length = com.read(2)
    length_int = struct.unpack('>H', payload_length)[0]
    payload = com.read(length_int)
    stop_byte = com.read(1)

    if stop_byte == EDM_STOP:
        print('in: ', end=' ')
        for x in (EDM_START + payload_length + payload + stop_byte):
            print(':'  + hex(x)[2:].zfill(2), end='')
        payload_id_type = payload[:2]
        payload_data = payload[2:]
        print('')

        if payload_id_type == AT_CONFIRMATION:
            print('AT response: ' + str(payload_data))

        elif payload_id_type == AT_EVENT:
            print('AT event: ' + str(payload_data))

        elif payload_id_type == CONNECT_EVENT:
            g_channel_id = payload_data[0]
            connect_type = payload_data[1]
            if connect_type == BLUETOOTH:
                bt_profile = payload_data[2]
                if bt_profile == SPS:
                    bd_address = payload_data[3:9]
                    frame_size = payload_data[9:]
                    print('Connect event Bluetooth SPS:')
                    print ('Channel id: ' + str(g_channel_id))
                    print ('BD Address: ', end='')
                    for x in (bd_address):
                        print(hex(x)[2:].zfill(2) + ':', end = '')
                    print('\n')
                    print ('Frame size: ', end='')
                    for x in frame_size:
                        print(hex(x)[2:].zfill(2) + ':', end = '')
                    print('\n')
                else:
                    print('Packet type not implemented')

            else:
                print('Packet type not implemented')

        elif payload_id_type == DISCONNECT_EVENT:
            channel_id = payload_data[0]
            print('Disconnect event:')
            print('Channel id: ' + str(channel_id) + '\n')

        elif payload_id_type == DATA_EVENT:
            channel_id = payload_data[0]
            data = payload_data[1:]
            print('Data event:')
            print('Channel id: ' + str(channel_id))
            print('Data: ' + str(data) + '\n')

        elif payload_id_type == START_EVENT:
            print('Start event' + '\n')

        else:
            print('Packet type not implemented')

    else:
        print('Invalid packet')

    sys.stdout.flush()


def send_edm_packet(com, payload):
    payload_length = struct.pack('>H', len(payload))
    packet = EDM_START + payload_length + payload + EDM_STOP
    print ('out: ', end='')
    print (payload)
    for x in packet:
        print (hex(x)[2:].zfill(2) + ':', end = '')
    print('\n')
    com.write(packet)

def generate_edm_at_request_payload(at_command):
    payload_id_type = AT_REQUEST
    payload = payload_id_type + at_command.encode()
    return payload

def generate_edm_data_payload(ch, data):
    payload_id_type = DATA_COMMAND
    channel_byte = struct.pack('>B', ch)
    payload = payload_id_type + channel_byte + data.encode()
    return payload

def generate_edm_resend_connect_events_payload():
    payload_id_type = RESEND_CONNECT_EVENT_COMMAND
    payload = payload_id_type
    return payload

def menu(com):
    print('\n')
    print('1) Data Command')
    print('2) AT Request')
    print('3) Resend Connect Events')
    print('4) Connect to SPS remote peer')
    print('>', end=' ')
    option = input()
    consume_keypress()

    if '1' in option:
        print('EDM channel id: ', end=' ')
        channel = input()
        consume_keypress()
        print('Data: ', end=' ')
        data = input()
        consume_keypress()
        packet_payload = generate_edm_data_payload(int(channel), data)
        send_edm_packet(com, packet_payload)

    elif '2' in option:
        print('AT command: ', end=' ')
        at_command = input()
        consume_keypress()
        packet_payload = generate_edm_at_request_payload((at_command + '\r'))
        send_edm_packet(com, packet_payload)

    elif '3' in option:
        packet_payload = generate_edm_resend_connect_events_payload()
        send_edm_packet(com, packet_payload)

    elif '4' in option:
        print('BT address (remember r or p): ', end=' ')
        bd_address = input()
        consume_keypress()
        at_command = 'AT+UDCP=sps://' + bd_address + '/\r'
        packet_payload = generate_edm_at_request_payload(at_command)
        send_edm_packet(com, packet_payload)

    sys.stdout.flush()


def main(argv):
    # Open COMx at 115200 8-N-1, read timeout set to 1s
    comport = 'COM' + sys.argv[1]
    ser = serial.Serial(port=comport, baudrate=115200, rtscts=False, timeout=1)
    print((ser.name + ' open'))
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Check if cts signal is True (device ready to receive data), if not
    # it is assumed that flow control is not supported. For example
    # EVK-ODIN-W2 does not support flow control, EVK-NINA-B1 and EVK-W262U
    # support flow control.
    print('Checking flow control support...', end=' ')
    flow_control_supported = False
    start = time.time()
    while not flow_control_supported:
        flow_control_supported = ser.cts
        time.sleep(1)
        if (time.time() - start) > 5:
            break
    print('done.')

    if flow_control_supported:
        ser.rtscts = True
        # Reset the DUT to factory defaults
        print(send_at_command(ser, 'AT+UFACTORY'))
        print(send_at_command(ser, 'AT+CPWROFF'))
        print(wait_for_startup(ser))

    else:
        # Reset the DUT to factory defaults
        print(send_at_command(ser, 'AT+UFACTORY'))
        print(send_at_command(ser, 'AT+UMRS=115200,2,8,1,1,0'))
        print(send_at_command(ser, 'AT&W'))
        print(send_at_command(ser, 'AT+CPWROFF'))
        print(wait_for_startup(ser))

    # Set Central role
    if sys.argv[2] == 'central':
        print(send_at_command(ser, 'AT+UBTLE=1'))
        print(send_at_command(ser, 'AT&W'))
        print(send_at_command(ser, 'AT+CPWROFF'))
        print(wait_for_startup(ser))

        # Set maximum number of links to 7
        print(send_at_command(ser, 'AT+UBTCFG=2,7'))
        print(send_at_command(ser, 'AT&W'))
        print(send_at_command(ser, 'AT+CPWROFF'))
        print(wait_for_startup(ser))

    # Enter Extended Data Mode
    print(send_at_command(ser, 'ATO2'))
    time.sleep(2)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Main loop
    while True:
        check_for_incoming_edm_packet(ser)
        x = msvcrt.kbhit()
        if x:
            consume_keypress()
            menu(ser)

if __name__ == '__main__':
    main(sys.argv)
