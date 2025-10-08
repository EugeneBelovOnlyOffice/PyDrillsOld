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
from bleak_winrt import _winrt
import pyautogui
import nats
from nats.errors import ConnectionClosedError, TimeoutError, NoServersError
from threading import Thread
import scanner
import beep
import json
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QObject, pyqtSignal
import sys
import psutil

# перенаправление консоли


class EmittingStream(QObject):
    text_written = pyqtSignal(str)

    def write(self, text):
        if text:
            self.text_written.emit(str(text))

    def flush(self):
        pass


# проверяем на повторный запуск программы, чтобы она не лочила компорт


def check_already_running():
    current_pid = os.getpid()
    current_name = os.path.basename(sys.argv[0])

    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if proc.info["pid"] != current_pid:
                if proc.info["cmdline"] and current_name in proc.info["cmdline"][0]:
                    print(" ⚠️ Программа уже запущена!")
                    sys.exit(0)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


check_already_running()


_winrt.uninit_apartment()  # Убираем ошибку при запуске (https://github.com/hbldh/bleak/issues/423)

# инициализации
##############################################################################################

# читаем файл конфигурации

with open("config.yml", "r") as file:
    Bullmer = yaml.safe_load(file)

# иницилизация имени базы SQLite
bullmer_sqlite_db = Bullmer["Bullmer"]["bullmer_sqlite_db"]

