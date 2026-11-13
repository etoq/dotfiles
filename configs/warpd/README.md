# warpd: стрелка Tiffany

Локальная X11-сборка warpd v1.3.5, база effea40.
`tiffany-cursor.patch` добавляет указатель из Xcursor-темы в normal mode.
Форма, alpha и hotspot сохраняются; тёмная заливка меняется на cursor_color,
светлая обводка остаётся. Обычная системная тема не меняется.

Настройки: cursor_theme: Bibata-Modern-Classic, cursor_theme_size: 24.
Пустой cursor_theme возвращает штатный квадрат warpd.
Тема берётся из ~/.local/share/icons/Bibata-Modern-Classic.
Для прозрачности используется работающий Picom и ARGB visual X11.

Воспроизведение сборки: получить исходники rvaiya/warpd тега v1.3.5,
применить git apply /home/eto/dotfiles/configs/warpd/tiffany-cursor.patch,
затем env CFLAGS=-O2 make -j2 DISABLE_WAYLAND=1.
Дополнительные библиотеки: libXcursor и libXrender.
Бинарник: ~/.local/lib/warpd/warpd, ссылка ~/.local/bin/warpd.
Пробная служба: warpd-trial.service; автозапуск не включён.

## Восстановление после клонирования

Сначала установить build tools, заголовки X11, libXcursor/libXrender
и тему Bibata (общий установщик уже содержит установку темы).
В отдельном каталоге выполнить:

```bash
git clone --branch v1.3.5 --depth 1 https://github.com/rvaiya/warpd.git
cd warpd
git rev-parse HEAD
# Ожидается effea402ec8668bb2bc5c5117800d16d0d9d349a.
git apply "$HOME/dotfiles/configs/warpd/tiffany-cursor.patch"
env CFLAGS=-O2 make -j2 DISABLE_WAYLAND=1
mkdir -p "$HOME/.local/lib/warpd" "$HOME/.local/bin"
install -m 755 bin/warpd "$HOME/.local/lib/warpd/warpd"
ln -s "$HOME/.local/lib/warpd/warpd" "$HOME/.local/bin/warpd"
```

Общий установщик подключает конфиг; бинарник warpd собирается отдельно.
Для пробного запуска без автозапуска:

```bash
systemd-run --user --unit=warpd-trial "$HOME/.local/bin/warpd" -f
```

Alt+Z — управление указателем; Alt+X — метки; Win+Alt+G — сетка; Esc — выход. Caps+J/K (стрелки вниз/вверх)
и e/r — прокрутка. Системный Caps настроен в configs/etc/keyd/default.conf.
Обычная тема указателя не меняется. Для warpd в Picom сохранены исключения
blur, shadow, rounded corners и fading.
Vimium устанавливается вручную из Mozilla Add-ons (vimium-ff).
