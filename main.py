import serial
import asyncio
import time
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget
from PyQt6 import QtCore
import requests
import glob
import os
import pandas as pd

# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = "COM6"
ser.open()
time.sleep(2)

# иницилизация самый ранний файл csv в каталоге булмера (маска поиска)
bullmer_log_folder_filter = "c:\\TEMP\*.csv"

# инициализация названия булмера
bullmer_db_log_name = ""

# инициализация точки входа для получение сверел с бд
drills_db = "http://10.55.128.67:5000/cutting/drills"

# Создаем пустой DataFrame
dfglobal = pd.DataFrame()


# функция, строит массив из сверел (два элемента). Сверла, вынутые с селектора
def get_indices(element, lst):
    return [i for i in range(len(lst)) if lst[i] == element]


# функция, сравнивает показания селектра и базы.
def comparison(lcd1, lcd2):
    if lcd1 == lcd2:
        return 1
    else:
        return 0


async def main():
    # функция, которая проверяет лог и стирает id раскладки из главного окна (тем самым делает его не скрытым)
    def logchk():
        # возвращаем самый ранний файл csv в каталоге логов
        list_of_files = glob.glob(bullmer_log_folder_filter)
        latest_file = max(list_of_files, key=os.path.getctime)
        print(latest_file)

        # создаем датафрейм и выводим его в консоль
        columns = [
            0,
            17,
            18,
            20,
            21,
            10,
            4,
            14,
            15,
            37,
            45,
            46,
            2,
        ]

        df1 = pd.read_csv(latest_file, sep=";", usecols=columns)
        df1.drop(index=df1.index[-1], axis=0, inplace=True)
        global dfglobal

        if dfglobal.equals(df1):
            print("Файл совпадает")

        else:
            # если произошла запись в логи, то будет выполняться эта часть. Сюда нужно вставить http post в БД Bullmer
            dfglobal = df1.copy()
            btn_clk()
            print("Файл не совпадает")

    # эта функция срабатывает при нажатии кнопки "Очистить"
    def btn_clk():
        form.lineEdit.clear()

    # эта функция срабатывает при изменении текста в поле id раскладки
    def ln_changed():
        url = drills_db
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

        # запускаем функцию сравнения значений селектора и базы. Управляем окном.
        if comparison(form.lcdNumber.value(), form.lcdNumber_3.value()) and comparison(
            form.lcdNumber_2.value(), form.lcdNumber_4.value()
        ):
            window.hide()
            return 1
        else:
            window.show()
            return 0

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)
    window.show()

    # настраиваем сценарий для элемента pushButton
    form.pushButton.clicked.connect(btn_clk)

    # настраиваем сценарий для элемента lineEdit
    form.lineEdit.textChanged.connect(ln_changed)

    # обновление строки с ардуино и lcd окон на интерфейсе
    timer1 = QtCore.QTimer()  # set up your QTimer
    timer1.timeout.connect(read_serial_arduino)  # connect it to your update function
    timer1.start(1000)  # set it to timeout in 5000 ms

    # обновление строки с ардуино и lcd окон на интерфейсе
    timer2 = QtCore.QTimer()  # set up your QTimer
    timer2.timeout.connect(logchk)  # connect it to your update function
    timer2.start(1000)  # set it to timeout in 5000 ms

    # запускаем окно программы
    app.exec()


asyncio.run(main())
