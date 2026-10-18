local awful,gears=require('awful'),require('gears')
local json=require('dkjson')
local M={}
local runtime=os.getenv('PANEL_LAB_RUNTIME') or ((os.getenv('XDG_RUNTIME_DIR') or gears.filesystem.get_cache_dir())..'/panel-lab-awesome')
-- XDG_RUNTIME_DIR is set in the graphical session; never publish personal window titles.
gears.filesystem.make_directories(runtime)
local function tags(s)
 local result={}
 for _,t in ipairs(s.tags)do
  local occupied,urgent=false,false
  for _,c in ipairs(t:clients())do
   if c.valid and not c.skip_taskbar and not c.hidden and (c.type=='normal' or c.type=='dialog')then
    occupied=true;urgent=urgent or c.urgent
   end
  end
  result[#result+1]={id=t.index,active=t.selected,occupied=occupied,urgent=urgent}
 end
 return result
end
local pending=false
function M.publish()
 if pending then return end
 pending=true
 gears.timer.delayed_call(function()
  pending=false
  local result={}
  for s in screen do
   local outputs={};for name in pairs(s.outputs or {})do outputs[#outputs+1]=name end
   result[#result+1]={screen=s.index,outputs=outputs,tags=tags(s)}
  end
  local path=runtime..'/workspaces.json';local f=io.open(path..'.tmp','w')
  if f then f:write(json.encode(result),'\n');f:close();os.rename(path..'.tmp',path)end
 end)
end
function M.screen(s)
 awful.tag({'1','2','3','4','5','6','7'},s,awful.layout.suit.tile)
 s.padding={top=0,left=0,right=0,bottom=0};M.publish()
end
function M.view_tag(n,monitor)
 local target=awful.screen.focused()
 if monitor then for s in screen do if s.outputs and s.outputs[monitor]then target=s;break end end end
 local t=target.tags[n]
 if t then
  if mouse.screen~=target then awful.screen.focus(target)end
  t:view_only()
 end
end
function M.workspace_json()return json.encode(tags(awful.screen.focused()))end
for _,name in ipairs({'manage','unmanage','tagged','untagged','property::screen','property::skip_taskbar','property::hidden','property::type','property::urgent'})do client.connect_signal(name,M.publish)end
tag.connect_signal('property::selected',M.publish)
for _,name in ipairs({'added','removed','property::geometry','property::outputs'})do screen.connect_signal(name,M.publish)end
return M
