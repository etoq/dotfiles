pcall(require,'luarocks.loader')
local gears,awful,beautiful=require('gears'),require('awful'),require('beautiful')
require('awful.autofocus')
local hotkeys=require('awful.hotkeys_popup')
local GLib=require('lgi').GLib
local home=os.getenv('HOME')
GLib.setenv('PANEL_WM','awesome',true)
GLib.setenv('XDG_CURRENT_DESKTOP','awesome',true)
GLib.setenv('XDG_SESSION_DESKTOP','awesome',true)
GLib.setenv('XDG_SESSION_TYPE','x11',true)
GLib.setenv('QT_QPA_PLATFORMTHEME','gtk3',true)
beautiful.init(gears.filesystem.get_configuration_dir()..'theme.lua')
local ui=require('ui')
local navigation=require('navigation')
tiffany=ui
local preview=os.getenv('AWESOME_PREVIEW')=='1'
local function action(name)awful.spawn({home..'/.local/bin/panel-action',name},false)end
local function spawn(command)awful.spawn(command,false)end
local function notice(title,message)awful.spawn({'notify-send',title,message},false)end
awesome.connect_signal('debug::error',function(err)
 io.stderr:write('AWESOME ERROR: '..tostring(err)..'\n')
 if not preview then notice('AwesomeWM · ошибка',tostring(err))end
end)
awful.layout.layouts={awful.layout.suit.tile.left,awful.layout.suit.tile.bottom,awful.layout.suit.fair,awful.layout.suit.max,awful.layout.suit.floating}
-- Keep both horizontal columns usable when resizing by keyboard or mouse.
tag.connect_signal('property::master_width_factor',function(t)
 if t.layout~=awful.layout.suit.tile.left and t.layout~=awful.layout.suit.tile then return end
 local factor=math.max(.30,math.min(.70,t.master_width_factor))
 if factor~=t.master_width_factor then t.master_width_factor=factor end
end)
-- One wallpaper owner for manual switching, timer, login and monitor changes.
local wallpaper_timer
local function restore_wallpaper()
 if preview then return end
 if wallpaper_timer then wallpaper_timer:stop()end
 wallpaper_timer=gears.timer.start_new(.3,function()
  spawn({home..'/bin/random_wallpaper','--restore'})
  return false
 end)
end
awful.screen.connect_for_each_screen(function(s)
 ui.screen(s)
 restore_wallpaper()
end)
screen.connect_signal('property::geometry',restore_wallpaper)
local keys={}
local mod='Mod4'
local physical={q=24,w=25,e=26,r=27,t=28,y=29,u=30,i=31,o=32,p=33,a=38,s=39,d=40,f=41,g=42,h=43,j=44,k=45,l=46,z=52,x=53,c=54,v=55,b=56,n=57,m=58,grave=49}
hotkeys.widget.default_widget=hotkeys.widget.new()
for name,code in pairs(physical)do
 hotkeys.widget.default_widget.labels['#'..code]=name=='grave' and '`' or name:upper()
end
local function key(mods,name,fn,description,group)
 name=physical[name] and ('#'..physical[name]) or name
 keys=gears.table.join(keys,awful.key(mods,name,fn,{description=description,group=group or 'Awesome'}))
