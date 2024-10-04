import serial
import asyncio
import time
from PyQt6 import uic
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

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
        return ser.readline().decode("utf-8")[:-1]
    ser.close()


# функция, которая ничего не делает
async def fun2():
    await asyncio.sleep(1)
    print("функция 2")
    return "2"


# функция, которая загружает интерфейс
async def fun3():
    await asyncio.sleep(1)
    print("функция 3")
    return "3"


# запускаем таски
async def main():
    task1 = asyncio.create_task(fun1())  # periodic(0.1, fun1)
    task2 = asyncio.create_task(fun2())
    task3 = asyncio.create_task(fun3())

    # эта функция срабатывает при нажатии кнопки
    def btn_clk():
        print("Button clicked")

        form.lcdNumber.display(form.lcdNumber.intValue() + 1)

    def ln_changed():
        print("Text changed")
        form.lcdNumber_2.display(2)

    def lbl3_add():
        form.label_3.setText(task1.result())

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)
    window.show()

    # настраиваем сценарий для элемента pushButton
    form.pushButton.clicked.connect(lbl3_add)
    form.lineEdit.textChanged.connect(ln_changed)

    await task1
    form.label_3.setText(task1.result())

    # запускаем окно программы
    app.exec()


asyncio.run(main())
