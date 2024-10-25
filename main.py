import serial
import asyncio
import time
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QPushButton
from PyQt5 import QtCore
import requests
import glob
import os
import pandas as pd
import json
import sqlite3
from datetime import datetime
import pywinauto
import warnings


#############################################################################################
# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = "COM6"
ser.open()
time.sleep(2)


# инициализации
##############################################################################################
# иницилизация имени базы SQLite
bullmer_sqlite_db = "bullmersqlite.db"

# иницилизация самый ранний файл csv в каталоге булмера (маска поиска)
bullmer_log_folder_filter = "c:\\TEMP\*.csv"

# инициализация названия булмера
bullmer_db_log_name = "4"

# инициализация точки входа для получение сверел с бд
drills_db = "http://10.55.128.67:5000/cutting/drills"

# инициализация точки входа отправки изменений в логе(статистики) в бд
blogs_db = "http://10.55.128.67:5000/cutting/bullmerStat"

# инициализация точки входа отправки текущей и предидущей раскладок в базу экрана раскроя
current_db = "http://10.55.128.67:5000/cutting/currentBullmerLog"

# инициализация ЧАСТИ строки названия nextgen - влияет на поиск окна nextgen, чтобы нажать клавишу редактора
nextgen_name = "NextGeneration R7.8.1"  # или "Nextgen 8.3.0"


# Создаем глобальный DataFrame
##############################################################################################
# возвращаем самый ранний файл csv в каталоге логов
list_of_files = glob.glob(bullmer_log_folder_filter)
latest_file = max(list_of_files, key=os.path.getctime)

# создаем датафрейм и выводим его в консоль
columns = [
    0,
    17,
    18,
    20,
    21,
    10,
    11,
    14,
    15,
    37,
    45,
    46,
    2,
]

dfglobal = pd.read_csv(latest_file, sep=";", usecols=columns)
dfglobal.drop(index=dfglobal.index[-1], axis=0, inplace=True)
##############################################################################################


# эта функция кликает по кнопке в nextgen
def nextgen_clicker():
    try:
        # здесь мы ищем наиболее подходящее окно по названию
        handle = pywinauto.findwindows.find_window(best_match=nextgen_name)

        app = pywinauto.application.Application(backend="uia").connect(
            handle=handle, timeout=100
        )

        # кликаем по кнопке редактора
        app.Dialog.child_window(
            title="qt_top_dock", control_type="Pane"
        ).СписокзаданийPane.СписокзаданийPane2.itsQueueEditPane.click_input()
    except:
        print("Запустите NextGen")


# функция, строит массив из сверел (два элемента). Сверла, вынутые с селектора
def get_indices(element, lst):
    return [i for i in range(len(lst)) if lst[i] == element]


# функция, сравнивает показания селектра и базы
def comparison(lcd1, lcd2):
    if lcd1 == lcd2:
        return 1
    else:
        return 0


