import sys
import serial
import time
import struct
import string
import msvcrt

EDM_START = '\xAA'
EDM_STOP = '\x55'

CONNECT_EVENT = '\x00\x11'
DISCONNECT_EVENT = '\x00\x21'
DATA_EVENT = '\x00\x31'
DATA_COMMAND = '\x00\x36'
AT_EVENT = '\x00\x41'
AT_REQUEST = '\x00\x44'
AT_CONFIRMATION = '\x00\x45'
RESEND_CONNECT_EVENT_COMMAND = '\x00\x56'
IPHONE_EVENT = '\x00\x61'
START_EVENT = '\x00\x71'

BLUETOOTH = '\x01'
IPv4 = '\x02'
IPv6 = '\x03'

SPP = '\x00'
DUN = '\x01'
SPS = '\x0E'


def consume_keypress():
    while msvcrt.kbhit():
        msvcrt.getch()


def send_at_command(com, cmd):
    # Send at command
    com.write(cmd + '\r')
    com.flush()

    # Search the response for the sent at command to be sure
    # that it has been sent before we proceed
    r = com.read()
    while string.find(r, cmd) < 0:
        r = r + com.read()

    # Read response until OK or ERROR received
    while r.find('OK') < 0 and r.find('ERROR') < 0:
        r = r + com.read()

    if r.find('ERROR') > 0:
        print ('ERROR: {}'.format(cmd))
        sys.exit()
    return r


def wait_for_startup(com):
    # Read response until +STARTUP received
    r = com.read()
    while r.find('+STARTUP') < 0:
        r = r + com.read()
    return r


def check_for_incoming_edm_packet(com):
    # Read response until EDM_START received
    r = ''
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
        print 'in: ',
        print (':'.join(x.encode('hex') for x in (EDM_START + payload_length + payload + stop_byte)))
        payload_id_type = payload[:2]
        payload_data = payload[2:]

        if payload_id_type == AT_CONFIRMATION:
            print 'AT response: ' + payload_data

        elif payload_id_type == AT_EVENT:
            print 'AT event: ' + payload_data

        elif payload_id_type == CONNECT_EVENT:
            channel_id = struct.unpack('>B', payload_data[0])[0]
            connect_type = payload_data[1]
            if connect_type == BLUETOOTH:
                bt_profile = payload_data[2]
                if bt_profile == SPS:
                    bd_address = payload_data[3:9]
                    frame_size = payload_data[9:]
                    print 'Connect event Bluetooth SPS:'
                    print 'Channel id: ' + str(channel_id)
                    print 'BD Address: ' + (':'.join(x.encode('hex') for x in bd_address))
                    print 'Frame size: ' + (':'.join(x.encode('hex') for x in frame_size)) + '\n'
                else:
                    print 'Packet type not implemented'
            else:
                print 'Packet type not implemented'

        elif payload_id_type == DISCONNECT_EVENT:
            channel_id = struct.unpack('>B', payload_data[0])[0]
            print 'Disconnect event:'
            print 'Channel id: ' + str(channel_id) + '\n'

        elif payload_id_type == DATA_EVENT:
            channel_id = struct.unpack('>B', payload_data[0])[0]
            data = payload_data[1:]
            print 'Data event:'
            print 'Channel id: ' + str(channel_id)
            print 'Data: ' + data + '\n'

        elif payload_id_type == START_EVENT:
            print 'Start event' + '\n'

        else:
            print 'Packet type not implemented'

    else:
        print 'Invalid packet'


def send_edm_packet(com, payload):
    payload_length = struct.pack('>H', len(payload))
    packet = EDM_START + payload_length + payload + EDM_STOP
    print 'out: ',
    print (':'.join(x.encode('hex') for x in packet)) + '\n'
    com.write(packet)


def generate_edm_at_request_payload(at_command):
    payload_id_type = AT_REQUEST
    payload = payload_id_type + at_command
    return payload


def generate_edm_data_payload(ch, data):
    payload_id_type = DATA_COMMAND
    channel_byte = struct.pack('>B', ch)
    payload = payload_id_type + channel_byte + data
    return payload


def generate_edm_resend_connect_events_payload():
    payload_id_type = RESEND_CONNECT_EVENT_COMMAND
    payload = payload_id_type
    return payload


def menu(com):
    print '\n'
    print '1) Data Command'
    print '2) AT Request'
    print '3) Resend Connect Events'
    print '4) Connect to SPS remote peer'
    print '>',
    option = raw_input()
    consume_keypress()

    if '1' in option:
        print 'EDM channel id: ',
        channel = raw_input()
        consume_keypress()
        print 'Data: ',
        data = raw_input()
        consume_keypress()
        packet_payload = generate_edm_data_payload(int(channel), data)
        send_edm_packet(com, packet_payload)

    elif '2' in option:
        print 'AT command: ',
        at_command = raw_input()
        consume_keypress()
        packet_payload = generate_edm_at_request_payload((at_command + '\r'))
        send_edm_packet(com, packet_payload)

    elif '3' in option:
        packet_payload = generate_edm_resend_connect_events_payload()
        send_edm_packet(com, packet_payload)

    elif '4' in option:
        print 'BT address (remember r or p): ',
        bd_address = raw_input()
        consume_keypress()
        at_command = 'AT+UDCP=sps://' + bd_address + '/\r'
        packet_payload = generate_edm_at_request_payload(at_command)
        send_edm_packet(com, packet_payload)


def main(argv):
    # Open COMx at 115200 8-N-1, read timeout set to 1s
    comport = 'COM' + sys.argv[1]
    ser = serial.Serial(port=comport, baudrate=115200, rtscts=False, timeout=1)
    print(ser.name + ' open')
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    # Check if cts signal is True (device ready to receive data), if not
    # it is assumed that flow control is not supported. For example
    # EVK-ODIN-W2 does not support flow control, EVK-NINA-B1 and EVK-W262U
    # support flow control.
    print 'Checking flow control support...',
    flow_control_supported = False
    start = time.time()
    while not flow_control_supported:
        flow_control_supported = ser.cts
        time.sleep(1)
        if (time.time() - start) > 5:
            break
    print 'done.'

    if flow_control_supported:
        ser.rtscts = True
        # Reset the DUT to factory defaults
        print send_at_command(ser, 'AT+UFACTORY')
        print send_at_command(ser, 'AT+CPWROFF')
        print wait_for_startup(ser)

    else:
        # Reset the DUT to factory defaults
        print send_at_command(ser, 'AT+UFACTORY')
        print send_at_command(ser, 'AT+UMRS=115200,2,8,1,1,0')
        print send_at_command(ser, 'AT&W')
        print send_at_command(ser, 'AT+CPWROFF')
        print wait_for_startup(ser)

    # Set Central role
    if sys.argv[2] == 'central':
        print send_at_command(ser, 'AT+UBTLE=1')
        print send_at_command(ser, 'AT&W')
        print send_at_command(ser, 'AT+CPWROFF')
        print wait_for_startup(ser)

        # Set maximum number of links to 7
        print send_at_command(ser, 'AT+UBTCFG=2,7')
        print send_at_command(ser, 'AT&W')
        print send_at_command(ser, 'AT+CPWROFF')
        print wait_for_startup(ser)

    # Enter Extended Data Mode
    print send_at_command(ser, 'ATO2')
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
