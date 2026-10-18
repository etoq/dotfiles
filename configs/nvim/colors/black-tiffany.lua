-- Black Tiffany: quiet surfaces, teal focus, distinct diagnostics.
vim.opt.termguicolors = true
vim.o.background = 'dark'
vim.cmd('highlight clear')
if vim.fn.exists('syntax_on') == 1 then vim.cmd('syntax reset') end
vim.g.colors_name = 'black-tiffany'
local c = {
 bg='#080D10', panel='#101B20', select='#183039', fg='#C5D6D8',
 muted='#7E999F', teal='#0ABAB5', cyan='#4DDDD5', pale='#A3F0E7',
 blue='#79A9D1', green='#8DC99B', yellow='#D8B77B', red='#DE7C86',
}
local function hi(name, fg, bg, extra)
 local v = extra or {}
 v.fg = fg; v.bg = bg
 vim.api.nvim_set_hl(0, name, v)
end
hi('Normal',c.fg,c.bg)
hi('NormalNC',c.fg,c.bg)
hi('NormalFloat',c.fg,c.panel)
hi('FloatBorder',c.teal,c.panel)
hi('FloatTitle',c.pale,c.panel,{bold=true})
hi('Comment',c.muted,nil,{italic=true})
hi('Constant',c.blue)
hi('String',c.pale)
hi('Character',c.pale)
hi('Number',c.blue)
hi('Boolean',c.blue)
hi('Identifier',c.fg)
hi('Function',c.cyan)
hi('Statement',c.teal,nil,{bold=true})
hi('Conditional',c.teal)
hi('Repeat',c.teal)
hi('Keyword',c.teal)
hi('Operator',c.cyan)
hi('PreProc',c.blue)
hi('Type',c.pale)
hi('Special',c.cyan)
hi('Delimiter',c.muted)
hi('Error',c.red,c.panel)
hi('Todo',c.yellow,c.panel,{bold=true})
hi('CursorLine',nil,c.panel)
hi('CursorColumn',nil,c.panel)
hi('CursorLineNr',c.teal,c.panel,{bold=true})
hi('LineNr',c.muted)
hi('SignColumn',c.muted,c.bg)
hi('FoldColumn',c.muted,c.bg)
hi('Folded',c.muted,c.panel)
hi('Visual',nil,c.select)
hi('Search',c.pale,c.select)
hi('IncSearch',c.bg,c.teal)
hi('CurSearch',c.bg,c.teal)
hi('MatchParen',c.pale,c.select,{bold=true})
hi('Pmenu',c.fg,c.panel)
hi('PmenuSel',c.pale,c.select,{bold=true})
hi('PmenuSbar',nil,c.panel)
hi('PmenuThumb',nil,c.teal)
hi('StatusLine',c.fg,c.panel)
hi('StatusLineNC',c.muted,c.panel)
hi('TabLine',c.muted,c.panel)
hi('TabLineFill',nil,c.bg)
hi('TabLineSel',c.pale,c.select,{bold=true})
hi('WinSeparator',c.select,c.bg)
hi('VertSplit',c.select,c.bg)
hi('Directory',c.cyan)
hi('Title',c.pale,nil,{bold=true})
hi('NonText',c.select)
hi('Whitespace',c.select)
hi('SpecialKey',c.muted)
hi('EndOfBuffer',c.bg)
hi('Cursor',c.bg,c.cyan)
hi('ColorColumn',nil,c.panel)
hi('DiffAdd',c.green,'#14251E')
hi('DiffChange',c.blue,c.panel)
hi('DiffDelete',c.red,'#2A191E')
hi('DiffText',c.pale,c.select)
for kind,col in pairs({Error=c.red,Warn=c.yellow,Info=c.blue,Hint=c.cyan,Ok=c.green}) do
 hi('Diagnostic'..kind,col)
 hi('DiagnosticVirtualText'..kind,col,c.panel)
 hi('DiagnosticUnderline'..kind,nil,nil,{undercurl=true,sp=col})
end
for group,target in pairs({
 ['@comment']='Comment',['@string']='String',['@number']='Number',
 ['@boolean']='Boolean',['@constant']='Constant',['@variable']='Identifier',
 ['@variable.builtin']='Special',['@function']='Function',['@function.call']='Function',
 ['@function.builtin']='Function',['@keyword']='Keyword',['@operator']='Operator',
 ['@type']='Type',['@property']='Identifier',['@punctuation']='Delimiter',
 ['@tag']='Keyword',['@tag.attribute']='Identifier',['@markup.heading']='Title',
 ['@markup.link']='Underlined',
}) do vim.api.nvim_set_hl(0,group,{link=target}) end
hi('Underlined',c.cyan,nil,{underline=true})
for _,group in ipairs({'NvimTreeNormal','NvimTreeNormalNC','TelescopeNormal'}) do hi(group,c.fg,c.bg) end
hi('NvimTreeFolderName',c.cyan)
hi('NvimTreeOpenedFolderName',c.pale)
hi('NvimTreeRootFolder',c.teal,nil,{bold=true})
hi('NvimTreeCursorLine',nil,c.select)
hi('TelescopeBorder',c.select,c.bg)
hi('TelescopeSelection',c.pale,c.select)
hi('TelescopeMatching',c.cyan,nil,{bold=true})
hi('WhichKey',c.cyan)
hi('WhichKeyDesc',c.fg)
hi('GitSignsAdd',c.green)
hi('GitSignsChange',c.blue)
hi('GitSignsDelete',c.red)
