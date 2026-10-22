-- ========================================================================== --
--                          ОСНОВНЫЕ НАСТРОЙКИ                                --
-- ========================================================================== --

-- Фикс для подавления предупреждения tbl_flatten (если оно идет из системных скриптов)
-- В новых версиях Neovim лучше использовать vim.iter():flatten():totable()
if vim.fn.has("nvim-0.10") == 1 then
    vim.tbl_flatten = function(t)
        return vim.iter(t):flatten():totable()
    end
end

-- Отключить встроенный проводник netrw
vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

-- Настройки текста
vim.opt.wrap = true
vim.opt.linebreak = true

-- Устанавливаем пробел как Leader клавишу
vim.g.mapleader = " "

-- ========================================================================== --
--                         ГОРЯЧИЕ КЛАВИШИ (MAPPINGS)                          --
-- ========================================================================== --

-- --- Вкладки (Tabs) ---
vim.keymap.set('n', '<leader>tn', ':tabnew<CR>', { silent = true, desc = 'Новая вкладка' })
vim.keymap.set('n', '<leader>j', ':tabnext<CR>', { silent = true, desc = 'След. вкладка' })
vim.keymap.set('n', '<leader>k', ':tabprevious<CR>', { silent = true, desc = 'Пред. вкладка' })

vim.keymap.set('n', '<leader>tw', function()
    if #vim.api.nvim_list_tabpages() > 1 then
        vim.cmd('tabclose')
    else
        vim.cmd('quit')
    end
end, { silent = true, desc = 'Закрыть вкладку/выход' })

vim.keymap.set('n', '<leader>tr', function()
    vim.ui.input({ prompt = 'Имя вкладки: ' }, function(input)
        if input then
            vim.t.tab_name = input
            vim.cmd('redrawtabline')
        end
    end)
end, { desc = 'Переименовать вкладку' })

-- --- Окна и Файлы ---
vim.keymap.set('n', '<leader>wc', ':close<CR>', { silent = true, desc = 'Закрыть окно (сплит)' })

vim.keymap.set('n', '<leader>rn', function()
    local old_name = vim.api.nvim_buf_get_name(0)
    if old_name == "" then return print("Ошибка: файл не сохранен") end

    vim.ui.input({ prompt = 'Новое имя файла: ', default = old_name }, function(new_name)
        if new_name and new_name ~= "" and new_name ~= old_name then
            vim.cmd('saveas ' .. new_name)
            os.remove(old_name)
            vim.cmd('bwipeout ' .. old_name)
            print("Файл переименован в: " .. new_name)
        end
    end)
end, { desc = 'Переименовать файл на диске' })


-- ========================================================================== --
--                         ПОДКЛЮЧЕНИЕ КОНФИГУРАЦИЙ                           --
-- ========================================================================== --

-- Базовые модули
require('core.plugins')
require('core.mappings')
require('core.colors')
require('core.configs')

-- Настройки плагинов (Проверьте, чтобы везде было require, а не equire)
require('plugins.nvim-tree')
require('plugins.treesitter')
require('plugins.lsp')
require('plugins.cmp')
require('plugins.mason')
require('plugins.telescope')
require('plugins.dashboard')
require('plugins.colorizer')
require('plugins.lualine')
require('plugins.cellular')
require('plugins.comment')
require('plugins.bufferline')
require('plugins.todo')
require('plugins.trouble')
require('plugins.toggleterm')
require('plugins.whichkey')
require('plugins.mini')
require('plugins.ide')
require('plugins.better-escape')
