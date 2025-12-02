import asyncio


async def scanwifi(ip, port, on_data, reconnect_delay=5):
    """
    Подключается к устройству по IP и порту, читает данные и передает их в on_data.
    Если данные не являются int, передается 0.
    При разрыве соединения автоматически переподключается через reconnect_delay секунд.

    :param ip: IP устройства
    :param port: порт устройства
    :param on_data: асинхронная функция обработки данных
    :param reconnect_delay: время в секундах перед повторным подключением
    """
    while True:
        try:
            print(f"Connecting to {ip}:{port}...")
            reader, writer = await asyncio.open_connection(ip, port)
            print("Connected to W30", ip, port)

            while True:
                data = await reader.read(1024)
                if not data:
                    print("Connection closed by device")
                    break

                raw_message = data.decode().strip()

                try:
                    message = int(raw_message)
                except Exception:
                    message = 0

                await on_data(message)

        except Exception as e:
            print(f"Connection error: {e}")

        finally:
            if "writer" in locals():
                writer.close()
                await writer.wait_closed()
            print(f"Reconnecting in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)
