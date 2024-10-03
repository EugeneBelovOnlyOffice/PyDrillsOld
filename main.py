import serial
import asyncio
import time

# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = "COM6"
ser.open()
time.sleep(2)


# helper function for running a target periodically
async def periodic(interval_sec, coro_name, *args, **kwargs):
    # loop forever
    while True:
        # wait an interval
        await asyncio.sleep(interval_sec)
        # await the target
        await coro_name(*args, **kwargs)


# получаем строку сверел с порта Ардуино
async def fun1():
    time.sleep(0.5)
    ser.write(b"1")
    time.sleep(0.1)
    while ser.in_waiting:
        return print(ser.readline().decode("utf-8")[:-1])
    ser.close()


# функция, которая ничего не делает
async def fun2():
    print("функция 2")


# функция, которая ничего не делает
async def fun3():
    print("функция 3")


# запускаем таски
async def main():
    task1 = asyncio.create_task(periodic(0.1, fun1))
    task2 = asyncio.create_task(periodic(2, fun2))
    task3 = asyncio.create_task(periodic(1, fun3))

    await task1
    await task2
    await task3


print(time.strftime("%X"))
asyncio.run(main())
