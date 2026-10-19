# Карта окружения Black Tiffany

Актуализировано 19 октября 2026. Рабочий WM — AwesomeWM с новым Polybar; bspwm сохранён как альтернативный сеанс. `~` — /home/eto. Пользовательские конфиги ниже подключены файлами или каталогами к ~/dotfiles. Некоторые приложения при сохранении через GUI могут заменить symlink обычным файлом: перед следующим коммитом сверять такую копию с источником, сохраняя актуальные пользовательские настройки.

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
| Control Deck | ~/.config/panel-lab/dashboard.js и dashboard.css | configs/panel-lab/; Super+Shift+B, звук/яркость/устройства/VM; Last Backup: DD:MM:YYYY без подсказок |
| Otter | ~/.config/otter-launcher/config.toml | configs/otter-launcher/; Super+D |
| Команды Otter | ~/.local/bin/otter-tools, otter-apps, otter-new-note и другие otter-* | scripts/local-bin/ |
| Оформление окна Otter | ~/.config/kitty/otter.conf | configs/kitty/otter.conf; фиксированные пользовательские размеры |
| Picom | ~/.config/picom/picom.conf | configs/picom/picom.conf; старый bspwm/picom_configurations/1.conf — ссылка на него же |
| Dunst | ~/.config/dunst/dunstrc | configs/dunst/dunstrc |
| Rofi | ~/.config/rofi/ | configs/rofi/; используется для отдельных функций/emoji |
| Обои | ~/Images | Личная коллекция; установщик добавляет только текущие обои tiffany-re-37-ghidra-neon-emblem.png. Остальная галерея репозитория не навязывается |
| Блокировка | ~/Images/system/lockscreen.png; ~/.config/betterlockscreen/betterlockscreenrc | Обсидиановая гидра Black Tiffany; кэш betterlockscreen, все способы блокировки используют dimblur; docs/LOCKSCREEN.md |
| Бездействие | user idle-screen-lock.service; ~/.local/bin/idle-screen-lock | xss-lock, 600 секунд, блокировка и гашение монитора без suspend; docs/IDLE-LOCK.md |

## Терминал и приложения

| Программа | Конфигурация | Данные / замечания |
|---|---|---|
| Kitty | ~/.config/kitty/kitty.conf | Источник configs/kitty/; текущая opacity 0.7 сохранена |
| Fish | ~/.config/fish/config.fish, tiffany.fish | configs/fish/; fish_variables — локальное универсальное состояние, не версионируется |
| LSD / ls | ~/.config/lsd/config.yaml и colors.yaml | Палитра Black Tiffany, color.theme: custom; устаревший themes/ удалён из рабочего конфига |
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
| Wispr Flow | ~/.config/Wispr Flow/ | Приватный профиль; autostart с --hidden, ручная команда wf; wrapper wispr-flow сохраняет WISPR_DISABLE_GPU=1 |
| EasyEffects | ~/.config/easyeffects/ | Локальная база параметров db/; user-служба easyeffects.service, --service-mode --hide-window |
| Throne | ~/.config/Throne/, ~/.config/systemd/user/throne.service | Приватные профили прокси; не коммитить URI/ключи |

## Системная часть Arch

| Назначение | Рабочие файлы / службы | Где сохранено |
|---|---|---|
| Ethernet/Wi-Fi | NetworkManager; iwd может обслуживать backend Wi-Fi | Секретные connection profiles вне публичного Git |
| Старый br0/networkd | br0 удалён, networkd/socket activation отключены | Прежние файлы в /var/backups/workstation-audit-* |
| Firewall | /etc/nftables.conf | configs/etc/nftables.conf; отдельные таблицы Throne/libvirt не очищать |
| Вентиляторы | /etc/thinkfan.conf, thinkfan-normal.conf, thinkfan-silent.conf | configs/etc/; thinkfan.service и scripts/system/thinkfan-wait-ready: ожидание датчиков вместо фиксированных 5 секунд |
| Питание | /etc/tlp.conf | configs/etc/tlp.conf; tlp.service |
| NVIDIA / сон | /etc/modprobe.d/, /etc/workstation/nvidia-sleep-mode | configs/etc/ и scripts/system/; 580.178.04, preserve-vram, /var/tmp, специальные службы сна и поздняя загрузка NVIDIA; docs/NVIDIA-RECOVERY.md |
| Initramfs / загрузчик | /etc/mkinitcpio.conf, /etc/default/grub | configs/etc/; machine-specific UUID, не переносить на другой диск вслепую |
| SDDM | /etc/sddm.conf, /usr/share/sddm/themes/black-tiffany/ | configs/etc/sddm.conf и themes/sddm/ |
| SMART | /etc/smartd.conf, smartd.service | configs/etc/smartd.conf; scripts/system/workstation-health-notify |
| Btrfs scrub | btrfs-scrub@-.timer/service | configs/etc/systemd/system/btrfs-scrub@-.service.d/; ежемесячно |
| TRIM | fstrim.timer enabled/active; cryptroot:allow-discards | Недельный fstrim только /, nodiscard в fstab; /vms не менялся; docs/STORAGE-AND-BOOT.md |
| Пакетные обновления | ~/.local/bin/sys-update, verify-kernel-stack | scripts/local-bin/; логи ~/.local/state/workstation-updates/ |
| Локальные снимки | Snapper root | /etc/snapper/configs/root; не замена внешнему backup |

