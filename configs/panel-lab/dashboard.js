import Gtk from 'gi://Gtk?version=3.0';
import Gdk from 'gi://Gdk?version=3.0';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
const H=GLib.get_home_dir();
const display=(GLib.getenv('DISPLAY')||'default').replace(/[^a-zA-Z0-9]/g,'_');
const app=new Gtk.Application({application_id:`local.tiffany.Deck.d${display}`});
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
 const deckHeight=Math.min(420,monitor.get_workarea().height-60);
 const healthHeight=Math.min(970,monitor.get_workarea().height-60);win.set_default_size(660,deckHeight);
 win.set_wmclass('panel-dashboard','panel-dashboard');win.set_keep_above(true);win.set_skip_taskbar_hint(true);
 win.set_position(Gtk.WindowPosition.CENTER);win.get_style_context().add_class('deck');
 let lastSize='';win.connect('size-allocate',(_,size)=>{const key=`${size.width}:${size.height}`;if(key===lastSize)return;lastSize=key;
  const area=monitor.get_workarea();win.move(area.x+Math.max(0,Math.floor((area.width-size.width)/2)),area.y+Math.max(0,Math.floor((area.height-size.height)/2)));
 });
 win.connect('key-press-event',(_,e)=>{if(e.get_keyval()[1]===Gdk.KEY_Escape){app.quit();return true;}return false;});
 const root=box(true,14);root.set_border_width(22);win.add(root);
 const header=box(false,12);const title=box(true,5);title.set_hexpand(true);
 title.pack_start(label('󰕮  ZER0 / CONTROL DECK','hero'),false,false,0);
 header.pack_start(title,true,true,0);const close=new Gtk.Button({label:'×'});close.connect('clicked',()=>app.quit());header.pack_end(close,false,false,0);root.pack_start(header,false,false,0);
 const pages=new Gtk.Stack({transition_type:Gtk.StackTransitionType.CROSSFADE,transition_duration:120,homogeneous:false});root.pack_start(pages,true,true,0);
 const main=box(true,14);pages.add_named(main,'main');
 const healthButton=new Gtk.Button({label:'Состояние'});header.pack_end(healthButton,false,false,0);
 const health=box(true,12);pages.add_named(health,'health');
 health.pack_start(label('ОБСЛУЖИВАНИЕ','section'),false,false,0);
 const healthScroll=new Gtk.ScrolledWindow({hscrollbar_policy:Gtk.PolicyType.NEVER,vscrollbar_policy:Gtk.PolicyType.AUTOMATIC});
 const healthRows=box(true,8);healthScroll.add(healthRows);health.pack_start(healthScroll,true,true,0);
 const healthActions=box(false,8);const refreshHealth=new Gtk.Button({label:'Обновить'});const refreshQuota=new Gtk.Button({label:'Проверить место Proton'});
 healthActions.pack_start(refreshHealth,false,false,0);healthActions.pack_start(refreshQuota,false,false,0);health.pack_end(healthActions,false,false,0);
 const healthFeedback=label('','description');healthFeedback.set_line_wrap(true);healthFeedback.set_max_width_chars(58);health.pack_end(healthFeedback,false,false,0);
 const unlockKeys=new Gtk.Button({label:'Разблокировать ключи'});health.pack_end(unlockKeys,false,false,0);
 function loadHealth(done=()=>{}){request([`${H}/.local/bin/workstation-status`],out=>{
  try{const data=JSON.parse(out);unlockKeys.set_visible(Boolean(data.needs_unlock));for(const child of healthRows.get_children())child.destroy();
   for(const [title,value] of data.rows){const item=box(true,4);item.get_style_context().add_class('controls');item.pack_start(label(title,'section'),false,false,0);
    const text=label(value,'tool-title');text.set_line_wrap(true);text.set_max_width_chars(58);text.set_selectable(true);item.pack_start(text,false,false,0);healthRows.pack_start(item,false,false,0);}
   healthRows.show_all();
  }catch(e){console.error(String(e));healthFeedback.set_text('Не удалось прочитать данные состояния.');}
  done();
 },err=>{healthFeedback.set_text(err);done();});}
 healthButton.connect('clicked',()=>{const show=pages.get_visible_child_name()!=='health';pages.set_visible_child_name(show?'health':'main');healthButton.set_label(show?'Назад':'Состояние');if(show)loadHealth();win.resize(660,show?healthHeight:deckHeight);win.set_position(Gtk.WindowPosition.CENTER);});
 refreshHealth.connect('clicked',()=>{
  refreshHealth.set_sensitive(false);refreshHealth.set_label('Обновление…');healthFeedback.set_text('Получение свежих данных SMART и Btrfs. Может потребоваться пароль администратора.');
  const done=()=>{refreshHealth.set_sensitive(true);refreshHealth.set_label('Обновить');};
  request([`${H}/.local/bin/workstation-status`,'--refresh'],()=>{healthFeedback.set_text(`Обновлено в ${GLib.DateTime.new_now_local().format('%H:%M:%S')}`);loadHealth(done);},err=>{healthFeedback.set_text(`Не обновлено: ${err}`);done();});
 });
 refreshQuota.connect('clicked',()=>request([`${H}/.local/bin/proton-quota`,'--refresh'],()=>loadHealth(),err=>{healthFeedback.set_text(err);loadHealth();}));
 unlockKeys.connect('clicked',()=>request([`${H}/.local/bin/proton-quota`,'--unlock'],()=>request([`${H}/.local/bin/proton-quota`,'--refresh'],()=>loadHealth(),err=>{healthFeedback.set_text(err);loadHealth();}),err=>{healthFeedback.set_text(err);loadHealth();}));
 const controls=box(true,8);controls.get_style_context().add_class('controls');main.pack_start(controls,false,false,0);
 function request(args,callback=()=>{},onError=()=>{}){
  try{const proc=Gio.Subprocess.new(args,Gio.SubprocessFlags.STDOUT_PIPE|Gio.SubprocessFlags.STDERR_PIPE);
   proc.communicate_utf8_async(null,null,(p,r)=>{try{const [,out,err]=p.communicate_utf8_finish(r);if(p.get_successful())callback(out.trim());else{console.error(err.trim()||'Не удалось применить настройку');onError(err.trim()||'Не удалось выполнить команду');}}catch(e){console.error(String(e));onError(String(e));}});
  }catch(e){console.error(String(e));onError(String(e));}
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
 controls.pack_start(devices,false,false,0);
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
 const systemState=box(true,4);const vmState=label('VM: проверка…','description');const backupState=label('Last Backup: —','description');
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
   deviceSync=false;const names=(data.vms||[]).join(', ');vmState.set_text(data.vm_available===false?'VM: служба недоступна':(names?`VM: ${names}`:'VM: все выключены'));
   const last=data.backup?.last_success;
   const date=last?GLib.DateTime.new_from_iso8601(last,GLib.TimeZone.new_local()):null;
   backupState.set_text(`Last Backup: ${date?date.to_local().format('%d:%m:%Y'):'—'}`);
  }catch(e){deviceSync=false;console.error(String(e));}});
 }
 refreshSystem();
 const systemRefreshId=GLib.timeout_add(GLib.PRIORITY_DEFAULT,3000,()=>{refreshSystem();return GLib.SOURCE_CONTINUE;});
 app.connect('shutdown',()=>GLib.source_remove(systemRefreshId));
 const refreshId=GLib.timeout_add(GLib.PRIORITY_DEFAULT,1000,()=>{refreshVolume();refreshBrightness();return GLib.SOURCE_CONTINUE;});
 app.connect('shutdown',()=>GLib.source_remove(refreshId));
 const footer=box(false,12);
 const power=new Gtk.Button({label:'󰐥  Питание'});power.get_style_context().add_class('power');power.connect('clicked',()=>action('power'));footer.pack_end(power,false,false,0);main.pack_start(footer,false,false,0);
 win.show_all();mute.grab_focus();

});
app.run([]);
