# Экран блокировки Black Tiffany

19 октября 2026 сгенерирован и установлен новый фон с обсидиановой гидрой.
Использован встроенный image_gen через навык imagegen; без CLI/API-ключей.
Вдохновение — Images/tiffany-re-37-ghidra-neon-emblem.png и
Images/tiffany-re-01-ghidra-obsidian.png из личной коллекции.

- Рабочий фон: ~/Images/system/lockscreen.png, копия в Images/system/lockscreen.png.
- Установленный PNG: 3840×2160. После улучшения деталей через image_gen
  получен PNG 1672×941: запрос точного 4K генератор не выполнил. Финальный
  размер подготовлен Lanczos-масштабированием с минимальной центральной
  подрезкой до 16:9. Это апскейл, а не исходная генерация 4K.
  Кэш betterlockscreen соответствует текущему экрану 1920×1080.
- Конфигурация: configs/betterlockscreen/betterlockscreenrc, ссылка в ~/.config/.
- Палитра Black Tiffany; часы и дата справа от центра, в тёмной зоне.
- Лёгкое затемнение 12%, blur ослаблен с 0.3 до 0.1; существующие команды dimblur сохранены.
- Тема применяется при следующей блокировке. Рабочий стол и SDDM не заменялись.
- Прежний фон и кэш: ~/.local/state/lockscreen-backup/20261019-144040/.
- Кэш обновлён без блокировки текущего сеанса. Реальный i3lock отрисован
  на отдельном Xvfb; проверены шрифт, часы, дата и расположение элементов.
  Пароль/разблокировка этим визуальным тестом не проверялись.
- Установщик подключает фон/конфиг и пересобирает кэш при доступном DISPLAY.

Повторная сборка кэша после изменения разрешения:

```bash
betterlockscreen -u ~/Images/system/lockscreen.png --fx dim,dimblur
```

## Промпт генерации

Use case: stylized-concept. Generate ONE original premium Linux lock-screen wallpaper, wide 16:9 landscape, ideally 3840x2160. Inspired by an existing personal Black Tiffany wallpaper collection of elegant three-headed Ghidra hydras, black obsidian sculpture, fine teal neon linework, binary structures and reverse-engineering imagery. This is a new composition, not an edit. Scene: a monumental but restrained three-headed hydra forged from layered matte obsidian and graphite, with exquisitely fine Tiffany turquoise inlaid veins and faint circuit / control-flow engravings, emerging from deep near-black atmospheric space. Composition deliberately designed for a functional lock screen: sculptural hydra occupies the LEFT THIRD, heads and fine curving necks elegantly silhouetted, looking into the scene; a very faint arc of fragmented disassembly/callgraph-like geometric lines drifts toward the far right edge. Keep the broad central zone (40%-72% width, 25%-85% height) almost empty, dark and low contrast so an actual clock and circular password indicator remain legible. Quiet cinematic lighting, soft thin rim lights, luxurious detailed dark materials, understated atmospheric depth, restrained teal highlights, mostly near black. Palette background #080D10, shadow #101B20, subtle secondary #183039, controlled accents #0ABAB5 and #4DDDD5, very rare tiny #A3F0E7 highlights. Tasteful, beautiful, calm, no eye-searing neon, no purple, no magenta, no green, no bright white, no other accent colors. NO text, NO letters, NO numbers, NO logos, NO watermarks, NO mockup clock, NO UI, NO password fields. Edge-to-edge finished wallpaper with sophisticated negative space and excellent visual hierarchy.

## Повышение детализации и размер 4K

Правка через встроенный image_gen, исходник — уже установленная картинка.
Промпт: сохранить точную композицию, три головы гидры слева, обсидиан и
палитру Black Tiffany, свободный центр; повысить чёткость чешуи, рогов,
тонких бирюзовых прожилок и граней камня без ореолов/шума; запросить
3840×2160 PNG, без текста, часов и UI. Генератор вернул 1672×941,
поэтому фактические 3840×2160 получены при подготовке файла к установке.

Предыдущая картинка и конфигурация сохранены в
~/.local/state/lockscreen-backup/20261019-144459/.