end
key({mod},'Return',function()spawn('kitty')end,'Терминал','Приложения')
key({mod},'d',function()action('launcher')end,'Otter launcher','Приложения')
key({mod,'Shift'},'x',function()action('color')end,'Пипетка Gpick · повтор — отмена','Инструменты')
key({mod,'Shift'},'d',function()spawn({home..'/.local/bin/desktop-app','open','discord'})end,'Discord','Приложения')
key({mod,'Shift'},'a',function()spawn({home..'/.local/bin/desktop-app','open','chatgpt'})end,'ChatGPT Desktop','Приложения')
key({mod,'Shift'},'c',function()spawn({home..'/bin/calculator'})end,'Калькулятор','Инструменты')
key({mod,'Shift'},'k',function()action('calendar')end,'Календарь calcurse','Инструменты')
key({mod,'Shift'},'v',function()action('vms')end,'Виртуальные машины','Лаборатория')
key({mod,'Shift'},'g',function()action('ghidra')end,'Ghidra','Лаборатория')
key({mod,'Shift'},'o',function()spawn('obsidian')end,'Obsidian','Приложения')
key({mod,'Shift'},'z',function()spawn('zen')end,'Браузер Zen','Приложения')
key({mod,'Shift'},'t',function()spawn({home..'/.local/bin/AyuGram'})end,'AyuGram','Приложения')
key({mod,'Shift'},'s',function()action('vpn')end,'Throne','Приложения')
key({mod,'Shift'},'n',function()action('files')end,'Yazi','Приложения')
key({mod,'Shift'},'p',function()spawn('pavucontrol')end,'Звуковые устройства','Приложения')
key({mod,'Shift'},'r',function()spawn({'kitty','--class','otter-tools','-e',home..'/.local/bin/study'})end,'Работа / отдых / таймер','Инструменты')
key({mod,'Shift'},'e',function()spawn({'rofi','-modi','emoji','-show','emoji'})end,'Эмодзи','Инструменты')
key({mod},'w',function()action('wallpaper')end,'Случайные обои','Оформление')
key({mod},'p',function()spawn({home..'/.local/bin/panel-switch','toggle'})end,'Скрыть / показать панель','Оформление')
key({mod,'Shift'},'b',function()action('switch')end,'Центр управления: звук, яркость, инструменты','Оформление')
key({mod,'Shift'},'l',function()action('lock')end,'Заблокировать экран','Сеанс')
key({mod,'Shift'},'Escape',function()action('power')end,'Питание / сон / выход','Сеанс')
key({mod,'Control'},'r',function()
 awful.spawn.easy_async({'awesome','-k'},function(out,err,reason,code)
  if code==0 then awesome.restart()else notice('AwesomeWM · конфиг не загружен',out..err)end
 end)
end,'Проверить конфиг и перезагрузить WM','Сеанс')
key({mod},'F1',hotkeys.show_help,'Показать все сочетания','Сеанс')
key({mod},'F2',function()require('cheatsheets').show('nvim')end,'Neovim · частые сочетания','Справочники')
key({mod},'F3',function()require('cheatsheets').show('terminal')end,'Fish / Kitty · команды и клавиши','Справочники')
key({mod},'F4',function()require('cheatsheets').show('yazi')end,'Yazi · частые сочетания','Справочники')
key({mod},'F5',function()require('cheatsheets').show('otter')end,'Otter · команды лаунчера','Справочники')
key({mod},'F6',function()require('cheatsheets').show('gdb')end,'GDB / pwndbg · отладка','Справочники')
key({mod},'F7',function()require('cheatsheets').show('recli')end,'RE CLI · анализ файлов','Справочники')
key({mod},'F8',function()require('cheatsheets').show('ghidra')end,'Ghidra · IDA-подобные сочетания','Справочники')
key({mod},'F9',function()require('cheatsheets').show('scripts')end,'Свои скрипты · команды терминала','Справочники')
if preview then key({mod,'Control','Shift'},'Escape',awesome.quit,'Закрыть предпросмотр','Сеанс')end
key({mod},'q',function()spawn({home..'/.config/sxhkd/clip.sh'})end,'История буфера','Инструменты')
key({mod,'Shift'},'q',function()spawn({'sh','-c','greenclip clear; printf "" | xclip -selection clipboard; notify-send "Clipboard" "История очищена"'})end,'Очистить буфер','Инструменты')
key({},'Print',function()action('shot')end,'Скриншот','Инструменты')
key({},'XF86AudioRaiseVolume',function()action('volume-up')end,'Громче','Мультимедиа')
key({},'XF86AudioLowerVolume',function()action('volume-down')end,'Тише','Мультимедиа')
key({},'XF86AudioMute',function()action('mute')end,'Mute','Мультимедиа')
key({},'XF86MonBrightnessUp',function()action('brightness-up')end,'Ярче','Мультимедиа')
key({},'XF86MonBrightnessDown',function()action('brightness-down')end,'Темнее','Мультимедиа')
key({},'XF86AudioPlay',function()action('media')end,'Play / pause','Мультимедиа')
key({},'XF86AudioNext',function()action('next')end,'Следующий трек','Мультимедиа')
key({},'XF86AudioPrev',function()action('previous')end,'Предыдущий трек','Мультимедиа')
key({mod},'c',function()if client.focus then client.focus:kill()end end,'Закрыть окно','Окна')
key({mod},'f',function()if client.focus then client.focus.fullscreen=not client.focus.fullscreen;client.focus:raise()end end,'Полный экран','Окна')
key({mod},'m',function()if client.focus then client.focus.maximized=not client.focus.maximized;client.focus:raise()end end,'Развернуть окно','Окна')
key({mod},'space',function()if client.focus then client.focus.floating=not client.focus.floating end end,'Плавающее / тайловое','Окна')
key({mod},'t',function()if client.focus then client.focus.fullscreen=false;client.focus.maximized=false;client.focus.floating=false end end,'Тайловое окно','Окна')
key({mod,'Control'},'space',function()awful.layout.inc(1)end,'Следующая раскладка','Окна')
key({mod,'Control','Shift'},'space',function()awful.layout.inc(-1)end,'Предыдущая раскладка','Окна')
key({'Mod1'},'Tab',function()navigation.cycle(1) end,'Следующее окно','Окна')
key({'Mod1','Shift'},'Tab',function()navigation.cycle(-1) end,'Предыдущее окно','Окна')
key({mod},'grave',function()navigation.previous() end,'Предыдущее активное окно','Окна')
key({mod},'Tab',awful.tag.history.restore,'Предыдущий рабочий стол','Столы')
key({mod,'Control'},'Left',function()awful.screen.focus_relative(-1)end,'Предыдущий монитор','Мониторы')
key({mod,'Control'},'Right',function()awful.screen.focus_relative(1)end,'Следующий монитор','Мониторы')
key({mod,'Control','Shift'},'Right',function()if client.focus then client.focus:move_to_screen()end end,'Перенести окно на другой монитор','Мониторы')
for name,dir in pairs({h='left',j='down',k='up',l='right'})do
 key({mod},name,function()navigation.focus(dir)end,'Фокус '..dir,'Окна')
 key({mod,'Mod1'},name,function()navigation.swap(dir)end,'Поменять окна '..dir,'Окна')
 key({mod,'Control'},name,function()
  local c=client.focus
  if c and c.floating then c:relative_move(0,0,(name=='h' and -30 or name=='l' and 30 or 0),(name=='k' and -30 or name=='j' and 30 or 0))
  elseif name=='h' or name=='l' then awful.tag.incmwfact(name=='h' and -.03 or .03)
  else awful.client.incwfact(name=='j' and -.03 or .03)end
 end,'Размер / пропорция '..dir,'Окна')
