import serial
import asyncio
import time
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication
from PyQt5 import QtCore
import requests
import glob
import os
import pandas as pd  # используем для анализа логов и трекинга их изменений
import sqlite3
import datetime
import pywinauto
import warnings
from tkinter import *
from tkinter import font
import yaml
import pyautogui
from bleak_winrt import _winrt


_winrt.uninit_apartment()  # Убираем ошибку при запуске (https://github.com/hbldh/bleak/issues/423)

# инициализации
##############################################################################################

# читаем файл конфигурации

with open("config.yml", "r") as file:
    Bullmer = yaml.safe_load(file)

# иницилизация имени базы SQLite
bullmer_sqlite_db = Bullmer["Bullmer"]["bullmer_sqlite_db"]

# иницилизация самый ранний файл csv в каталоге булмера (маска поиска)
bullmer_log_folder_filter = Bullmer["Bullmer"]["bullmer_log_folder_filter"] + "\*.csv"

# инициализация названия булмера
bullmer_db_log_name = Bullmer["Bullmer"]["bullmer_db_log_name"]

# инициализация точки входа для получение сверел с бд
drills_db = Bullmer["Bullmer"]["drills_db"]

# инициализация точки входа отправки изменений в логе(статистики) в бд
blogs_db = Bullmer["Bullmer"]["blogs_db"]

# инициализация точки входа отправки изменений в логе(статистики) в бд. Отправка всего файла
blog_db_batch = Bullmer["Bullmer"]["blog_db_batch"]

# инициализация точки входа отправки текущей и предидущей раскладок в базу экрана раскроя
current_db = Bullmer["Bullmer"]["current_db"]

# инициализация ЧАСТИ строки названия nextgen - влияет на поиск окна nextgen, чтобы нажать клавишу редактора
nextgen_name = Bullmer["Bullmer"]["nextgen_name"]  # или "Nextgen 8.3.0"

# пароль бригадира
supervisor_pass = Bullmer["Bullmer"]["supervisor_pass"]


# номер Serial порта
serial_port = Bullmer["Bullmer"]["serial_port"]

#############################################################################################
# иницилизация порта Ардуино
ser = serial.Serial()
ser.baudrate = 9600
ser.port = serial_port
ser.open()
time.sleep(2)

# Создаем глобальный DataFrame
##############################################################################################
# возвращаем самый ранний файл csv в каталоге логов
try:
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


# если лог пустой
except IndexError:
    list_of_files = glob.glob(bullmer_log_folder_filter)
    latest_file = max(list_of_files, key=os.path.getctime)

    # создаем датафрейм
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
        top = Tk()
        top.geometry("200x200+10+10")
        top.title("NextGen")

        # make font template
        appHighlightFont = font.Font(family="Helvetica", size=15, weight="bold")
        font.families()

        # create listbox object
        listbox1 = Listbox(
            top,
            height=8,
            width=18,
            bg="lightgrey",
            activestyle="dotbox",
            font=appHighlightFont,
            fg="red",
        )
        listbox1.insert(1, "Запустите NextGen")
        listbox1.grid(row=1, column=1, sticky=W, pady=2)
        top.mainloop()


# функция, сравнивает показания селектра и базы
def comparison(lcd1, lcd2):
    if lcd1 == lcd2:
        return 1
    else:
        return 0


