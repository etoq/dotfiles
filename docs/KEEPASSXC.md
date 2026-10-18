# KeePassXC: запуск через менеджер пользовательского сеанса

18 октября 2026 прямой запуск /usr/bin/keepassxc воспроизводимо завершался SIGABRT в QDBusConnection/libQt5DBus с assertion dbus_pending_call_block(pending != NULL), до появления окна. Повторилось с временным пустым config, без темы Qt, с GTK3 и без accessibility. Это не подтверждает неисправность базы паролей. Точную причину сбоя взаимодействия с общей шиной не устанавливали отключением защит.

Запуск через systemd user service на той же общей session bus работает: окно KeePassXC появилось, процесс остался active. Для постоянного обхода используются:

- scripts/local-bin/keepassxc → ~/.local/bin/keepassxc;
- configs/applications/org.keepassxc.KeePassXC.desktop → локальное переопределение системного desktop entry.

Launcher выполняет systemd-run --user --collect --service-type=exec --expand-environment=no /usr/bin/keepassxc, передаёт аргументы отдельными argv и текущие DISPLAY/XAUTHORITY. Автозапуск не включает. Другая шина D-Bus не создаётся, AppArmor не отключается, системные библиотеки не заменяются. Бинарник пакета /usr/bin/keepassxc остаётся прежним. Основной процесс поддерживает штатный единственный экземпляр; повторный запуск из меню направляется в существующее окно.

Проверены bash syntax, desktop-file-validate (только подсказка по необязательной дополнительной Categories), запуск launcher и gtk-launch, отсутствие failed user units. Базы не разблокировались и пароли не считывались. Если обход больше не нужен, удалить локальное desktop entry и symlink ~/.local/bin/keepassxc; перед этим проверить прямой запуск после устранения первопричины.