end
for i=1,7 do
 key({mod},'#'..(i+9),function()ui.view_tag(i)end,'Рабочий стол '..i,'Столы')
 key({mod,'Shift'},'#'..(i+9),function()navigation.move_to_tag(awful.screen.focused().tags[i])end,'Окно на стол '..i,'Столы')
end
key({mod,'Shift'},'Return',function()
 for _,c in ipairs(client.get())do
  if c.class=='tiffany-scratch' then
   if c.minimized then c.minimized=false;c:move_to_screen(awful.screen.focused());awful.placement.centered(c);c:emit_signal('request::activate','scratchpad',{raise=true})
   else c.minimized=true end
   return
  end
 end
 spawn({'kitty','--class','tiffany-scratch','--title','Scratch terminal'})
end,'Терминал по требованию','Инструменты')
-- Layout switching is handled by XKB, including when clients grab the keyboard.
root.keys(keys)
root.buttons(gears.table.join(awful.button({},3,function()action('dashboard')end),awful.button({},4,awful.tag.viewnext),awful.button({},5,awful.tag.viewprev)))
local mouse=gears.table.join(awful.button({},1,function(c)c:emit_signal('request::activate','mouse_click',{raise=true})end),
 awful.button({mod},1,function(c)c:emit_signal('request::activate','mouse_click',{raise=true});awful.mouse.client.move(c)end),
 awful.button({mod},3,function(c)c:emit_signal('request::activate','mouse_click',{raise=true});awful.mouse.client.resize(c)end))
