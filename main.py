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
ser.port = "COM6"
ser.open()
time.sleep(2)


# функция, строит массив из сверел (два элемента). Сверла, вынутые с селектора
def get_indices(element, lst):
    return [i for i in range(len(lst)) if lst[i] == element]


# функция, сравнивает показания селектра и базы. Сворачивает окно, если они совпадают
def comparison():
    print("comparison_fun")
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
        form.lineEdit.clear()

    # эта функция срабатывает при изменении текста в поле id раскладки
    def ln_changed():
        url = "http://10.55.128.67:5000/cutting/drills"
        myobj = {"markerID": form.lineEdit.text()}
        try:
            x = requests.get(url, myobj)
            # выводим ответ

            form.lcdNumber_3.display(x.json().get("Сверло1", None))
            form.lcdNumber_4.display(x.json().get(("Сверло2", None)))
            print(x.json().get("Сверло1", None))
            print(x.json().get(("Сверло2", None)))
        except:
            form.lcdNumber_3.display(None)
            form.lcdNumber_4.display(None)

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
            if len(indices) <= 2:
                try:
                    form.lcdNumber.display(drills[indices[0]])
                except IndexError:
                    form.lcdNumber.display(None)
                try:
                    form.lcdNumber_2.display(drills[indices[1]])
                except IndexError:
                    form.lcdNumber_2.display(None)
            else:
                form.lcdNumber.display(None)
                form.lcdNumber_2.display(None)
        comparison()

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)
    window.show()

    # настраиваем сценарий для элемента pushButton
    form.pushButton.clicked.connect(btn_clk)
    form.lineEdit.textChanged.connect(ln_changed)

    # обновление строки с ардуино и lcd окон на интерфейсе
    timer1 = QtCore.QTimer()  # set up your QTimer
    timer1.timeout.connect(read_serial_arduino)  # connect it to your update function
    timer1.start(1000)  # set it to timeout in 5000 ms

    timer2 = QtCore.QTimer()  # set up your QTimer
    timer2.timeout.connect(comparison)  # connect it to your update function
    timer2.start(1000)  # set it to timeout in 5000 ms

    # запускаем окно программы
    app.exec()


asyncio.run(main())
