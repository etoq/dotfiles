require("full-border"):setup()

Header:children_add(function()
    if ya.target_family() ~= "unix" then return ui.Line {} end
    return ui.Span(ya.user_name() .. "@" .. ya.host_name() .. ":"):fg("magenta")
end, 500, Header.LEFT)

-- Downloads show newest first; other folders retain alphabetical ordering.
ps.sub("cd", function()
    local downloads = os.getenv("HOME") .. "/Downloads"
    if tostring(cx.active.current.cwd) == downloads then
        ya.emit("sort", { "mtime", reverse = true, dir_first = true })
        ya.emit("linemode", { "size" })
    else
        ya.emit("sort", { "alphabetical", dir_first = true })
        ya.emit("linemode", { "none" })
    end
end)
