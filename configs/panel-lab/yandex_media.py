"""Select Yandex Music by MPRIS identity, never by Chromium's changing bus id."""
import re

_connection=None
_Gio=_GLib=None

def _bus():
 global _connection,_Gio,_GLib
 if _connection is None:
  from gi.repository import Gio,GLib
  _Gio,_GLib=Gio,GLib
  _connection=Gio.bus_get_sync(Gio.BusType.SESSION,None)
 return _connection

def _call(name,path,interface,method,params=None):
 return _bus().call_sync(name,path,interface,method,params,None,_Gio.DBusCallFlags.NONE,1500,None).unpack()

def _properties(name,interface):
 _bus()
 return _call(name,'/org/mpris/MediaPlayer2','org.freedesktop.DBus.Properties','GetAll',_GLib.Variant('(s)',(interface,)))[0]

def _identity(value):return re.sub(r'[^a-zа-я0-9]','',str(value).casefold())

def selected_player():
 try:
  names=_call('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','ListNames')[0]
 except Exception:return None
 for name in sorted(n for n in names if n.startswith('org.mpris.MediaPlayer2.')):
  try:
   props=_properties(name,'org.mpris.MediaPlayer2')
   if any(_identity(props.get(k,'')) in ('yandexmusic','яндексмузыка') for k in ('Identity','DesktopEntry')):return name
  except Exception:continue
 return None

def metadata():
 try:
  name=selected_player()
  if not name:return {}
  props=_properties(name,'org.mpris.MediaPlayer2.Player')
  meta=props.get('Metadata',{});artists=meta.get('xesam:artist',[])
  if isinstance(artists,str):artists=[artists]
  return {'player':name,'artist':', '.join(str(a) for a in artists),
          'title':str(meta.get('xesam:title','')),'status':props.get('PlaybackStatus','Stopped')}
 except Exception:return {}

def control(action):
 method={'play-pause':'PlayPause','next':'Next','previous':'Previous'}.get(action)
 if not method:return False
 name=selected_player()
 if not name:return False
 try:_call(name,'/org/mpris/MediaPlayer2','org.mpris.MediaPlayer2.Player',method);return True
 except Exception:return False
