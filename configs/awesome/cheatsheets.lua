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
sheets.gdb = {
 {'GDB · 1. Запуск и точки', {
  {'file ./program', 'Загрузить программу и символы'}, {'set args аргументы', 'Аргументы запуска'},
  {'start / starti', 'Старт до main / первой инструкции'}, {'b main / b *АДРЕС', 'Точка на функции / адресе'},
  {'info break / delete НОМЕР', 'Список / удалить точку'}, {'disable / enable НОМЕР', 'Отключить / включить точку'},
 }},
 {'GDB · 2. Выполнение', {
  {'r / c', 'Запустить / продолжить'}, {'n / s', 'Шаг по строкам: поверх / внутрь'},
  {'ni / si', 'Шаг по инструкциям: поверх / внутрь'}, {'finish', 'До возврата из функции'},
  {'Ctrl+C', 'Прервать выполнение'}, {'q', 'Выйти из GDB'},
 }},
 {'GDB · 3. Память и регистры', {
  {'info registers', 'Регистры процессора'}, {'p/x ВЫРАЖЕНИЕ', 'Значение в HEX'},
  {'x/16gx $rsp', '16 восьмибайтовых слов стека · x86-64'}, {'x/32bx АДРЕС', '32 байта памяти'},
  {'x/s АДРЕС', 'Строка по адресу'}, {'x/10i $pc', '10 инструкций от текущей'},
 }},
 {'GDB · 4. Функции и стек', {
  {'bt', 'Стек вызовов'}, {'frame НОМЕР / up / down', 'Выбрать стековый кадр'},
  {'info args / info locals', 'Аргументы / локальные переменные'}, {'disassemble /r ИМЯ', 'Инструкции с байтами'},
 }},
 {'PWNDBG · 5. Быстрый анализ', {
  {'context / ctx', 'Сводка текущего состояния'}, {'telescope $rsp 16', 'Разыменовать указатели стека'},
  {'vmmap', 'Карта памяти процесса'}, {'nearpc', 'Инструкции около текущего PC'},
  {'search -t string ТЕКСТ', 'Найти строку в памяти'}, {'checksec', 'Защитные свойства бинарника'},
 }},
 {'GDB · 6. Справка', {
  {'help КОМАНДА', 'Синтаксис команды'}, {'apropos СЛОВО', 'Найти команду по описанию'},
  {'pwndbg ФИЛЬТР', 'Найти команду pwndbg'},
 }},
}
sheets.recli = {
 {'RE CLI · 1. Первичный осмотр', {
  {'file ФАЙЛ', 'Определить формат'}, {'sha256sum ФАЙЛ', 'Вычислить SHA-256'},
  {'strings -a -n 6 ФАЙЛ', 'ASCII-строки от 6 символов'}, {'xxd -g 1 -l 256 ФАЙЛ', 'Первые 256 байт'},
 }},
 {'RE CLI · 2. ELF', {
  {'readelf -h ФАЙЛ', 'Заголовок и архитектура'}, {'readelf -SW ФАЙЛ', 'Секции'},
  {'readelf -lW ФАЙЛ', 'Сегменты и права'}, {'readelf -sW ФАЙЛ', 'Таблицы символов'},
  {'readelf -dW ФАЙЛ', 'Зависимости и dynamic'}, {'readelf -rW ФАЙЛ', 'Релокации'},
 }},
 {'RE CLI · 3. Дизассемблирование', {
  {'objdump -d -M intel ФАЙЛ', 'Код · синтаксис Intel для x86'}, {'objdump -s -j .rodata ФАЙЛ', 'Байты секции .rodata'},
  {'nm -an ФАЙЛ', 'Символы по адресам, если сохранены'},
 }},
 {'RADARE2 · 4. Навигация', {
  {'r2 -A ФАЙЛ', 'Открыть и выполнить статический анализ'}, {'afl', 'Список функций'},
  {'s sym.main / s АДРЕС', 'Перейти к функции / адресу'}, {'pdf', 'Дизассемблировать функцию'},
  {'px 64', '64 байта от текущего смещения'}, {'izz', 'Строки во всём файле'},
 }},
 {'RADARE2 · 5. Связи и помощь', {
  {'axt @ АДРЕС', 'Входящие ссылки на адрес'}, {'agf', 'Граф текущей функции'},
  {'V / VV', 'Визуальный режим / граф'}, {'КОМАНДА?', 'Справка: pdf? / afl? / px?'},
  {'q', 'Выйти из текущего режима / r2'},
 }},
 {'СВОИ · 6. Дополнение', {
  {'workstation-files kind ФАЙЛ', 'Формат + SHA-256 + расширение'}, {'workstation-files bindiff A B', 'Разница байт, строк и ELF-секций'},
  {'workstation-files carve ФАЙЛ', 'Кандидаты встроенных объектов'},
 }},
}
sheets.ghidra = {
 {'GHIDRA · 1. Код и данные', {
  {'C / U', 'Дизассемблировать / убрать разметку'}, {'P / Alt+P', 'Создать / изменить функцию'},
  {'D', 'Данные: byte → word → dword → qword'}, {'A', 'Данные: char → string → unicode'},
  {'O', 'Создать указатель'}, {'Ctrl+Alt+A', 'Патч: Assemble'},
 }},
 {'GHIDRA · 2. Имена и типы', {
  {'N', 'Переименовать символ под курсором'}, {'Y', 'Тип в декомпиляторе'},
  {';', 'Комментарий'}, {'Ctrl+Shift+L', 'Метка операнда'},
  {'Ctrl+Z / Ctrl+Shift+Z', 'Отменить / повторить изменение'},
 }},
 {'GHIDRA · 3. Навигация', {
  {'G', 'Перейти к адресу / метке'}, {'X', 'Ссылки на символ под курсором'},
  {'Alt+← / Alt+→', 'Назад / вперёд по истории'}, {'Ctrl+F6', 'Предыдущая активная панель'},
  {'Ctrl+Shift+F6', 'Предыдущая активная программа'},
 }},
 {'GHIDRA · 4. Декомпилятор и граф', {
  {'F5', 'Открыть декомпилятор'}, {'Ctrl+F5', 'Обновить декомпиляцию'},
  {'Space', 'Listing ↔ Function Graph'}, {'Ctrl+Space', 'Раскрыть данные / переменные в Listing'},
  {'Shift+A', 'Автоанализ'},
 }},
 {'GHIDRA · 5. Поиск', {
  {'Alt+T', 'Поиск текста'}, {'Alt+F3', 'Повторить поиск текста'},
  {'Alt+B', 'Поиск байтов в памяти'}, {'F3 / Shift+F3', 'Поиск памяти: вперёд / назад'},
  {'Shift+F12', 'Defined Strings'},
 }},
 {'GHIDRA · 6. Файлы', {
  {'I / Ctrl+I', 'Импорт файла / открыть файловую систему'}, {'Ctrl+S', 'Сохранить программу'},
  {'Ctrl+Shift+O', 'Экспортировать программу'}, {'Win+F8', 'Эта справка · профиль Linux / IDA'},
 }},
}
local function instance(name,data)
 if M.instances[name] then return M.instances[name] end
 data=data or assert(sheets[name],'Unknown cheat sheet: '..tostring(name))
 local dense=name=='otter' or name=='scripts'
 local widget=popup.widget.new({width=name=='scripts' and 1480 or 1280,height=name=='otter' and 800 or 620,font=dense and 'JetBrainsMono Nerd Font 10.5' or 'JetBrainsMono Nerd Font 11',
  description_font=dense and 'JetBrainsMono Nerd Font 10.5' or 'JetBrainsMono Nerd Font 11',group_margin=20,merge_duplicates=false,
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
 if name=='otter' or name=='scripts' then
  awful.spawn.easy_async({os.getenv('HOME')..'/.local/bin/cheat-data',name},function(out,err,_,code)
   local data=require('dkjson').decode(out)
   if code~=0 or not data then
    require('naughty').notify({title='Справочник',text='Не удалось прочитать данные: '..err})
    return
   end
   M.instances[name]=nil
   instance(name,data):show_help(nil,awful.screen.focused(),{show_awesome_keys=false})
  end)
  return
 end
 return instance(name):show_help(nil,awful.screen.focused(),{show_awesome_keys=false})
end
return M
