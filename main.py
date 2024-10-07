import serial
import asyncio
import time
from PyQt6 import uic
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton
from PyQt6 import QtCore
import requests


# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = "COM3"
ser.open()
time.sleep(2)


# функция, строит массив из сверел (два элемента)
def get_indices(element, lst):
    return [i for i in range(len(lst)) if lst[i] == element]


# функция, которая ничего не делает
async def fun1():
    await asyncio.sleep(1)
    print("функция 1")
    return "1"


# функция, которая ничего не делает
async def fun2():
    await asyncio.sleep(1)
    print("функция 2")
    return "2"


# функция, которая ничего не делает
async def fun3():
    await asyncio.sleep(1)
    print("функция 3")
    return "3"


async def main():
    # эта функция срабатывает при нажатии кнопки
    def btn_clk():
        print("Button clicked")
        form.lcdNumber.display(form.lcdNumber.intValue() + 1)

    # эта функция срабатывает при изменении текста в поле id раскладки
    def ln_changed():

        url = "https://httpbin.org/get"
        myobj = {"Zhopa": "Kedy", "Kon": "Vpalto"}

        x = requests.get(url, myobj)

        # print the response text (the content of the requested file):
        print(x.text)

    # эта функция получает строку с ардуино и вносит значения в интерфейс
    def read_serial_arduino():
        ser.write(b"1")
        asyncio.sleep(0.1)
        while ser.in_waiting:
            arduinostring = ser.readline().decode("utf-8")[:-2]
            form.label_3.setText(arduinostring)
            symbols = []  # массив символов - показаний ардуино
            drills = [
                "2",
                "3",
                "4",
                "6",
                "8",
                "10",
                "12",
                "15",
                "17",
                "18",
                "20",
                "21",
                "22",
                "24",
                "26",
            ]  # массив обозначений сверел селектора

            for symbol in arduinostring:
                symbols += symbol
            indices = get_indices("1", symbols)
            print(symbols)
            print(indices)
            try:
                form.lcdNumber.display(drills[indices[0]])
            except IndexError:
                form.lcdNumber.display("0")
            try:
                form.lcdNumber_2.display(drills[indices[1]])
            except IndexError:
                form.lcdNumber_2.display("0")

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)
    window.show()

    # настраиваем сценарий для элемента pushButton
    form.pushButton.clicked.connect(read_serial_arduino)
    form.lineEdit.textChanged.connect(ln_changed)

    # обновление строки с ардуино и lcd окон на интерфейсе
    timer1 = QtCore.QTimer()  # set up your QTimer
    timer1.timeout.connect(read_serial_arduino)  # connect it to your update function
    timer1.start(1000)  # set it to timeout in 5000 ms

    # запускаем окно программы
    app.exec()


asyncio.run(main())
