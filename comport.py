import serial
import time


async def portStringArduino():
    ser = serial.Serial()
    ser.baudrate = 9600
    ser.port = "COM6"
    ser.open()
    time.sleep(2)
    ser.write(b"1")
    time.sleep(0.1)
    while ser.in_waiting:
        return print(ser.readline().decode("utf-8")[:-1])
    ser.close()
