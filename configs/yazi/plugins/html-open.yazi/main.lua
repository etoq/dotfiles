-- HTML asks for an opener; other files keep their normal opening behavior.
local needs_choice = ya.sync(function(_, hovered_only)
	local hovered = cx.active.current.hovered
	if not hovered then return false end
	local function is_html(file)
		if file.cha.is_dir then return false end
		local ext = (file.url.ext or ""):lower()
		return ext == "html" or ext == "htm" or ext == "xhtml"
	end
	if hovered_only or #cx.active.selected == 0 then return is_html(hovered) end
	for _, file in pairs(cx.active.selected) do
		if is_html(file) then return true end
	end
	return false
end)

return {
	entry = function(_, job)
		local hovered = job.args.hovered == true
		ya.emit("open", { hovered = hovered, interactive = needs_choice(hovered) })
	end,
}