if not os.path.exists(bullmer_sqlite_db):
    print(
        f"⚠️ База данных '{bullmer_sqlite_db}' не найдена. Создаём новую SQLite-базу..."
    )
    try:
        conn = sqlite3.connect(bullmer_sqlite_db)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS idRasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marker_id INTEGER NOT NULL,
            datetime TEXT NOT NULL
        )
        """)
        cursor.execute(
            "INSERT INTO idRasks (marker_id, datetime) VALUES (?,?)",
            (1, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        cursor.execute(
            "INSERT INTO idRasks (marker_id, datetime) VALUES (?,?)",
            (1, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        conn.close()
        print("✅ Новая база данных успешно создана.")
    except Exception as e:
        print(f"❌ Ошибка при создании базы данных: {e}")
        sys.exit(1)

# иницилизация самый ранний файл csv в каталоге булмера (маска поиска)
bullmer_log_folder_filter = Bullmer["Bullmer"]["bullmer_log_folder_filter"] + "\*.csv"
search_mask = os.path.join(Bullmer["Bullmer"]["bullmer_log_folder_filter"], "*.csv")
try:
    csv_files = glob.glob(search_mask)

    if not csv_files:
        raise FileNotFoundError(
            f"❌ В каталоге '{Bullmer['Bullmer']['bullmer_log_folder_filter']}' не найдено ни одного CSV-файла."
        )

    # находим самый ранний файл по дате изменения
    earliest_csv = min(csv_files, key=os.path.getmtime)
    print(f"✅ Найден CSV-файл: {earliest_csv}")

except Exception as e:
    print(f"⚠️ Ошибка при поиске CSV: {e}")
    sys.exit(1)  # завершаем программу, чтобы не продолжать без данных

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

# подключение к nats
nats_ip = Bullmer["Bullmer"]["nats_ip"]

# строка сверл, котрые мы отключили для отслеживания. 0 - датчик отслеживается, 1 - датчик выключен программно
drills_off = Bullmer["Bullmer"]["drills_off"]

# тестовая раскладка, мы не будем писать ее в базу
test_marker = Bullmer["Bullmer"]["test_marker"]

# Проверка наличия interface.ui
try:
    ui_files = glob.glob("interface.ui")

    if not ui_files:
        raise FileNotFoundError(
            "❌ Файл интерфейса 'interface.ui' не найден в текущей директории."
        )

    interface_path = ui_files[0]
    print(f"✅ Найден UI-файл: {interface_path}")

except Exception as e:
    print(f"⚠️ Ошибка при поиске interface.ui: {e}")
    sys.exit(1)

# Проверка наличия config.yml
try:
    ui_files = glob.glob("config.yml")

    if not ui_files:
        raise FileNotFoundError(
            "❌ Файл конфига 'config.yml' не найден в текущей директории."
        )

    config_path = ui_files[0]
    print(f"✅ Найден UI-файл: {config_path}")

except Exception as e:
    print(f"⚠️ Ошибка при поиске config.yml: {e}")
    sys.exit(1)

#############################################################################################
# иницилизация порта Ардуино
while True:
    try:
        ser = serial.Serial(port=serial_port, baudrate=9600, timeout=1)
        break  # порт успешно открыт, выходим из цикла
    except serial.SerialException as e:
        print(f" ❌ Ошибка при открытии порта {serial_port}: {e}")
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
        2,
    ]

    dfglobal = pd.read_csv(latest_file, sep=";", usecols=columns)


# эта функция кликает по кнопке в nextgen
def nextgen_clicker():
    pywinauto.timings.Timings.fast()  # устанавливаем глобально быстрые тайминги для  pywinauto
    try:
        # здесь мы ищем наиболее подходящее окно по названию
        handle = pywinauto.findwindows.find_window(best_match=nextgen_name)

        app = pywinauto.application.Application(backend="uia").connect(
            handle=handle, timeout=1
        )
        # кликаем по кнопке редактора
        app.Dialog.child_window(
            best_match="itsQueueEditPane", control_type="Pane"
        ).click_input()

    except Exception:
        print(" ⚠️ Запустите NextGen")


# функция, сравнивает показания селектра и базы
def comparison(lcd1, lcd2):
    if lcd1 == lcd2:
        return 1
    else:
        return 0


# глобальные переменные хранят полученные из базы сверла при сканировании раскладки. Раскладка хранится для управления окном селектора
drill1_sql = 0
drill2_sql = 0
drill_id = 0
marker_id = 0


async def main():
    # функция выводит сообщение, что раскладку уже сканировали
    def worning_window(message, color, duration):
        # Параметры окна
        width, height = 500, 250
        duration = 3000  # время в миллисекундах

        # Создаём всплывающее окно без кнопок
        warn = QWidget(window)
        warn.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        warn.setStyleSheet(f"background-color: lightgrey; border: 3px solid {color};")

        # Центрируем окно по экрану
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = (screen_geometry.width() - width) // 2
        y = (screen_geometry.height() - height) // 2
        warn.setGeometry(x, y, width, height)

        # Добавляем текст
        layout = QVBoxLayout()
        label = QLabel(message)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 24pt;")
        layout.addWidget(label)
        warn.setLayout(layout)

        warn.show()
        warn.raise_()
        warn.activateWindow()

        # Автоматическое закрытие через duration миллисекунд
        QTimer.singleShot(duration, warn.close)

    # функция получает сверла из базы для id раскладки и саму раскладку
    def sql_drills_get():
        url = drills_db
        myobj = {"markerID": form.lineEdit.text()}
        x = requests.get(url, myobj)
        try:
            global drill1_sql
            drill1_sql = int(x.json().get("Сверло1", None))
        except:
            drill1_sql = 0

        try:
            global drill2_sql
            drill2_sql = int(x.json().get("Сверло2", None))
        except:
            drill2_sql = 0

        try:
            global drill_id
            drill_id = x.json().get("id", None)
        except:
            drill_id = 0

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
            print(" ✅ sent log to SQL")
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
        global marker_id
        marker_id = 0
        form.lineEdit.setText("")
        window.activateWindow()
        form.lineEdit.setFocus()
        form.lcdNumber_3.display(None)
        form.lcdNumber_4.display(None)

    # эта функция отправки текущей и предыдущей раскладки в nats
    async def send_nats():
        nc = await nats.connect(nats_ip)
        while True:
            curent_id = str(sqlite_get_last_two_records(bullmer_sqlite_db)[0])[:-2][
                1:
            ]  # id раскладки текуще
            past_id = str(sqlite_get_last_two_records(bullmer_sqlite_db)[1])[:-2][
                1:
            ]  # id раскладки предыдущее
            await asyncio.sleep(3)
            await nc.publish(
                "cutter" + bullmer_db_log_name,
                bytes(curent_id + "," + past_id, encoding="utf-8"),
            )
            # публиувция для плавающего перестила
            await nc.publish(
                "bullmerLog",
                json.dumps(
                    {
                        "event": "getCurrentMarker",
                        "payload": {"markerID": curent_id, "mode": "current"},
                    }
                ).encode(),
            )
            # публиувция для плавающего перестила
            await nc.publish(
                "bullmerLog",
                json.dumps(
                    {
                        "event": "getCurrentMarker",
                        "payload": {"markerID": past_id, "mode": "previous"},
                    }
                ).encode(),
            )

    # эта функция срабатывает при нажатии кнопки "Очистить" пароль супервайзера
    def btn_clk_sv():
        form.lineEdit_2.setText("")

    # эта функция срабатывает при изменении текста в поле id раскладки
    def ln_changed():
        # проверяем, есть ли такая раскладка в БД
        try:
            url = drills_db
            myobj = {"markerID": form.lineEdit.text()}

            x = requests.get(url, params=myobj)
            print(x.json())

            data = x.json()
            if data is None:
                print("❌ Нет такой раскладки. Сервер вернул None")
                btn_clk()
                return
            x.raise_for_status()  # выбросит исключение для 4xx и 5xx ошибок
        except requests.exceptions.HTTPError as http_err:
            if http_err.response is not None and http_err.response.status_code == 500:
                print(" ❌ Ошибка сервера 500: попробуйте позже")
                btn_clk()
            else:
                print(f" ❌ HTTP ошибка: {http_err}")
                btn_clk()

        except requests.exceptions.RequestException as err:
            print(f" ❌ Ошибка запроса: {err}")
            btn_clk()
        else:
            global marker_id
            text = x.json().get("id", None)  # получаем текст из QLineEdit
            try:
                marker_id = int(text)
            except ValueError:
                btn_clk()

            nextgen_clicker()  # запускаем редактор NextGen
            sql_drills_get()  # эта функция присваивает значения глобальным переменным сверл базы, для управления окном функцией read_serial_arduino()
            url = drills_db
            myobj = {"markerID": form.lineEdit.text()}
            try:
                x = requests.get(url, params=myobj)

                # выводим ответ
                form.lcdNumber_3.display(x.json().get("Сверло1", None))
                form.lcdNumber_4.display(x.json().get("Сверло2", None))

                # проверяем, сканировали ли мы эту раскладку ранее (проверяем последнюю запись в SQLite). Если да, выводим worning
                if sqlite_get(bullmer_sqlite_db).strip("'\"") == form.lineEdit.text():
                    print(" ❌ Уже сканировали " + sqlite_get_time(bullmer_sqlite_db))
                    worning_window("Уже сканировали!!!", "red", 6000)
                    btn_clk()

                # записывает отсканированную раскладку в sqlite
                if (
                    test_marker == form.lineEdit.text()
                ):  # если это тест, то в базу sqlite не пишем, чтобы убрать повторный ворнинг
                    pass
                else:
                    sqlite_post(form.lineEdit.text(), bullmer_sqlite_db)

            except Exception as ex:
                print(ex)
                form.lcdNumber_3.display(None)
                form.lcdNumber_4.display(None)

    # эта функция срабатывает при изменении текста в поле пароль бригадира
    def ln_changed_sv():
        if form.lineEdit_2.text() == supervisor_pass:
            window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            form.lineEdit_2.setStyleSheet("QLineEdit{background : lightgreen;}")

        else:
            window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
            form.lineEdit_2.setStyleSheet("QLineEdit{background : white;}")

    # эта функция получает строку с ардуино и вносит значения в интерфейс
    def read_serial_arduino():
        if not ser.is_open:
            while True:
                try:
                    ser.open()  # откроет только если закрыт

                    break
                except serial.SerialException as e:
                    print(f" ❌[WARN] Порт недоступен: {e}")
                time.sleep(2)
        try:
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

                for index, symbol in enumerate(arduinostring):
                    # здесь пишем логику наложения маски отключенных сверл на строку показаний с датчиком

                    if drills_off[index] == "0":
                        symbols += symbol
                    else:
                        symbols += "0"

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

                if marker_id != 0:
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
        except serial.SerialException as e:
            print(f" ❌[ERROR] Ошибка работы с портом: {e}. Переподключение...")
            ser.close()

    # Перезапускает текущий процесс
    def restart_program():
        python = sys.executable
        os.execl(python, python, *sys.argv)

    # Переопределяем событие закрытия у главного окна
    def prevent_close_event(event):
        event.ignore()  # не даём PyQt закрыть окно
        window.hide()  # можно скрыть, если нужно
        restart_program()

    # подключаем файл, полученный в QtDesigner
    Form, Window = uic.loadUiType("interface.ui")
    app = QApplication([])
    window, form = Window(), Form()
    form.setupUi(window)

    def append_text(text):
        form.textEditConsole.moveCursor(form.textEditConsole.textCursor().End)
        form.textEditConsole.insertPlainText(text)
        form.textEditConsole.ensureCursorVisible()

    sys.stdout_stream = EmittingStream()
    sys.stdout_stream.text_written.connect(append_text)
    sys.stdout = sys.stdout_stream

    window.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)  # Поверх всех окон
    window.setWindowFlag(
        QtCore.Qt.FramelessWindowHint, True
    )  # Запрещаем двигать окно, убирая рамку
    window.setWindowFlag(QtCore.Qt.WindowMinimizeButtonHint, False)
    window.closeEvent = prevent_close_event
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

    # запуск функции, которая проверяет лог и отсылает данные в SQL
    timer2 = QtCore.QTimer()  # set up your QTimer
    timer2.timeout.connect(logchk)  # connect it to your update function
    timer2.start(60_000)  # set it to timeout in 60_000 ms

    # проверка логов для стирания записи раскладки
    timer3 = QtCore.QTimer()  # set up your QTimer
    timer3.timeout.connect(logcheck_clear_id)  # connect it to your update function
    timer3.start(5000)  # set it to timeout in 5000 ms

    # запускает функцию send_nats() отправки текущей и предыдущей раскладки в nats
    _thread = Thread(target=asyncio.run, args=(send_nats(),))
    _thread.start()

    # запускаем окно программы
    app.exec()


asyncio.run(main())
