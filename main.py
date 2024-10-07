import serial
import asyncio
import time
from PyQt6 import uic
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from PyQt6 import QtCore
import aioserial


# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = "COM6"
ser.open()
time.sleep(2)


# читаем порт асинхронно
async def read_and_print(aioserial_instance: aioserial.AioSerial):
    while True:
        print(
            (await aioserial_instance.read_async()).decode(errors="ignore"),
            end="",
            flush=True,
        )


# получаем строку сверел с порта Ардуино
async def fun1():
    await asyncio.sleep(1)
    print("функция 1")
    return "1"


async def fun2():
    await asyncio.sleep(1)
    print("функция 2")
    return "2"


# функция, которая ничего не делает
async def fun3():
    await asyncio.sleep(1)
    print("функция 3")
    return "3"


# запускаем таски
async def main():
    # эта функция срабатывает при нажатии кнопки
    def btn_clk():
        print("Button clicked")
        form.lcdNumber.display(form.lcdNumber.intValue() + 1)

    def ln_changed():
        print("Text changed")
        form.lcdNumber_2.display(2)

    def lbl3_add():
        ser.write(b"1")
        asyncio.sleep(0.1)
        while ser.in_waiting:
            form.label_3.setText(ser.readline().decode("utf-8")[:-1])

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)
    window.show()

    # настраиваем сценарий для элемента pushButton
    form.pushButton.clicked.connect(lbl3_add)
    form.lineEdit.textChanged.connect(ln_changed)

    timer1 = QtCore.QTimer()  # set up your QTimer
    timer1.timeout.connect(lbl3_add)  # connect it to your update function
    timer1.start(1000)  # set it to timeout in 5000 ms

    # запускаем окно программы
    app.exec()


asyncio.run(main())