Системные файлы /etc являются управляемыми копиями, а не symlink в HOME. Их изменения требуют root и отдельного применения. Полный восстановитель restore-system.sh по умолчанию только проверяет комплектность; --apply на рабочем сеансе без причины не запускать.

## Резервирование и отчёты

- План Proton: ~/.config/workstation-backup/plan.json (0600); официальный клиент ~/.local/bin/proton-drive. Секреты сессии — OS keychain.
- Ручная копия: workstation-backup --run-once. Без параметров — только показать план. Таймеры: workstation-backup-full.timer (воскресенье 20:00), workstation-backup-keepass.timer (ежедневно 19:00).
- Последний подтверждённый результат и манифесты: ~/.local/state/workstation-backup/ (0700). Каждая успешная версия проверяется обратным скачиванием и восстановлением; хранится одна полная и до 14 разных дневных версий KeePassXC.
- Инструкция: docs/PROTON-BACKUP.md. Backup пользовательских папок не включает всё HOME, весь /etc и диски VM.
- Логи и резервные файлы текущего ремонта: ~/Documents/Workstation/2026-10-18/system-repair/.
- Завершённые одноразовые helpers: system-repair/retired-helpers/. Рабочие команды обновления, проверки и backup остаются в ~/.local/bin.
- Исходный аудит: Documents/Workstation/2026-10-18/system-audit/REPORT.md; фактически выполненные изменения — docs/WORKSTATION-2026-10-18.md.

После правок конфигурации: git diff --check; для Awesome — awesome -k. git status должен показывать осмысленные пользовательские правки. Ничего автоматически не публикуется и не отправляется в Git remote.

Защита очереди Wispr Flow: `~/.local/bin/wispr-a11y-guard` и `~/.config/systemd/user/wispr-a11y-guard.{service,timer}`; источники в scripts/local-bin и configs/systemd/user. Проверяет только счётчики AT-SPI; см. docs/KEEPASSXC.md.


## Сверка и установщик

`bash ~/dotfiles/install.sh --check` — только сравнение управляемых пользовательских
файлов, без sudo, сети и изменений. Обычная совпадающая копия допустима;
посторонние личные файлы в каталогах не удаляются. JSON-отчёт:
`python ~/dotfiles/scripts/maintenance/audit-dotfiles.py --json`.

Режимы «только конфиги» и «только скрипты» не требуют sudo. Общий установщик
не меняет ветку NVIDIA; восстановитель системной части требует уже установленную
580. Нативные системные файлы являются копиями, не ссылками в HOME.
Текущие списки пакетов — docs/packages-explicit.txt и packages-aur.txt;
это снимки состояния, а не команды повторной установки всего списка.


## Дополнение: выбранные утилиты и страница состояния

| Компонент | Путь / управление |
|---|---|
| Состояние обслуживания | Control Deck → Состояние; ~/.local/bin/workstation-status |
| Размер Proton | ~/.local/bin/proton-quota; proton-quota.timer; приватный quota.json рядом со статусом backup |
| Снимок SMART/scrub | /var/lib/workstation-health/status.json; root workstation-health-status.timer включён, снимок раз в 6 часов |
| ImHex | ~/.local/bin/imhex → ~/.local/opt/imhex/1.38.1/squashfs-root/AppRun; локальный desktop entry |
| Bibata | ~/.local/share/icons/Bibata-Modern-Classic; GTK/Xresources/xsettingsd; размер 24 |
| udiskie | ~/.config/udiskie/config.yml; user udiskie.service, automount выключен |
| bpftrace | /usr/bin/bpftrace установлен и проверен; отдельные программы трассировки по задаче |

Состояние применения и команда системного шага — [DESKTOP-ENHANCEMENTS.md](DESKTOP-ENHANCEMENTS.md).
