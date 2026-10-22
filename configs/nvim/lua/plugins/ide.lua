-- Everyday IDE actions; keep file rename (<leader>rn) separate from symbol rename.
local function map(keys, fn, description, mode)
    vim.keymap.set(mode or 'n', keys, fn, { silent = true, desc = description })
end

map('gd', vim.lsp.buf.definition, 'К определению символа')
map('gD', vim.lsp.buf.declaration, 'К объявлению символа')
map('gi', vim.lsp.buf.implementation, 'К реализации')
map('<leader>ld', vim.lsp.buf.definition, 'Определение')
map('<leader>lD', vim.lsp.buf.declaration, 'Объявление')
map('<leader>lk', vim.lsp.buf.hover, 'Документация символа')
map('<leader>lr', vim.lsp.buf.references, 'Все ссылки на символ')
map('<leader>ln', vim.lsp.buf.rename, 'Переименовать символ в проекте')
map('<leader>la', vim.lsp.buf.code_action, 'Действия / исправления кода', { 'n', 'x' })
map('<leader>e', vim.diagnostic.open_float, 'Ошибка под курсором')
map('<leader>lq', vim.diagnostic.setloclist, 'Список ошибок текущего файла')
map('<leader>lf', function()
    local available = vim.lsp.get_clients({ bufnr = 0, method = 'textDocument/formatting' })
    if #available == 0 then
        vim.notify('Для этого файла не подключён LSP-форматировщик.', vim.log.levels.WARN)
        return
    end
    vim.lsp.buf.format({ async = true })
end, 'Форматировать через доступный LSP')

local dap = require('dap')
map('<S-F11>', dap.step_out, 'Отладка: выйти из функции')
map('<leader>du', function() require('dapui').toggle() end, 'Отладка: панели')
map('<leader>de', function() require('dapui').eval() end, 'Отладка: значение выражения', { 'n', 'x' })
map('<leader>dr', dap.repl.toggle, 'Отладка: REPL')
map('<leader>dt', dap.terminate, 'Отладка: завершить сеанс')
map('<leader>dc', dap.run_to_cursor, 'Отладка: до курсора')
map('<leader>db', function()
    vim.ui.input({ prompt = 'Условие остановки: ' }, function(condition)
        if condition and condition ~= '' then dap.set_breakpoint(condition) end
    end)
end, 'Отладка: условная точка')

require('which-key').add({
    { '<leader>d', group = 'Отладка DAP' },
    { '<leader>l', group = 'Код / LSP' },
    { '<leader>u', group = 'Справка' },
})

-- Read-only local guide, shipped beside this dotfiles checkout.
local source = vim.uv.fs_realpath(debug.getinfo(1, 'S').source:sub(2))
local guide = source and vim.fs.normalize(vim.fs.dirname(source) .. '/../../../../docs/NEOVIM-GUIDE.md')
local function open_guide()
    if not guide or vim.fn.filereadable(guide) ~= 1 then
        vim.notify('Справочник: ~/dotfiles/docs/NEOVIM-GUIDE.md', vim.log.levels.WARN)
        return
    end
    vim.cmd('tabnew ' .. vim.fn.fnameescape(guide))
    vim.bo.readonly = true
    vim.bo.modifiable = false
end
vim.api.nvim_create_user_command('NvimGuide', open_guide, { desc = 'Как работать с твоим Neovim' })
map('<leader>ug', open_guide, 'Открыть подробный справочник Neovim')
