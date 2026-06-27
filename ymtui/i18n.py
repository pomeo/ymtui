"""Tiny i18n layer.

Adding a new language is just adding a dict to ``TRANSLATIONS`` with the same
keys (missing keys gracefully fall back to English, then to the key itself).
"""
from __future__ import annotations

LANGUAGE_NAMES: dict[str, str] = {
    'en': 'English',
    'ru': 'Русский',
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    'en': {
        # panel / chrome
        'panel.search': 'Search',
        'panel.help': 'Help',
        'panel.library': 'Library',
        'panel.songs': 'Songs',
        'col.title': 'Title',
        'col.artist': 'Artist',
        'col.album': 'Album',
        'col.time': 'Time',
        'hint.help': 'Type  ?',
        'search.placeholder': 'Search tracks…',
        # library categories
        'cat.wave': 'Wave',
        'cat.liked': 'Liked Songs',
        'cat.chart': 'Chart',
        'cat.history': 'History',
        'cat.daily': 'Daily',
        'cat.new-playlists': 'New playlists',
        'cat.new-releases': 'New releases',
        'cat.my-playlists': 'My playlists',
        'cat.genres': 'Genres',
        'cat.moods': 'Moods',
        'cat.activities': 'Activities',
        'cat.eras': 'Eras',
        # collection panel title for user playlists
        'coll.my-playlists': 'Playlists',
        # songs panel titles
        'songs.liked': 'Liked Songs',
        'songs.chart': 'Chart',
        'songs.history': 'History',
        'songs.wave': 'Wave',
        'songs.search': 'Search: {q}',
        # now playing
        'np.nothing': 'Nothing playing',
        'np.playing': 'Playing',
        'np.shuffle': 'Shuffle',
        'np.repeat': 'Repeat',
        'np.volume': 'Volume',
        'np.on': 'On',
        'np.off': 'Off',
        # footer / key hints
        'bind.play': 'Play/Pause',
        'bind.next': 'Next',
        'bind.prev': 'Prev',
        'bind.like': 'Like',
        'bind.shuffle': 'Shuffle',
        'bind.repeat': 'Repeat',
        'bind.seekback': '« 5s',
        'bind.seekfwd': '5s »',
        'bind.volup': 'Vol+',
        'bind.voldown': 'Vol−',
        'bind.search': 'Search',
        'bind.help': 'Help',
        'bind.quit': 'Quit',
        'bind.palette': 'settings',
        # help modal
        'help.title': 'Help',
        'help.body': """\
[b]Playback[/b]
  space      play / pause
  enter      play selected track
  n / p      next / previous track
  < / >      seek -5s / +5s  (or , / .)
  click bar  seek to position
  l          like / unlike current track
  s          toggle shuffle
  r          toggle repeat
  + / -      volume up / down

[b]Navigation[/b]
  tab        next panel
  shift+tab  previous panel
  ↑ / ↓      move in list / table
  /          focus search

[b]Command palette[/b]
  ctrl+p     open the palette — themes, language,
             save screenshot, quit, etc.
             type to filter · ↑/↓ move · enter run

[b]Other[/b]
  ?          this help
  q          quit

[dim]press  ?  ·  esc  ·  q  to close[/dim]""",
        # command palette
        'cmd.language': 'Language: {name}',
        'cmd.language.help': 'Switch the interface language',
        'cmd.cover': 'Album cover: {state}',
        'cmd.cover.help': 'Show/hide album art in the player',
        'cover.missing': 'Install ymtui[cover] for album art',
    },
    'ru': {
        'panel.search': 'Поиск',
        'panel.help': 'Помощь',
        'panel.library': 'Библиотека',
        'panel.songs': 'Треки',
        'col.title': 'Название',
        'col.artist': 'Исполнитель',
        'col.album': 'Альбом',
        'col.time': 'Время',
        'hint.help': 'Нажми  ?',
        'search.placeholder': 'Поиск треков…',
        'cat.wave': 'Моя волна',
        'cat.liked': 'Любимое',
        'cat.chart': 'Чарт',
        'cat.history': 'История',
        'cat.daily': 'Плейлисты дня',
        'cat.new-playlists': 'Новые плейлисты',
        'cat.new-releases': 'Новинки',
        'cat.my-playlists': 'Мои плейлисты',
        'cat.genres': 'Жанры',
        'cat.moods': 'Настроения',
        'cat.activities': 'Занятия',
        'cat.eras': 'Эпохи',
        'coll.my-playlists': 'Плейлисты',
        'songs.liked': 'Любимое',
        'songs.chart': 'Чарт',
        'songs.history': 'История',
        'songs.wave': 'Моя волна',
        'songs.search': 'Поиск: {q}',
        'np.nothing': 'Ничего не играет',
        'np.playing': 'Играет',
        'np.shuffle': 'Перемешать',
        'np.repeat': 'Повтор',
        'np.volume': 'Громкость',
        'np.on': 'Вкл',
        'np.off': 'Выкл',
        'bind.play': 'Воспр/Пауза',
        'bind.next': 'Дальше',
        'bind.prev': 'Назад',
        'bind.like': 'Лайк',
        'bind.shuffle': 'Перемешать',
        'bind.repeat': 'Повтор',
        'bind.seekback': '« 5с',
        'bind.seekfwd': '5с »',
        'bind.volup': 'Громк+',
        'bind.voldown': 'Громк−',
        'bind.search': 'Поиск',
        'bind.help': 'Помощь',
        'bind.quit': 'Выход',
        'bind.palette': 'настройки',
        'help.title': 'Помощь',
        'help.body': """\
[b]Воспроизведение[/b]
  space      играть / пауза
  enter      играть выбранный трек
  n / p      следующий / предыдущий
  < / >      перемотка -5с / +5с  (или , / .)
  клик       перемотка по полосе
  l          лайк текущего трека
  s          перемешать
  r          повтор
  + / -      громче / тише

[b]Навигация[/b]
  tab        следующая панель
  shift+tab  предыдущая панель
  ↑ / ↓      движение по списку / таблице
  /          фокус на поиск

[b]Палитра команд[/b]
  ctrl+p     открыть палитру — тема, язык,
             скриншот, выход и т.д.
             печатай для фильтра · ↑/↓ · enter

[b]Прочее[/b]
  ?          эта справка
  q          выход

[dim]закрыть:  ?  ·  esc  ·  q[/dim]""",
        'cmd.language': 'Язык: {name}',
        'cmd.language.help': 'Сменить язык интерфейса',
        'cmd.cover': 'Обложка альбома: {state}',
        'cmd.cover.help': 'Показывать/скрывать обложку в плеере',
        'cover.missing': 'Установите ymtui[cover] для обложек',
    },
}

_current = 'en'


def set_language(lang: str) -> None:
    global _current
    if lang in TRANSLATIONS:
        _current = lang


def get_language() -> str:
    return _current


def available_languages() -> list[str]:
    return list(TRANSLATIONS)


def t(key: str, **kwargs) -> str:
    table = TRANSLATIONS.get(_current, {})
    text = table.get(key)
    if text is None:
        text = TRANSLATIONS['en'].get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text