-- Place Otter after its final size and initial X11 configure requests settle.
local function place_popup(c)
 local function center()
  if c.valid then awful.placement.centered(c,{honor_workarea=true,honor_padding=true}) end
 end
 gears.timer.delayed_call(center)
 gears.timer.start_new(.12,function()center();return false end)
end
-- Screenshot overlays must cover physical monitor geometry, including dock struts.
local function place_capture(c)
 local function cover()
  if c.valid then c:geometry(c.screen.geometry);c:raise()end
 end
 cover();gears.timer.delayed_call(cover)
 gears.timer.start_new(.12,function()cover();return false end)
end
awful.rules.rules={
 {rule={},properties={border_width=beautiful.border_width,border_color=beautiful.border_normal,focus=awful.client.focus.filter,raise=true,keys={},buttons=mouse,screen=awful.screen.preferred,placement=awful.placement.no_overlap+awful.placement.no_offscreen}},
 {rule_any={class={'otter','clipboard-manager','pkg-manager','sysmenu','panel-tool','panel-dashboard'},instance={'calendar','otter-tools'}},properties={floating=true,placement=awful.placement.centered}},
 {rule={type='utility'},rule_any={class={'flameshot','Flameshot'}},properties={floating=true,fullscreen=true,ontop=true,border_width=0,skip_taskbar=true,placement=function(c)c:geometry(c.screen.geometry)end},callback=place_capture},
 {rule_any={type={'dock'}},properties={border_width=0,focus=false,focusable=false,skip_taskbar=true,buttons={}}},
 {rule={class='panel-dashboard'},properties={floating=true,ontop=true,border_width=0,skip_taskbar=true,placement=awful.placement.centered}},
 {rule={class='panel-monitor'},properties={fullscreen=true}},
 {rule={class='TiffanyCalculator'},properties={floating=true,ontop=false,fullscreen=false,maximized=false,border_width=0,placement=awful.placement.centered}},
 {rule={class='kitty'},properties={maximized=false,maximized_horizontal=false,maximized_vertical=false}},
 {rule={class='calendar'},properties={floating=true,width=function(c)return math.min(1400,c.screen.workarea.width-80)end,height=function(c)return math.min(900,c.screen.workarea.height-80)end},callback=place_popup},
 {rule={class='otter'},properties={floating=true,fullscreen=false,maximized=false,maximized_horizontal=false,maximized_vertical=false,width=500,height=420,screen=function()return awful.screen.focused()end},callback=place_popup},
 {rule={class='tiffany-scratch'},properties={floating=true,sticky=true,ontop=true,skip_taskbar=true,width=1000,height=600,placement=awful.placement.centered}},
 {rule_any={type={'dialog'},role={'pop-up','GtkFileChooserDialog'}},properties={floating=true,placement=awful.placement.centered}},
}
client.connect_signal('manage',function(c)
 -- Keep the larger master on the right; append new tiled windows to the left stack.
 if not awesome.startup and c.type=='normal' and not c.floating then awful.client.setslave(c)end
 if awesome.startup and not c.size_hints.user_position and not c.size_hints.program_position then awful.placement.no_offscreen(c)end
end)
-- Follow explicit activation of Zen links and the single-instance calculator.
awful.ewmh.add_activate_filter(function(c,context,hints)
 local class=(c.class or ''):lower()
 if (class~='zen' and class~='tiffanycalculator') or c.type~='normal' then return end
 c.minimized=false
 if not c:isvisible() and c.first_tag then c.first_tag:view_only()end
 if _G.mouse.screen~=c.screen then awful.screen.focus(c.screen)end
 hints.raise=true
 return true
end,'ewmh')
client.connect_signal('mouse::enter',function(c)if navigation.is_window(c)then c:emit_signal('request::activate','mouse_enter',{raise=false})end end)
client.connect_signal('focus',function(c)c.border_color=beautiful.border_focus end)
client.connect_signal('unfocus',function(c)c.border_color=beautiful.border_normal end)
if not preview then
 awful.spawn({home..'/.local/bin/awesome-session-start'},false)
 gears.timer.start_new(.8,function()root.keys(keys);return false end)
 gears.timer.start_new(1,function()awful.spawn({home..'/.local/bin/panel-autostart'},false);return false end)
end
