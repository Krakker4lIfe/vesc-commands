"""
This file is a sending/receiving script to the VESC 6

"""
import serial, time, numpy
from packets import Packet
import packets

CURRENT_CONTROL_ACCURACY = 1e3
DUTY_CONTROL_ACCURACY = 1e5
TEMP_ACCURACY = 1e1
NO_SCALE = 1
CURRENT_CONTROL_ID = 6
DUTY_CONTROL_ID = 5
ALIVE_ID = 30
REBOOT_ID = 29
GET_VALUES_ID = 4


def process_buffer(buffer):
    """
    This function processes the given buffer (bytearray). When a packet is received, the function calls the process_packet fucntion
    :param buffer: The given bytearray to proces
    :return: None
    """
    global phase, payload, length, crc
    """
    This is an integer that indicates the state the message reading is in.
    0: Starting a package read
    1: Reading payload length - long version
    2: Reading payload length - both versions
    3: Reading payload
    4: Reading CRC checksum - first byte
    5: Reading CRC checksum - second byte
    6: Checking checksum
    """

    for x in range(len(buffer)):

        curr_byte = buffer[x]
        if phase == 0:
            payload = bytearray()
            length = 0
            crc = 0
            if curr_byte == 2:
                phase += 2
            elif curr_byte == 3:
                phase += 1
        elif phase == 1:
            length = curr_byte << 8
            phase += 1
        elif phase == 2:
            length |= curr_byte
            phase += 1
        elif phase == 3:
            payload.append(curr_byte)
            if len(payload) == length:
                phase += 1
        elif phase == 4:
            crc = curr_byte << 8
            phase += 1
        elif phase == 5:
            crc |= curr_byte
            phase += 1
        elif phase == 6:
            phase = 0
            if curr_byte == 3 and packets.calc_crc(payload) == crc:
                process_packet(Packet(payload))
                return True
        else:
            phase = 0


def process_packet(packet):
    if packet.get_next_number(8, NO_SCALE, True) == GET_VALUES_ID:
        packet.index += 22
        data[counter].append(packet.get_next_number(32, 1))


def print_values(packet):
    if packet.get_next_number(8, NO_SCALE, True) == GET_VALUES_ID:
        print("Temperature mosfet[°C]: " + str(packet.get_next_number(16, TEMP_ACCURACY)))
        print("Temperature motor[°C] : " + str(packet.get_next_number(16, TEMP_ACCURACY)))
        print("Current motor[A]: " + str(packet.get_next_number(32, 100)))
        print("Current VESC[A]: " + str(packet.get_next_number(32, 100)))
        print("D axis current[A]: " + str(packet.get_next_number(32, 100)))
        print("Q axis current[A]: " + str(packet.get_next_number(32, 100)))
        print("Duty[%]: " + str(packet.get_next_number(16, 1000)))
        print("ERPM[RPM]: " + str(packet.get_next_number(32, 1)))
        print("Voltage VESC[V]: " + str(packet.get_next_number(16, 10)))
        print("Drawn charge[mAh]: " + str(packet.get_next_number(32, 10000)))
        print("Charged charge[mAh]: " + str(packet.get_next_number(32, 10000)))
        print("Drawn power[Wh]: " + str(packet.get_next_number(32, 10000)))
        print("Charged power[Wh]: " + str(packet.get_next_number(32, 10000)))
        print("The Tachometer value = number of revolutions*3*#motor poles")
        print("Tachometer value[motor steps]: " + str(packet.get_next_number(32, 1)))
        print("Tachometer absolute value[motor steps]: " + str(packet.get_next_number(32, 1)))
        print("Fault code: " + str(packet.get_next_number(8, 1)))


def get_duty_for_counter(counter):
    return min(0.05 * counter, 0.95)


phase = 0
payload = bytearray()
length = 0
crc = 0
vesc_usb = serial.Serial('COM3', 38400, timeout=0.1)
time.sleep(1)  # give the connection a second to settle

current_control = Packet(8, CURRENT_CONTROL_ID, NO_SCALE, 32, 0.3, CURRENT_CONTROL_ACCURACY)
current_control_high = Packet(8, CURRENT_CONTROL_ID, NO_SCALE, 32, 0.5, CURRENT_CONTROL_ACCURACY)
duty_control = Packet(8, DUTY_CONTROL_ID, NO_SCALE, 32, 0.1, DUTY_CONTROL_ACCURACY)
alive = Packet(8, ALIVE_ID, NO_SCALE)
reboot = Packet(8, REBOOT_ID, NO_SCALE)
stop = Packet(8, 6, 1, 32, 0, CURRENT_CONTROL_ACCURACY)
get_rt_data = Packet(8, GET_VALUES_ID, NO_SCALE)

get_rt_data.send(vesc_usb)
data = [[] for x in range(20)]
counter = 0
data_counter = 0
wait_until = time.time() + 1
data_req_sent = False
while True:
    alive.send(vesc_usb)
    if process_buffer(vesc_usb.read(10)):
        data_counter += 1
        data_req_sent = False
        if data_counter > 10:
            counter += 1
            data_counter = 0
            Packet(8, DUTY_CONTROL_ID, NO_SCALE, 32, get_duty_for_counter(counter), DUTY_CONTROL_ACCURACY).send(vesc_usb)
            time.sleep(0.3)
            alive.send(vesc_usb)
            time.sleep(0.3)
        get_rt_data.send(vesc_usb)
    if counter > 19:
        break
stop.send(vesc_usb)
text_file = open("Output.txt", "w")
print(data)
text_file.writelines("%s\n" % numpy.average(item) for item in data)
text_file.close()
