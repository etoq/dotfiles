local awful,gears=require('awful'),require('gears')
local M={}
function M.is_window(c)
 return c and c.valid and awful.client.focus.filter(c) ~=nil
end
local function windows(s)
 local result={}
 for _,c in ipairs(awful.client.visible(s))do
  if M.is_window(c) and not c.skip_taskbar and not c.minimized then result[#result+1]=c end
 end
 return result
end
local function activate(c)
 if c then c:emit_signal('request::activate','keyboard',{raise=true})end
end
local function target(dir,tiled)
 local source=client.focus
 if not M.is_window(source)then return nil end
 local choices,geometries={},{}
 for _,c in ipairs(windows(source.screen))do
  if c~=source and (not tiled or not c.floating)then
   choices[#choices+1]=c;geometries[#geometries+1]=c:geometry()
  end
 end
 local index=gears.geometry.rectangle.get_in_direction(dir,geometries,source:geometry())
 return index and choices[index] or nil
end
function M.focus(dir)activate(target(dir,false))end
function M.swap(dir)
 local source=client.focus
 if not M.is_window(source) or source.floating then return end
 local dest=target(dir,true)
 if dest then source:swap(dest);activate(source)end
end
function M.move_to_tag(t)
 local c=client.focus
 if not M.is_window(c) or not t then return end
 local current=c:tags()
 if #current==1 and current[1]==t then return end
 -- Maximization itself can make c.floating true implicitly. Respect only
 -- explicit floating intent (dialogs/tools/Win+Space) and fixed-size windows.
 local tiled=c.type=='normal' and awful.client.property.get(c,'floating')~=true and not awful.client.object.is_fixed(c)
 -- A maximized tiled client is excluded from the tiler, even on its new tag.
 if tiled then
  c.fullscreen=false
  c.maximized=false
  c.maximized_horizontal=false
  c.maximized_vertical=false
 end
 c:move_to_tag(t)
 if tiled then
  -- Append from the current position, keeping the destination's existing order.
  -- setslave() also swaps earlier clients and can promote an already-managed one.
  local after=false
  for _,other in ipairs(client.get(c.screen))do
   if other==c then after=true elseif after then c:swap(other)end
  end
 end
end
function M.cycle(step)
 local source=client.focus;local choices=windows(source and source.screen or awful.screen.focused())
 if #choices==0 then return end
 local index=step>0 and 0 or 1
 for i,c in ipairs(choices)do if c==source then index=i;break end end
 activate(choices[(index-1+step)%#choices+1])
end
function M.previous()
 local source=client.focus;local s=source and source.screen or awful.screen.focused()
 for _,c in ipairs(awful.client.focus.history.list)do
  if c~=source and M.is_window(c) and not c.skip_taskbar and c.screen==s and c:isvisible() and not c.minimized then activate(c);return end
 end
end
return M
