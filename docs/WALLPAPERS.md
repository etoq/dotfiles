# Автоматическая смена обоев

Раз в 30 минут пользовательский таймер `wallpaper-rotate.timer` выбирает
следующее изображение Black Tiffany из `~/Images/tiffany-*` (PNG/JPEG/WebP).
Порядок случайный, вся подборка проходит без повторов; на границе двух
кругов одинаковые изображения подряд также исключены. Новые обои
автоматически попадут в следующий полный круг.

`Win+W` переключает вручную через тот же механизм. Вход в Awesome или bspwm
восстанавливает последнюю картинку. В Awesome изменение геометрии мониторов
повторно применяет её вместо возврата к фиксированному фону. Используется
`feh --bg-fill`: изображение заполняет экран с сохранением пропорций.
Экран блокировки не изменяется. Постоянного процесса смены обоев нет,
таймер не будит ноутбук из сна.

Состояние очереди: `~/.local/state/wallpaper/rotation.json`.

```sh
# Следующая картинка
~/bin/random_wallpaper
# Восстановить текущую, не продвигая очередь
~/bin/random_wallpaper --restore
# Посмотреть следующее срабатывание
systemctl --user list-timers wallpaper-rotate.timer
# Остановить автоматическую смену до следующего входа
systemctl --user stop wallpaper-rotate.timer
```

Интервал задаётся в `configs/systemd/user/wallpaper-rotate.timer`:
`OnActiveSec=30min` и `OnUnitActiveSec=30min`. После правки:

```sh
systemctl --user daemon-reload
systemctl --user restart wallpaper-rotate.timer
```
