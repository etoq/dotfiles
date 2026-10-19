import Gtk from 'gi://Gtk?version=3.0';
import Gdk from 'gi://Gdk?version=3.0';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
const H=GLib.get_home_dir();
const display=(GLib.getenv('DISPLAY')||'default').replace(/[^a-zA-Z0-9]/g,'_');
const app=new Gtk.Application({application_id:`local.tiffany.Deck.d${display}`});
const groups=[
 ['АНАЛИЗ И ЛАБОРАТОРИЯ',[
 ['󰍉','Ghidra','Дизассемблер','ghidra'],['󰘦','HEX','Байты в nvim','hex'],['󰅩','CyberChef','Кодировки и данные','cc'],
 ['󰈔','Файл / хеш','Строки и сигнатуры','info'],['󰒓','VM Lab','Виртуальные машины','vms'],['󰈀','Порты','Сетевые соединения','ports']]],
 ['НА КАЖДЫЙ ДЕНЬ',[
 ['󰒍','OCR','Текст с экрана','ocr'],['󰏘','Пипетка','Цвет с экрана','color'],['󰘥','Калькулятор','Вычисления','calc'],
 ['󰈙','Новая заметка','Записать мысль','notes'],['󰃭','Календарь','Даты и задачи','calendar'],['󰄉','Таймер','Обратный отсчёт','timer']]],
 ['СИСТЕМА',[
 ['󰓅','Процессы','CPU и память','monitor'],['󰖟','Сеть','NetworkManager','network'],['󰒄','Throne','VPN-подключение','vpn'],
 ['󰒲','Фокус','Пауза уведомлений','focus'],['󰍹','Обои','Случайные из Images','wallpaper'],['󰌾','Блокировка','Заблокировать экран','lock']]],
];
let win;
function label(text,cls=''){const w=new Gtk.Label({label:text,xalign:0});if(cls)w.get_style_context().add_class(cls);return w;}
function box(vertical,spacing=0){return new Gtk.Box({orientation:vertical?Gtk.Orientation.VERTICAL:Gtk.Orientation.HORIZONTAL,spacing});}
function launch(argv){Gio.Subprocess.new(argv,Gio.SubprocessFlags.NONE);app.quit();}
function action(name){launch([`${H}/.local/bin/panel-action`,name]);}
app.connect('activate',()=>{
 if(win){app.quit();return;}
 const css=new Gtk.CssProvider();css.load_from_path(`${H}/.config/panel-lab/dashboard.css`);
 Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),css,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
 win=new Gtk.ApplicationWindow({application:app,title:'Tiffany Control Deck',decorated:false,resizable:false,type_hint:Gdk.WindowTypeHint.DIALOG});
 const monitor=Gdk.Display.get_default().get_primary_monitor()||Gdk.Display.get_default().get_monitor(0);
 win.set_default_size(660,Math.min(970,monitor.get_workarea().height-60));
 win.set_wmclass('panel-dashboard','panel-dashboard');win.set_keep_above(true);win.set_skip_taskbar_hint(true);
 win.set_position(Gtk.WindowPosition.CENTER);win.get_style_context().add_class('deck');
 win.connect('key-press-event',(_,e)=>{if(e.get_keyval()[1]===Gdk.KEY_Escape){app.quit();return true;}return false;});
 const root=box(true,14);root.set_border_width(22);win.add(root);
 const header=box(false,12);const title=box(true,5);title.set_hexpand(true);
 title.pack_start(label('󰕮  ZER0 / CONTROL DECK','hero'),false,false,0);
 header.pack_start(title,true,true,0);const close=new Gtk.Button({label:'×'});close.connect('clicked',()=>app.quit());header.pack_end(close,false,false,0);root.pack_start(header,false,false,0);
 const controls=box(true,8);controls.get_style_context().add_class('controls');root.pack_start(controls,false,false,0);
 function request(args,callback=()=>{}){
  try{const proc=Gio.Subprocess.new(args,Gio.SubprocessFlags.STDOUT_PIPE|Gio.SubprocessFlags.STDERR_PIPE);
   proc.communicate_utf8_async(null,null,(p,r)=>{try{const [,out,err]=p.communicate_utf8_finish(r);if(p.get_successful())callback(out.trim());else controls.set_tooltip_text(err.trim()||'Не удалось применить настройку');}catch(e){controls.set_tooltip_text(String(e));}});
  }catch(e){controls.set_tooltip_text(String(e));}
 }
 function slider(title,command,minimum,query,parse){
  const row=box(false,12);const caption=label(title,'tool-title');caption.set_size_request(120,-1);row.pack_start(caption,false,false,0);
  const scale=Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,minimum,100,1);scale.set_hexpand(true);scale.set_draw_value(false);scale.set_size_request(260,24);row.pack_start(scale,true,true,0);
  const value=label('—','description');value.set_size_request(40,-1);row.pack_start(value,false,false,0);
  let syncing=false,pending=0,edited=0,dragging=false;
  scale.connect('button-press-event',()=>{dragging=true;return false;});scale.connect('button-release-event',()=>{dragging=false;return false;});
  scale.connect('value-changed',()=>{const n=Math.round(scale.get_value());value.set_text(`${n}%`);if(syncing)return;
   edited=GLib.get_monotonic_time();if(pending)GLib.source_remove(pending);
   pending=GLib.timeout_add(GLib.PRIORITY_DEFAULT,120,()=>{pending=0;request([`${H}/.local/bin/panel-action`,command,String(n)]);return GLib.SOURCE_REMOVE;});
  });
  function refresh(){request(query,out=>{const n=parse(out);if(!Number.isFinite(n)||dragging||GLib.get_monotonic_time()-edited<1000000)return;syncing=true;scale.set_value(n);value.set_text(`${Math.round(n)}%`);syncing=false;});}
  controls.pack_start(row,false,false,0);refresh();return refresh;
 }
 const refreshVolume=slider('󰕾 Звук','volume-set',0,['pamixer','--get-volume'],Number);
 const refreshBrightness=slider('󰃠 Яркость','brightness-set',1,['brightnessctl','-m'],s=>Number(s.split(',')[3]?.replace('%','')));
 const devices=box(false,8);const mute=new Gtk.Button({label:'󰖁 Звук вкл/выкл'});mute.connect('clicked',()=>request([`${H}/.local/bin/panel-action`,'mute']));devices.pack_start(mute,false,false,0);
 const audio=new Gtk.Button({label:'Аудиоустройства'});audio.connect('clicked',()=>launch(['pavucontrol']));devices.pack_end(audio,false,false,0);controls.pack_start(devices,false,false,0);
 const selectors=box(true,6);controls.pack_start(selectors,false,false,0);
 let deviceSync=false,deviceEdited=0,deviceOptions={};
 function deviceSelector(title,command,key,selectedKey){
  const row=box(false,10);const caption=label(title,'tool-title');caption.set_size_request(118,-1);row.pack_start(caption,false,false,0);
  const combo=new Gtk.ComboBoxText();combo.set_hexpand(true);combo.set_size_request(300,-1);
  for(const cell of combo.get_cells()){cell.set_property('ellipsize',Pango.EllipsizeMode.END);cell.set_property('max-width-chars',39);}
  combo.connect('changed',()=>{const id=combo.get_active_id();if(deviceSync||!id)return;deviceEdited=GLib.get_monotonic_time();request([`${H}/.local/bin/deck-system`,command,id],()=>refreshSystem());});
  row.pack_start(combo,true,true,0);selectors.pack_start(row,false,false,0);return {combo,key,selectedKey};
 }
 const output=deviceSelector('󰕾 Выход','set-sink','sinks','default_sink');
 const input=deviceSelector('󰍬 Микрофон','set-source','sources','default_source');
 const systemState=box(true,4);const vmState=label('VM: проверка…','description');const backupState=label('Копия: проверка…','description');
 for(const w of [vmState,backupState]){w.set_ellipsize(Pango.EllipsizeMode.END);w.set_max_width_chars(65);systemState.pack_start(w,false,false,0);}
 controls.pack_start(systemState,false,false,0);
 let systemPending=false;
 function refreshSystem(){
  if(systemPending)return;systemPending=true;
  const proc=Gio.Subprocess.new([`${H}/.local/bin/deck-system`,'status'],Gio.SubprocessFlags.STDOUT_PIPE|Gio.SubprocessFlags.STDERR_PIPE);
  proc.communicate_utf8_async(null,null,(p,r)=>{systemPending=false;try{
   const [,out]=p.communicate_utf8_finish(r);if(!p.get_successful())return;const data=JSON.parse(out);deviceSync=true;
   for(const item of [output,input]){
    const opts=JSON.stringify(data[item.key]||[]);
    if(deviceOptions[item.key]!==opts){item.combo.remove_all();for(const d of data[item.key]||[])item.combo.append(d.id,d.label);deviceOptions[item.key]=opts;}
    if(GLib.get_monotonic_time()-deviceEdited>1200000)item.combo.set_active_id(data[item.selectedKey]||'');
   }
   deviceSync=false;const names=(data.vms||[]).join(', ');vmState.set_text(data.vm_available===false?'VM: служба недоступна':(names?`VM: ${names}`:'VM: все выключены'));vmState.set_tooltip_text(names||'Нет запущенных виртуальных машин');
   const last=data.backup?.last_success;const backupLabels={awaiting_destination:'ждёт выбора облака',awaiting_authentication:'Proton — нужен вход',not_configured:'не настроена',ready:'Proton подключён, копии ещё нет',running:'выполняется',error:'ошибка'};const state=data.backup?.state;backupState.set_text(['running','error'].includes(state)?`Копия: ${backupLabels[state]}`:(last?`Копия: ${last}${data.backup?.scope==='partial'?' · дополнение':''}`:`Копия: ${backupLabels[state]||'не запущена'}`));backupState.set_tooltip_text([data.backup?.message,data.backup?.last_full_success?`Полная копия: ${data.backup.last_full_success}`:null].filter(Boolean).join('\n')||'Резервирование пока не запущено');
  }catch(e){deviceSync=false;controls.set_tooltip_text(String(e));}});
 }
 refreshSystem();
 const systemRefreshId=GLib.timeout_add(GLib.PRIORITY_DEFAULT,3000,()=>{refreshSystem();return GLib.SOURCE_CONTINUE;});
 app.connect('shutdown',()=>GLib.source_remove(systemRefreshId));
 const refreshId=GLib.timeout_add(GLib.PRIORITY_DEFAULT,1000,()=>{refreshVolume();refreshBrightness();return GLib.SOURCE_CONTINUE;});
 app.connect('shutdown',()=>GLib.source_remove(refreshId));
 const search=new Gtk.SearchEntry({placeholder_text:'Найти инструмент…'});root.pack_start(search,false,false,0);
 const catalog=box(true,14);const scroll=new Gtk.ScrolledWindow({hscrollbar_policy:Gtk.PolicyType.NEVER,vscrollbar_policy:Gtk.PolicyType.AUTOMATIC});scroll.set_min_content_height(230);scroll.add(catalog);root.pack_start(scroll,true,true,0);
 const sections=[];const tiles=[];
 for(const [name,items] of groups){
  const section=box(true,8);section.pack_start(label(name,'section'),false,false,0);
  const grid=new Gtk.Grid({column_spacing:8,row_spacing:8,column_homogeneous:true});section.pack_start(grid,false,false,0);
  items.forEach(([icon,name,description,command],i)=>{
   const tile=new Gtk.Button();tile.get_style_context().add_class('tile');tile.set_size_request(186,62);
   const row=box(false,10);row.pack_start(label(icon,'icon'),false,false,0);const copy=box(true,5);
   copy.pack_start(label(name,'tool-title'),false,false,0);copy.pack_start(label(description,'description'),false,false,0);
   row.pack_start(copy,true,true,0);tile.add(row);tile.connect('clicked',()=>action(command));grid.attach(tile,i%3,Math.floor(i/3),1,1);
   tiles.push({tile,key:`${name} ${description} ${command}`.toLowerCase(),section});
  });sections.push(section);catalog.pack_start(section,false,false,0);
 }
 const footer=box(false,12);
 const power=new Gtk.Button({label:'󰐥  Питание'});power.get_style_context().add_class('power');power.connect('clicked',()=>action('power'));footer.pack_end(power,false,false,0);root.pack_start(footer,false,false,0);
 search.connect('search-changed',()=>{const q=search.get_text().toLowerCase().trim();for(const t of tiles)t.tile.set_visible(t.key.includes(q));for(const section of sections)section.set_visible(tiles.some(t=>t.section===section&&t.tile.get_visible()));});
 search.connect('activate',()=>{const found=tiles.find(t=>t.tile.get_visible());if(found)found.tile.clicked();});
 win.show_all();search.grab_focus();
});
app.run([]);
