# Карта окружения Black Tiffany

Актуализировано 18 октября 2026. Рабочий WM — AwesomeWM с новым Polybar; bspwm сохранён как альтернативный сеанс. `~` — /home/eto. Пользовательские конфиги ниже подключены файлами или каталогами к ~/dotfiles. Некоторые приложения при сохранении через GUI могут заменить symlink обычным файлом: перед следующим коммитом сверять такую копию с источником, сохраняя актуальные пользовательские настройки.

## Интерфейс и управление

| Компонент | Рабочий путь | Источник в dotfiles / назначение |
|---|---|---|
| Общая палитра | ~/.config/tiffany/palette.json | configs/tiffany/palette.json; tiffany-theme / tiffany-reload |
| AwesomeWM | ~/.config/awesome/ | configs/awesome/; rc.lua, theme.lua, ui.lua, navigation.lua |
| Автозапуск Awesome | ~/.local/bin/awesome-session-start | scripts/local-bin/awesome-session-start |
| Альтернативный bspwm | ~/.config/bspwm/bspwmrc | configs/bspwm/ |
| Клавиши bspwm | ~/.config/sxhkd/sxhkdrc | configs/sxhkd/; Awesome использует свои native bindings |
| Polybar | ~/.config/polybar/config.ini | configs/polybar/config.ini; запуск panel-autostart/panel-switch |
| Runtime Polybar в Awesome | /run/user/1000/panel-lab-awesome/polybar.ini | Генерируется panel-switch; редактировать основной конфиг |
| Данные и клики панели | ~/.local/bin/panel-data, panel-action | scripts/local-bin/; музыка закреплена за Yandex Music |
| Рабочие столы Polybar | ~/.local/bin/polybar-workspaces | События Awesome, без периодической задержки переключения |
| Control Deck | ~/.config/panel-lab/dashboard.js и dashboard.css | configs/panel-lab/; Super+Shift+B, звук/яркость/устройства/VM/backup |
| Otter | ~/.config/otter-launcher/config.toml | configs/otter-launcher/; Super+D |
| Команды Otter | ~/.local/bin/otter-tools, otter-apps, otter-new-note и другие otter-* | scripts/local-bin/ |
| Оформление окна Otter | ~/.config/kitty/otter.conf | configs/kitty/otter.conf; фиксированные пользовательские размеры |
| Picom | ~/.config/picom/picom.conf | configs/picom/picom.conf; старый bspwm/picom_configurations/1.conf — ссылка на него же |
| Dunst | ~/.config/dunst/dunstrc | configs/dunst/dunstrc |
| Rofi | ~/.config/rofi/ | configs/rofi/; используется для отдельных функций/emoji |
| Обои | ~/Images | Изображения и исходники темы в dotfiles/Images; дополнительные личные файлы могут храниться отдельно |

## Терминал и приложения

| Программа | Конфигурация | Данные / замечания |
|---|---|---|
| Kitty | ~/.config/kitty/kitty.conf | Источник configs/kitty/; текущая opacity 0.7 сохранена |
| Fish | ~/.config/fish/config.fish, tiffany.fish | configs/fish/; fish_variables — локальное универсальное состояние, не версионируется |
| Neovim | ~/.config/nvim/ | configs/nvim/; lockfile сохраняет текущие версии плагинов |
| Yazi | ~/.config/yazi/{yazi,keymap,theme,package}.toml и init.lua | configs/yazi/; ассоциации открытия также в mimeapps.list |
| Btop | ~/.config/btop/btop.conf | configs/btop/; Black Tiffany theme |
| Calcurse | ~/.config/calcurse/{conf,keys} | configs/calcurse/; календарные записи/задачи — отдельные пользовательские данные |
| Zathura | ~/.config/zathura/zathurarc | configs/zathura/ |
| Flameshot | ~/.config/flameshot/flameshot.ini | configs/flameshot/; текущий путь сохранения ~/Downloads |
| Пипетка | ~/bin/xcolor-pick | scripts/bin/xcolor-pick; Super+Shift+X |
| GTK3 / GTK4 | ~/.config/gtk-{3,4}.0/{settings.ini,gtk.css} | configs/gtk-3.0/, configs/gtk-4.0/ и themes/Black-Tiffany |
| XSettings / Xresources | ~/.config/xsettingsd/xsettingsd.conf, ~/.Xresources | configs/xsettingsd/, configs/Xresources |
| Qt | ~/.config/environment.d/60-black-tiffany.conf | configs/environment.d/; xcb + gtk3 platform theme |
| Ассоциации файлов | ~/.config/mimeapps.list | configs/mimeapps.list; локальные desktop entries в ~/.local/share/applications |
| KeePassXC | ~/.config/keepassxc/ | Штатный /usr/bin/keepassxc; приватные настройки/базы не публикуются, docs/KEEPASSXC.md |
| Ghidra | ~/.config/ghidra/, ~/.local/share/ghidra/ | Тема themes/Ghidra/BlackTiffany.theme; проекты хранятся отдельно |
| Obsidian | ~/Documents/obsidian/ | Пользовательский vault; настройки каждого vault в его .obsidian/ |
| Zen | ~/.config/zen/ | Приватный профиль, не переносить в публичный Git |
| AyuGram | ~/.local/share/AyuGramDesktop/ | Приватные данные; launcher ~/.local/bin/AyuGram |
| Yandex Music | ~/.config/YandexMusic/ | Приватный профиль; MPRIS-модуль configs/panel-lab/yandex_media.py |
| Wispr Flow | ~/.config/Wispr Flow/ | Приватный профиль; autostart и команда wf в Otter |
| EasyEffects | ~/.config/easyeffects/ | Локальная база параметров db/; запуск --service-mode |
| Throne | ~/.config/Throne/, ~/.config/systemd/user/throne.service | Приватные профили прокси; не коммитить URI/ключи |

