# USB Serial IDE

Мощный, но очень лёгкий терминал для инженеров. Специально заточен под ежедневную работу с UART, STM32, ESP, nRF и т.д.

![Скриншот терминала Amber](screenshots/musbs_term_amber.py.png)
<img src="screenshots/musbs_term_blue.py.png" alt="Описание" width="300"/>
<img src="screenshots/musbs_term_green_a.py.png" alt="Описание" width="300"/>
<img src="screenshots/musbs_term_green_b.py.png" alt="Описание" width="300"/>

## Возможности

- Горячие клавиши для всего
- Быстрый список команд (один клик = отправить)
- Повтор отправки с настраиваемым интервалом и количеством повторений
- Автосохранение лога с красивым именем
- Профили (сохраняются все настройки + команды)
- Полная устойчивость к отваливанию USB-порта
- Тёмные/светлые темы
- Виртуальный режим для отладки

## Горячие клавиши

| Клавиша                    | Действие                                       |
|----------------------------|------------------------------------------------|
| **Ctrl + X**               | Выход из программы                             |
| **Ctrl + B**               | Очистить терминал и буфер                      |
| **Ctrl + C**               | Скопировать выделенный текст в буфер обмена    |
|                            | автоматически копируется в буфер обмена системы|
| **Ctrl + F**               | Сохранить профиль по умолчанию                 |
| **Ctrl + H**               | Показать справку                               |
| **Esc**                    | Вернуться из справки обратно в лог             |
| **Enter**                  | Отправить команду                              |
| **Клик по строке справа**  | Отправить + скопировать в поле ввода           |
| **Двойной клик по строке** | Редактировать команду                          |
| **Клик по HEX**            | Скопировать hex-строку в буфер обмена          |

При нажатии **Ctrl + S** теперь лог не только сохраняется в файл, 
но и **автоматически копируется в буфер обмена** системы.  
Можно сразу вставить его (Cmd+V / Ctrl+V) в любой редактор, чат, заметки и т.д.

## Установка и запуск

### Быстрый старт (macOS)

```bash
# Клонировать репозиторий
git clone https://github.com/твой_ник/usbs-serial-ide.git
cd usbs-serial-ide

# Установить зависимости
pip install pyserial

# Запустить используя системный Python (рекомендуется)
./my_term.py
# или
/usr/bin/python3 my_term.py
```

### Альтернатива: использование pyenv

Если вы используете pyenv и получаете ошибку `ModuleNotFoundError: No module named '_tkinter'`:

```bash
# Установить Tcl/Tk через Homebrew
brew install tcl-tk

# Переустановить Python с поддержкой Tkinter
PYTHON_CONFIGURE_OPTS="--with-tcltk-includes='-I$(brew --prefix tcl-tk)/include' --with-tcltk-libs='-L$(brew --prefix tcl-tk)/lib'" \
pyenv install 3.14.0

# Установить локальную версию
pyenv local 3.14.0

# Установить зависимости
pip install pyserial

# Запустить
./my_term.py
```

### Linux

```bash
# Установить системные зависимости
sudo apt-get install python3-tk  # Debian/Ubuntu
# или
sudo dnf install python3-tkinter  # Fedora

# Установить зависимости Python
pip install pyserial

# Запустить
python3 my_term.py
```

## Требования

- **Python**: 3.8+ (рекомендуется 3.14+)
- **pyserial**: `pip install pyserial`
- **tkinter**: Обычно уже установлен вместе с Python

## Решение проблем

### `ModuleNotFoundError: No module named '_tkinter'`

Эта ошибка возникает когда Python был скомпилирован без поддержки Tkinter (часто встречается с pyenv на macOS).

**Решение 1**: Использовать системный Python (рекомендуется):
```bash
/usr/bin/python3 my_term.py
```

**Решение 2**: Переустановить Python с поддержкой Tkinter (см. "Альтернатива: использование pyenv" выше).

### `ModuleNotFoundError: No module named 'serial'`

Установите pyserial:
```bash
pip install pyserial
```

### Permission denied на `/dev/tty.usb*`

На macOS вам может понадобиться добавить вашего пользователя в группу `dialout` или использовать `sudo` (не рекомендуется).

На Linux:
```bash
sudo usermod -a -G dialout $USER
# Выйти и войти снова в систему
```