async def main():
    # функция, строит массив из сверел (два элемента). Сверла, вынутые с селектора
    def get_indices(element, lst):
        return [i for i in range(len(lst)) if lst[i] == element]

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
                (marker_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

            # Сохраняем изменения
            connection.commit()
        connection.close()

    # функция, которая проверяет лог и отсылает данные в SQL
    def logchk():
        try:
            # возвращаем самый ранний файл csv в каталоге логов
            list_of_files = glob.glob(bullmer_log_folder_filter)
            latest_file = max(list_of_files, key=os.path.getctime)

            # создаем датафрейм
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

            list = []  # список обьектов для отправки на сервер

            for i in range(0, len(df1)):
                DStart = dfglobal.loc[i, "Start    .1"].rstrip().replace(".", "-")
                DEnde = dfglobal.loc[i, "Ende     .1"].rstrip().replace(".", "-")

                # этот запрос отправляет данные на сервер. пишет статистику Булмер в базу
                data = {
                    "Bild": dfglobal.loc[i, "Bild                "]
                    .lstrip()
                    .rstrip(),  # string
                    ############################## конвертируем дату в формат SQL
                    "DStart": datetime.datetime.strptime(DStart, "%d-%m-%y").strftime(
                        "%Y-%m-%d"
                    )
                    ############################## конвертируем дату в формат SQL
                    + " "
                    + dfglobal.loc[i, "Start    "].rstrip(),  # string
                    ############################## конвертируем дату в формат SQL
                    "DEnde": datetime.datetime.strptime(DEnde, "%d-%m-%y").strftime(
                        "%Y-%m-%d"
                    )
                    ############################## конвертируем дату в формат SQL
                    + " "
                    + dfglobal.loc[i, "Ende     "].rstrip(),  # string
                    "JOB": dfglobal.loc[i, "JOB[min]"]
                    .lstrip()
                    .replace(",", "."),  # number
                    "CUT": dfglobal.loc[i, "CUT[min]"]
                    .lstrip()
                    .replace(",", "."),  # number
                    "Bite": dfglobal.loc[i, "Bite[min]"]
                    .lstrip()
                    .replace(",", "."),  # number
                    "Neben": str(dfglobal.loc[i, "Neben[min]"]).lstrip(),  # number
                    "idRask": "0",  # sqlite_get(bullmer_sqlite_db),  # string, данные в SQLite
                }
                list.append(data)
            addtosqldata = {"data": {"cutter": bullmer_db_log_name, "payload": list}}
            print("sent log to SQL")
            print(requests.post(blog_db_batch, json=addtosqldata, timeout=None))

        except Exception as err:
            print(err)

    # функция, которая проверяет лог и стирает id раскладки из главного окна (тем самым делает его не скрытым)
    def logcheck_clear_id():
        try:
            # возвращаем самый ранний файл csv в каталоге логов
            list_of_files = glob.glob(bullmer_log_folder_filter)
            latest_file = max(list_of_files, key=os.path.getctime)

            # создаем датафрейм
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

            if len(dfglobal) == len(df1):
                # файл лога не изменился. ничего не делаем
                pass
            else:
                # если произошла запись в логи, то будет выполняться эта часть.
                dfglobal = df1.copy()
                btn_clk()  # очищаем окно ввода
                print("Файл не совпадает. Очищаем окно ввода")

        except Exception as err:
            print(err)

    # эта функция срабатывает при нажатии кнопки "Очистить"
    def btn_clk():
        form.lineEdit.setText("")
        form.lcdNumber_3.display(None)
        form.lcdNumber_4.display(None)

    # эта функция срабатывает при нажатии кнопки "Очистить" пароль супервайзера
    def btn_clk_sv():
        form.lineEdit_2.setText("")

    # эта функция срабатывает при изменении текста в поле id раскладки
    def ln_changed():
        url = drills_db
        myobj = {"markerID": form.lineEdit.text()}
        try:
            x = requests.get(url, myobj)
            # выводим ответ

            form.lcdNumber_3.display(x.json().get("Сверло1", None))
            form.lcdNumber_4.display(x.json().get("Сверло2", None))

            # проверяем, сканировали ли мы эту раскладку ранее (проверяем последнюю запись в SQLite). Если да, выводим worning
            if sqlite_get(bullmer_sqlite_db) == form.lineEdit.text():
                print("Уже сканировали " + sqlite_get_time(bullmer_sqlite_db))

                top = Tk()
                top.geometry("200x200+10+10")
                top.title("SQLite")

                # make font template
                appHighlightFont = font.Font(family="Helvetica", size=15, weight="bold")
                font.families()

                # create listbox object
                listbox1 = Listbox(
                    top,
                    height=8,
                    width=18,
                    bg="lightgrey",
                    activestyle="dotbox",
                    font=appHighlightFont,
                    fg="red",
                )
                listbox1.insert(1, "Уже сканировали")
                listbox1.insert(2, sqlite_get_time(bullmer_sqlite_db))
                listbox1.grid(row=1, column=1, sticky=W, pady=2)
                top.mainloop()

            # записывает отсканированную раскладку в sqlite
            sqlite_post(form.lineEdit.text(), bullmer_sqlite_db)

            # записываем текущую и предыдущую раскладки в sql бд Bullmer.current
            url = current_db
            data = {
                "data": {
                    "idrask": str(sqlite_get_last_two_records(bullmer_sqlite_db)[0])[
                        :-2
                    ][1:],  # string
                    "idraspost": str(sqlite_get_last_two_records(bullmer_sqlite_db)[1])[
                        :-2
                    ][1:],  # string
                    "komp": "Bullmer" + str(bullmer_db_log_name),  # string
                }
            }
            if form.lineEdit.text() == "":
                pass
            else:
                print("sent current to SQL current")
                print(requests.post(current_db, json=data, timeout=2.50))
            nextgen_clicker()  # запускаем редактор NextGen
        except:
            form.lcdNumber_3.display(None)
            form.lcdNumber_4.display(None)

    # эта функция срабатывает при изменении текста в поле пароль бригадира
    def ln_changed_sv():
        if form.lineEdit_2.text() == supervisor_pass:
            window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            form.lineEdit_2.setStyleSheet(
                "QLineEdit" "{" "background : lightgreen;" "}"
            )

        else:
            window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
            form.lineEdit_2.setStyleSheet("QLineEdit" "{" "background : white;" "}")

    # эта функция получает строку с ардуино и вносит значения в интерфейс
    def read_serial_arduino():
        if ser.isOpen() != True:
            ser.open()
        else:
            pass

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

            if len(indices) == 1:  # если вытащили одно сверло
                form.lcdNumber.display(drills[indices[0]])
                form.lcdNumber_2.display(None)
                drill1 = drills[indices[0]]
                drill2 = 0

            elif len(indices) == 2:
                form.lcdNumber.display(drills[indices[0]])
                form.lcdNumber_2.display(drills[indices[1]])
                drill1 = drills[indices[0]]
                drill2 = drills[indices[1]]
            else:
                form.lcdNumber.display(None)
                form.lcdNumber_2.display(None)
                drill1 = 0
                drill2 = 0

                # запускаем функцию сравнения значений селектора и базы. Управляем окном.
                ########################################################################
            url = drills_db
            myobj = {"markerID": form.lineEdit.text()}
            x = requests.get(url, myobj)
            try:
                drill1_sql = int(x.json().get("Сверло1", None))
            except:
                drill1_sql = 0

            try:
                drill2_sql = int(x.json().get("Сверло2", None))
            except:
                drill2_sql = 0

            try:
                drill_id = x.json().get("id", None)
            except:
                drill_id = 0

            list1 = [
                int(drill1),
                int(drill2),
            ]  # список для сравнения сверл селектора и сверл базы
            list2 = [
                int(drill1_sql),
                int(drill2_sql),
            ]  # список для сравнения сверл селектора и сверл базы
            list1.sort()
            list2.sort()

            if form.lineEdit.text() != "" and drill_id != 0:
                if list1 == list2:  # сверла селектора совпадают с базой
                    window.hide()
                elif (list2[0] == list2[1]) and list2[0] == list1[
                    1
                ]:  # сверла базы одинаковые
                    window.hide()
                else:
                    window.show()
            else:
                window.show()

                #########################################################################

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

    # настраиваем сценарий для элемента pushButton (под id раскладки)
    form.pushButton.clicked.connect(btn_clk)

    # настраиваем сценарий для элемента pushButton_2 (пароль бригадира)
    form.pushButton_2.clicked.connect(btn_clk_sv)

    # настраиваем сценарий для элемента lineEdit (id раскладки)
    form.lineEdit.returnPressed.connect(ln_changed)

    # настраиваем сценарий для элемента lineEdit_2 (пароль супервайзера)
    form.lineEdit_2.textChanged.connect(ln_changed_sv)

    # обновление строки с ардуино и lcd окон на интерфейсе
    timer1 = QtCore.QTimer()  # set up your QTimer
    timer1.timeout.connect(read_serial_arduino)  # connect it to your update function
    timer1.start(1000)  # set it to timeout in 5000 ms

    timer2 = QtCore.QTimer()  # set up your QTimer
    timer2.timeout.connect(logchk)  # connect it to your update function
    timer2.start(60_000)  # set it to timeout in 60_000 ms

    # проверка логов для стирания записи раскладки
    timer3 = QtCore.QTimer()  # set up your QTimer
    timer3.timeout.connect(logcheck_clear_id)  # connect it to your update function
    timer3.start(5000)  # set it to timeout in 5000 ms

    # запускаем окно программы
    app.exec()


asyncio.run(main())