## Системная часть Arch

| Назначение | Рабочие файлы / службы | Где сохранено |
|---|---|---|
| Ethernet/Wi-Fi | NetworkManager; iwd может обслуживать backend Wi-Fi | Секретные connection profiles вне публичного Git |
| Старый br0/networkd | br0 удалён, networkd/socket activation отключены | Прежние файлы в /var/backups/workstation-audit-* |
| Firewall | /etc/nftables.conf | configs/etc/nftables.conf; отдельные таблицы Throne/libvirt не очищать |
| Вентиляторы | /etc/thinkfan.conf, thinkfan-normal.conf, thinkfan-silent.conf | configs/etc/; thinkfan.service, текущая задержка старта 5 секунд сохранена |
| Питание | /etc/tlp.conf | configs/etc/tlp.conf; tlp.service |
| NVIDIA / сон | /etc/modprobe.d/, /etc/workstation/nvidia-sleep-mode | configs/etc/ и scripts/system/; рабочая ветка 470, callback сна |
| Initramfs / загрузчик | /etc/mkinitcpio.conf, /etc/default/grub | configs/etc/; machine-specific UUID, не переносить на другой диск вслепую |
| SDDM | /etc/sddm.conf, /usr/share/sddm/themes/black-tiffany/ | configs/etc/sddm.conf и themes/sddm/ |
| SMART | /etc/smartd.conf, smartd.service | configs/etc/smartd.conf; scripts/system/workstation-health-notify |
| Btrfs scrub | btrfs-scrub@-.timer/service | configs/etc/systemd/system/btrfs-scrub@-.service.d/; ежемесячно |
| TRIM | fstrim.timer выключен; LUKS discard не разрешён | Политика оставлена без изменений |
| Пакетные обновления | ~/.local/bin/sys-update, verify-kernel-stack | scripts/local-bin/; логи ~/.local/state/workstation-updates/ |
| Локальные снимки | Snapper root | /etc/snapper/configs/root; не замена внешнему backup |

Системные файлы /etc являются управляемыми копиями, а не symlink в HOME. Их изменения требуют root и отдельного применения. Полный восстановитель restore-system.sh по умолчанию только проверяет комплектность; --apply на рабочем сеансе без причины не запускать.

## Резервирование и отчёты

- План Proton: ~/.config/workstation-backup/plan.json (0600); официальный клиент ~/.local/bin/proton-drive. Секреты сессии — OS keychain.
- Ручная копия: workstation-backup --run-once. Без параметров — только показать план. Автоматического расписания нет.
- Последний подтверждённый результат и манифесты: ~/.local/state/workstation-backup/ (0700). Первая копия полностью проверена обратным скачиванием и восстановлением.
- Инструкция: docs/PROTON-BACKUP.md. Backup пользовательских папок не включает всё HOME, весь /etc и диски VM.
- Логи и резервные файлы текущего ремонта: ~/Documents/Workstation/2026-10-18/system-repair/.
- Завершённые одноразовые helpers: system-repair/retired-helpers/. Рабочие команды обновления, проверки и backup остаются в ~/.local/bin.
- Исходный аудит: Documents/Workstation/2026-10-18/system-audit/REPORT.md; фактически выполненные изменения — docs/WORKSTATION-2026-10-18.md.

После правок конфигурации: git diff --check; для Awesome — awesome -k. git status должен показывать осмысленные пользовательские правки. Ничего автоматически не публикуется и не отправляется в Git remote.

Защита очереди Wispr Flow: `~/.local/bin/wispr-a11y-guard` и `~/.config/systemd/user/wispr-a11y-guard.{service,timer}`; источники в scripts/local-bin и configs/systemd/user. Проверяет только счётчики AT-SPI; см. docs/KEEPASSXC.md.
