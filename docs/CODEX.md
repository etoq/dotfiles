# Codex · Black Tiffany

Установлен CLI 0.164.0. Тема `black-tiffany` применяется к коду и diff;
фон и прозрачность сохраняются из Kitty. Текущий чат: `/theme` → `black-tiffany`.
Новые запуски получают тему автоматически.

Команды из актуальной документации; доступность зависит от версии и функций.
Фактическое меню установленного клиента открывается вводом `/`.

- Чаты: `/new`, `/clear`, `/resume`, `/fork`, `/rename`, `/archive`, `/delete`, `/export`.
- Контекст: `/compact`, `/recap`, `/mention`, `/ide`, `/cd`, `/pwd`, `/cwd`.
- Работа: `/plan`, `/goal`, `/review`, `/diff`, `/copy`, `/ps`, `/stop`.
- Модель: `/model`, `/fast`, `/status`, `/usage`, `/permissions`, `/approve`.
- Интеграции: `/skills`, `/mcp`, `/apps`, `/plugins`, `/hooks`, `/import`.
- Оформление: `/theme`, `/keymap`, `/vim`, `/statusline`, `/title`, `/tui`, `/raw`, `/pets`, `/pet`.
- Агенты: `/agents`, `/subagents`, `/side`, `/btw`, `/worktree`.
- Служебные: `/init`, `/experimental`, `/memories`, `/debug-config`, `/warnings`, `/daemon`, `/feedback`, `/logout`, `/app`.
- Выход: `/exit`, `/quit`. Windows: `/setup-default-sandbox`.

Бинды:

- `Enter` — отправить; во время работы — направить уточнение.
- `Shift+Enter` — новая строка в поддерживающем терминале.
- `Tab` во время работы — поставить сообщение в очередь.
- `Ctrl+R` — поиск истории ввода.
- `Ctrl+G` — внешний редактор (`VISUAL`/`EDITOR`).
- `Ctrl+O` — копировать последний ответ.
- `Ctrl+L` — очистить экран, сохранив чат.
- `Esc Esc` в пустом вводе — редактировать прошлый запрос с ответвлением.
- `Ctrl+C` — прервать работу; в ожидании может закрывать CLI.
- `@` — выбрать файл; `!команда` — локальная shell-команда.

Локальные настройки Kitty: `Ctrl+V` — текст; `Ctrl+Alt+V` — изображение в Codex.

[Команды](https://learn.chatgpt.com/docs/developer-commands?surface=cli)
[Темы](https://learn.chatgpt.com/docs/cli-customization)
