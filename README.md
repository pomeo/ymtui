# ymtui

> Консольный плеер **Яндекс Музыки**.

[![PyPI](https://img.shields.io/pypi/v/ymtui.svg)](https://pypi.org/project/ymtui/)
[![Python](https://img.shields.io/pypi/pyversions/ymtui.svg)](https://pypi.org/project/ymtui/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

![Скриншот ymtui](https://raw.githubusercontent.com/pomeo/ymtui/master/assets/screenshot.png)

`ymtui` — это терминальный плеер для Яндекс Музыки на [Textual](https://textual.textualize.io/)

## Возможности

- 🌊 **Моя волна** — бесконечное персональное радио с подгрузкой и подстройкой
- ❤️ **Любимое**, 🏆 **Чарт**, 🕘 **История** прослушивания
- ⭐ **Плейлисты дня** (Дежавю, Премьера, Плейлист дня…) из персональной ленты
- ✨ **Новые плейлисты** и 💿 **Новинки** (альбомы)
- 🎼 **Жанры / Настроения / Занятия / Эпохи** — навигация по подборкам
- 📂 **Мои плейлисты**
- 🔎 Поиск треков
- ⏯ Воспроизведение, перемотка (клавишами и кликом по полосе), 🔀 шафл, 🔁 повтор, лайки
- 💾 **Сохранение сессии**: при следующем запуске откроется тот же раздел/плейлист,
  а последний трек подгрузится на сохранённой позиции
- 🎨 Темы и 🌐 **языки интерфейса** (русский / английский), всё сохраняется
- 🎛 **MPRIS**: управление мультимедиа-клавишами и через `playerctl`

## Установка

### 1. Системные зависимости

Для воспроизведения нужен **libmpv**:

```bash
# Debian / Ubuntu
sudo apt install libmpv2        # на старых релизах: libmpv1

# Fedora
sudo dnf install mpv-libs

# Arch
sudo pacman -S mpv
```

### 2. Установка ymtui

Рекомендуемый способ — [pipx](https://pipx.pypa.io/) (изолированно) или
[uv](https://docs.astral.sh/uv/):

```bash
pipx install ymtui
# или
uv tool install ymtui
# или
pip install --user ymtui
```

### 3. (Опционально) Медиа-клавиши и playerctl

Поддержка MPRIS вынесена в отдельную зависимость, т.к. требует системных
библиотек GObject. Если нужны мультимедиа-клавиши / `playerctl`:

```bash
# Debian / Ubuntu — заголовки для сборки PyGObject
sudo apt install libgirepository-2.0-dev gir1.2-glib-2.0 gcc pkg-config python3-dev

pipx install "ymtui[mpris]"     # или uv tool install "ymtui[mpris]"
```

Без этого приложение работает полностью — просто без медиа-клавиш.

## Первый запуск

```bash
ymtui
```

При первом запуске пройдёт авторизация через **OAuth Device Flow**: в терминале
появится ссылка и код — откройте ссылку, введите код, и токен сохранится в
`~/.config/ymtui/config.ini`. Повторно авторизовываться не нужно.
Если получение токена для вашего аккаунта не работает — смотрите [альтернативные способы](https://ym.marshal.dev/token/#implicit-oauth).

> Уже есть токен? Можно вписать его вручную:
> ```ini
> [ymtui]
> token = y0_AgAEA...
> ```

## Управление

| Клавиша | Действие |
|---|---|
| `space` | играть / пауза |
| `enter` | играть выбранный трек |
| `n` / `p` | следующий / предыдущий |
| `< ` / `>` (или `,` / `.`) | перемотка −5с / +5с |
| клик по полосе | перемотка на позицию |
| `l` | лайк / снять лайк |
| `s` | перемешать |
| `r` | повтор |
| `+` / `-` | громче / тише |
| `tab` / `shift+tab` | переключение панелей |
| `↑` / `↓` | движение по списку |
| `/` | поиск |
| `?` | справка |
| `ctrl+p` | настройки (тема, язык, скриншот…) |
| `q` | выход |

## Темы и язык

Нажмите `Ctrl+P` (настройки) → можно сменить **тему** оформления и **язык**
интерфейса (русский / английский). Выбор сохраняется и применяется сразу,
без перезапуска.

## Медиа-клавиши (MPRIS / playerctl)

С установленным extra `[mpris]` плеер виден как `ymtui`:

```bash
playerctl -p ymtui play-pause
playerctl -p ymtui next
playerctl -p ymtui metadata --format '{{artist}} — {{title}}'
```

Можно запускать несколько копий: первая занимает имя `ymtui`, остальные —
`ymtui.instance<PID>`.

## Конфигурация и данные

Всё хранится в `~/.config/ymtui/`:

- `config.ini` — токен авторизации;
- `state.json` — последняя сессия (раздел, трек, позиция, тема, язык).

## Разработка

```bash
git clone https://github.com/pomeo/ymtui
cd ymtui
uv sync                 # или: pip install -e ".[mpris]"
python main.py
```

## Лицензия

[MIT](LICENSE) © Sergey Ovechkin

---

Проект не является официальным продуктом Яндекса. Используйте с собственным
аккаунтом Яндекс Музыки.