async def main():
    # функция получает id последней раскладки из sqlite
    def sqlite_get(db):
        # Устанавливаем соединение с базой данных
        connection = sqlite3.connect(db)
        cursor = connection.cursor()
        cursor.execute("SELECT marker_id FROM idRasks order by id desc limit 1")
        return str(cursor.fetchall()[0])[:-2][1:]

    # функция получает время последней раскладки из sqlite
    def sqlite_get_time(db):
        # Устанавливаем соединение с базой данных
        connection = sqlite3.connect(db)
        cursor = connection.cursor()
        cursor.execute("SELECT datetime FROM idRasks order by id desc limit 1")
        return str(cursor.fetchall()[0])[:-2][1:]

    # функция получает две последние раскладки (id) из sqlite для отображения на ТВ
    def sqlite_get_last_two_records(db):
        # Устанавливаем соединение с базой данных
        connection = sqlite3.connect(db)
        cursor = connection.cursor()
        cursor.execute("SELECT marker_id FROM idRasks order by id desc limit 2")
        return cursor.fetchall()

    # функция отправляет данные раскладки в sqlite
    def sqlite_post(marker_id, db):
        # Устанавливаем соединение с базой данных
        connection = sqlite3.connect(db)
        cursor = connection.cursor()

        # Создаем таблицу раскладок в sqlite
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS idRasks (id INTEGER PRIMARY KEY, marker_id TEXT, datetime TEXT)"
        )

        # Сохраняем изменения
        connection.commit()

        if marker_id != "":
            cursor.execute(
                "INSERT INTO idRasks (marker_id, datetime) VALUES (?,?)",
                (marker_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

            # Сохраняем изменения
            connection.commit()
        connection.close()

    # функция, которая проверяет лог и стирает id раскладки из главного окна (тем самым делает его не скрытым)
    def logchk():
        # возвращаем самый ранний файл csv в каталоге логов
        list_of_files = glob.glob(bullmer_log_folder_filter)
        latest_file = max(list_of_files, key=os.path.getctime)
        # print(latest_file)

        # создаем датафрейм и выводим его в консоль
        columns = [
            0,
            17,
            18,
            20,
            21,
            10,
            11,
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
            pass  # "Файл совпадает"

        else:
            # если произошла запись в логи, то будет выполняться эта часть. Сюда нужно вставить http post в БД Bullmer
            dfglobal = df1.copy()
            btn_clk()
            print("Файл не совпадает. Записываем в SQL")

            # этот запрос отправляет данные на сервер. пишет статистику Булмер в базу
            data = {
                "data": {
                    "cutter": bullmer_db_log_name,  # number
                    "Bild": dfglobal.loc[
                        len(dfglobal) - 1, "Bild                "
                    ].lstrip(),  # string
                    "DStart": dfglobal.loc[len(dfglobal) - 1, "Start    .1"].rstrip()
                    + " "
                    + dfglobal.loc[len(dfglobal) - 1, "Start    "].rstrip(),  # string
                    "DEnde": dfglobal.loc[len(dfglobal) - 1, "Ende     .1"].rstrip()
                    + " "
                    + dfglobal.loc[len(dfglobal) - 1, "Ende     "].rstrip(),  # string
                    "JOB": dfglobal.loc[
                        len(dfglobal) - 1, "JOB[min]"
                    ].lstrip(),  # number
                    "CUT": dfglobal.loc[
                        len(dfglobal) - 1, "CUT[min]"
                    ].lstrip(),  # number
                    "Bite": dfglobal.loc[
                        len(dfglobal) - 1, "Bite[min]"
                    ].lstrip(),  # number
                    "Neben": str(
                        dfglobal.loc[len(dfglobal) - 1, "Neben[min]"]
                    ).lstrip(),  # number
                    "idRask": sqlite_get(bullmer_sqlite_db),  # string, данные в SQLite
                    "Drills": None,  # number
                    "Hdrills": None,  # number
                }
            }
            json_data = json.dumps(data)
            requests.post(blogs_db, data=json_data)
            print(json_data)

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
            nextgen_clicker()  # если раскладка найдена в базе - запускаем редактор NextGen
        except:
            form.lcdNumber_3.display(None)
            form.lcdNumber_4.display(None)

        # проверяем, сканировали ли мы эту раскладку ранее (проверяем последнюю запись в SQLite). Если да, выводим worning
        if sqlite_get(bullmer_sqlite_db) == form.lineEdit.text():
            print("Уже сканировали " + sqlite_get_time(bullmer_sqlite_db))

        # записывает отсканированную раскладку в sqlite
        sqlite_post(form.lineEdit.text(), bullmer_sqlite_db)

        # записываем текущую и предыдущую раскладки в sql бд Bullmer.current
        url = current_db
        data = {
            "data": {
                "idrask": str(sqlite_get_last_two_records(bullmer_sqlite_db)[0])[:-2][
                    1:
                ],  # string
                "idraspost": str(sqlite_get_last_two_records(bullmer_sqlite_db)[1])[
                    :-2
                ][1:],  # string
                "komp": "Bullmer" + str(bullmer_db_log_name),  # string
            }
        }
        if form.lineEdit.text() == "":
            pass
        else:
            print(requests.post(current_db, json=data, timeout=2.50))
            print(data)

    # эта функция получает строку с ардуино и вносит значения в интерфейс
    def read_serial_arduino():
        ser.write(b"1")

        # убираем ворнинги от asyncio
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
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

                    # запускаем функцию сравнения значений селектора и базы. Управляем окном.
                if comparison(
                    form.lcdNumber.value(), form.lcdNumber_3.value()
                ) and comparison(
                    form.lcdNumber_2.value(),
                    form.lcdNumber_4.value() and form.lcdNumber_2.value(),
                ):
                    window.hide()
                    return 1
                else:
                    window.show()
                    return 0

            else:
                form.lcdNumber.display(None)
                form.lcdNumber_2.display(None)

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)

    window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)  # Поверх всех окон
    window.setWindowFlag(
        QtCore.Qt.FramelessWindowHint, True
    )  # Запрещаем двигать окно, убирая рамку
    window.setWindowFlag(QtCore.Qt.WindowMinimizeButtonHint, False)

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
