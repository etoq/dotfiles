-- Curated from this workstation's Neovim, Fish, Kitty and Yazi configuration.
-- Uses the native Win+F1 renderer, with independent app-only widgets.
local awful = require('awful')
local popup = require('awful.hotkeys_popup')
local escape = require('gears.string').xml_escape
local M = { instances = {} }
local sheets = {
 nvim = {
  {'NEOVIM · 1. Режимы и правка', {
   {'i / a', 'Ввод перед / после курсора'}, {'Esc', 'Обычный режим'},
   {'v / V', 'Выделить символы / строки'}, {'u / Ctrl+R', 'Отменить / повторить'},
   {'dd / yy / p', 'Вырезать / копировать / вставить'}, {'gcc / gc', 'Комментарий строки / выделения'},
  }},
  {'NEOVIM · 2. Сохранение и поиск', {
   {'Ctrl+S', 'Сохранить · normal и insert'}, {'Ctrl+Q', 'Закрыть текущий файл'},
   {'Ctrl+A', 'Скопировать весь файл в буфер ОС'}, {'/текст → Enter', 'Найти в текущем файле'},
   {'n / N', 'Следующее / предыдущее совпадение'}, {'gg / G', 'Начало / конец файла'},
  }},
  {'NEOVIM · 3. Пробел — Leader', {
   {'Пробел ff', 'Поиск файлов · Telescope'}, {'Пробел ft', 'Поиск текста в проекте'},
   {'Пробел fb', 'Выбрать открытый буфер'}, {'Пробел fh', 'Поиск по справке Neovim'},
   {'Пробел gs', 'Изменения Git · Telescope'}, {'Пробел h', 'Включить / выключить HEX'},
  }},
  {'NEOVIM · 4. Буферы и вкладки', {
   {'Tab / Shift+Tab', 'Следующий / предыдущий буфер'}, {'Ctrl+L', 'Закрыть остальные буферы'},
   {'Пробел tn', 'Новая вкладка'}, {'Пробел j / k', 'Следующая / предыдущая вкладка'},
   {'Пробел tw', 'Закрыть вкладку / выйти'}, {'Ctrl+W h/j/k/l', 'Перейти между сплитами'},
   {'Пробел wc', 'Закрыть текущий сплит'},
  }},
  {'NEOVIM · 5. Код и отладка', {
   {'F4 / F5', 'Запустить код / закрыть запуск'}, {'F9', 'Поставить / убрать breakpoint'},
   {'F10 / F11', 'Шаг поверх / внутрь'}, {'F12', 'Начать / продолжить отладку'},
   {'Esc · в терминале', 'Выйти из режима ввода терминала'},
  }},
  {'NEOVIM · 6. Автодополнение', {
   {'Ctrl+Space', 'Показать варианты'}, {'Tab / Shift+Tab · insert', 'Следующий / предыдущий вариант'},
   {'Enter · insert', 'Принять вариант'}, {'Ctrl+E · insert', 'Закрыть дополнение'},
  }},
 },
 terminal = {
  {'FISH · 1. Ввод и поиск', {
   {'Ctrl+R', 'История команд через fzf'}, {'Ctrl+T', 'Найти файл через fzf'},
   {'Alt+C', 'Выбрать папку через fzf'}, {'Tab / Shift+Tab', 'Дополнение / выбор через fzf'},
   {'→ / Ctrl+F', 'Принять подсказку справа'}, {'Ctrl+U', 'Удалить ввод до курсора'},
   {'Ctrl+C', 'Отменить ввод / команду'},
  }},
  {'FISH · 2. Папки и файлы', {
   {'.. / ... / h', 'Выше / на два уровня / домой'}, {'z имя / zi', 'Папка по истории / выбрать'},
   {'ls / ll / la', 'Список / подробно / скрытые'}, {'lt', 'Дерево файлов · lsd'},
   {'cat / catp', 'bat с оформлением / без рамки'}, {'find', 'Быстрый поиск · fd'},
   {'rm', 'Переместить в корзину · rmtrash'}, {'n файл / m файл', 'Открыть в Neovim'},
  }},
  {'FISH · 3. Git', {
   {'gs', 'Состояние репозитория'}, {'ga файл', 'Добавить файл в индекс'},
   {'gc "сообщение"', 'Создать коммит'}, {'gp', 'Отправить в удалённый репозиторий'},
   {'gl', 'Короткая история с графом'},
  }},
  {'FISH · 4. Система', {
   {'update', 'Новости Arch → pacman -Syu'}, {'install / search', 'Установить / найти пакет'},
   {'snaps / dkms-check', 'Снимки Snapper / статус DKMS'}, {'df / top', 'Диски · duf / ресурсы · btop'},
   {'ports / localip', 'Сокеты / локальные адреса'}, {'fan-toggle', 'Тихий ↔ обычный Thinkfan'},
   {'reload', 'Перечитать config.fish'},
  }},
  {'KITTY · 5. Буфер и вкладки', {
   {'Ctrl+Shift+C / V', 'Копировать / вставить'}, {'Ctrl+Shift+T', 'Новая вкладка Kitty'},
   {'Ctrl+Shift+← / →', 'Предыдущая / следующая вкладка'}, {'Ctrl+Shift+Q', 'Закрыть вкладку Kitty'},
   {'Ctrl+Shift+W', 'Закрыть текущее окно Kitty'},
  }},
  {'KITTY · 6. Просмотр', {
   {'Ctrl+Shift+H', 'Открыть историю вывода в pager'}, {'Ctrl+Shift+PgUp / PgDn', 'Прокрутить на страницу'},
   {'Ctrl+Shift+Plus / Minus', 'Увеличить / уменьшить шрифт'}, {'Ctrl+Shift+Backspace', 'Вернуть размер шрифта'},
  }},
 },
 yazi = {
  {'YAZI · 1. Навигация', {
   {'h / j / k / l', 'Родитель / вниз / вверх / войти'}, {'H / L', 'Назад / вперёд по истории'},
   {'gg / G', 'Первый / последний файл'}, {'Ctrl+U / Ctrl+D', 'Половина страницы вверх / вниз'},
   {'gh / gd / gc', 'Домой / Downloads / .config'}, {'z / Z', 'Переход через fzf / zoxide'},
  }},
  {'YAZI · 2. Открытие и поиск', {
   {'Enter', 'Открыть файл под курсором'}, {'o / O', 'Открыть выбранные / выбрать чем'},
   {'s / S', 'Поиск по имени / содержимому'}, {'f', 'Фильтр текущей папки'},
   {'/ → n / N', 'Найти → следующее / предыдущее'}, {'.', 'Показать / скрыть скрытые файлы'},
   {'Ctrl+S', 'Отменить поиск'},
  }},
  {'YAZI · 3. Выделение и файлы', {
   {'Space', 'Выбрать файл и перейти ниже'}, {'v / V', 'Выделять / снимать выделение'},
   {'Ctrl+A / Ctrl+R', 'Выбрать всё / инвертировать'}, {'y / x → p', 'Копировать / вырезать → вставить'},
   {'Y / X', 'Отменить копирование / вырезание'}, {'a', 'Создать файл; имя с / — папка'},
   {'r', 'Переименовать файл'}, {'d / D', 'Корзина / удалить навсегда'},
  }},
  {'YAZI · 4. Пути и сортировка', {
   {'cc / cd', 'Скопировать путь файла / папки'}, {'cf / cn', 'Имя файла / имя без расширения'},
   {',s / ,S', 'Размер: по возрастанию / убыванию'}, {',m / ,M', 'Дата изменения: прямо / обратно'},
   {'ms / mp', 'Показать размеры / права'},
  }},
  {'YAZI · 5. Вкладки и просмотр', {
   {'t', 'Новая вкладка в текущей папке'}, {'1…9 / [ / ]', 'Выбрать вкладку / предыдущая / следующая'},
   {'Ctrl+C', 'Закрыть вкладку; последняя — выход'}, {'Tab', 'Подробности файла · spot'},
   {'J / K', 'Прокрутка предпросмотра'}, {'w', 'Очередь фоновых операций'},
   {'q / Esc', 'Выход / отменить выделение'}, {'F1', 'Полная встроенная справка'},
  }},
 },
}
local function instance(name)
 if M.instances[name] then return M.instances[name] end
 local data=assert(sheets[name],'Unknown cheat sheet: '..tostring(name))
 local widget=popup.widget.new({width=1280,height=620,font='JetBrainsMono Nerd Font 11',
  description_font='JetBrainsMono Nerd Font 11',group_margin=20,merge_duplicates=false,
  bg='#080D10',fg='#C5D6D8',border_color='#0ABAB5',border_width=1,
  modifiers_fg='#0ABAB5',label_bg='#0ABAB5',label_fg='#080D10'})
 -- App sheets contain only curated rows, independent of global bindings/client class.
 widget._import_awful_keys=function()end
 local groups={}
 for _,section in ipairs(data)do
  local bindings={}
  for _,row in ipairs(section[2])do
   bindings[#bindings+1]={modifiers={},keys={['<span foreground="#4DDDD5">'..escape(row[1])..'</span>']=escape(row[2])}}
  end
  groups[section[1]]=bindings
  widget:add_group_rules(section[1],{color='#0ABAB5'})
 end
 widget:add_hotkeys(groups)
 M.instances[name]=widget
 return widget
end
function M.show(name)
 return instance(name):show_help(nil,awful.screen.focused(),{show_awesome_keys=false})
end
return M
