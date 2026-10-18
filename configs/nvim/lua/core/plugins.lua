-- =====================================================================
-- 1. БАЗОВЫЕ НАСТРОЙКИ (Должны быть до загрузки плагинов)
-- =====================================================================
vim.g.mapleader = " "                  -- Space - главная клавиша (leader)
vim.g.loaded_netrw = 1                 -- Отключаем стандартный проводник (для nvim-tree)
vim.g.loaded_netrwPlugin = 1

vim.opt.showmode = false
vim.opt.updatetime = 100
vim.wo.signcolumn = "yes"
vim.opt.wrap = false
vim.wo.linebreak = true
vim.opt.virtualedit = "block"
vim.opt.undofile = true
vim.opt.swapfile = false               -- Отключить swap файлы
vim.opt.encoding = "utf-8"
vim.opt.cursorline = true              -- Выделять активную строку
vim.opt.fileformat = "unix"
vim.opt.termguicolors = true
vim.opt.so = 30                        -- При скролле курсор всегда по центру
vim.opt.ignorecase = true              -- Игнорировать регистр при поиске
vim.opt.smartcase = true
vim.opt.hlsearch = true
vim.opt.incsearch = true
vim.opt.mouse = "a"                    -- Включить мышь
vim.opt.mousefocus = true
vim.opt.number = true                  -- Номера строк
vim.opt.relativenumber = true          -- Относительные номера строк
vim.opt.splitbelow = true              -- Открытие окон внизу
vim.opt.splitright = true              -- Открытие окон справа
vim.opt.clipboard = "unnamedplus"      -- Общий буфер обмена с ОС
vim.opt.shortmess:append("c")
vim.opt.expandtab = true               -- Табы как пробелы
vim.opt.shiftwidth = 4
vim.opt.tabstop = 4
vim.opt.softtabstop = 4
vim.opt.smartindent = true
vim.opt.cindent = true
vim.opt.smarttab = true

-- =====================================================================
-- 2. ИНИЦИАЛИЗАЦИЯ МЕНЕДЖЕРА ПЛАГИНОВ (lazy.nvim)
-- =====================================================================
local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  vim.fn.system({
    "git",
    "clone",
    "--filter=blob:none",
    "https://github.com/folke/lazy.nvim.git",
    "--branch=stable",
    lazypath,
  })
end
vim.opt.rtp:prepend(lazypath)

-- =====================================================================
-- 3. СПИСОК ПЛАГИНОВ
-- =====================================================================
require("lazy").setup({

    { 'nvim-treesitter/nvim-treesitter', build = ":TSUpdate" },
    { 'neovim/nvim-lspconfig' },

    -- Автодополнение
    { 'hrsh7th/cmp-nvim-lsp' },
    { 'hrsh7th/cmp-buffer' },
    { 'hrsh7th/cmp-path' },
    { 'hrsh7th/cmp-cmdline' },
    { 'hrsh7th/nvim-cmp' },
    { 'williamboman/mason.nvim' },

    { 'nvim-telescope/telescope.nvim', tag = '0.1.6', dependencies = { 'nvim-lua/plenary.nvim' } },
    { 'nvimdev/dashboard-nvim', event = 'VimEnter', config = function() require('dashboard').setup {} end, dependencies = { {'nvim-tree/nvim-web-devicons'}} },
    { 'Eandrju/cellular-automaton.nvim' },
    { 'norcalli/nvim-colorizer.lua' },
    { 'nvim-lualine/lualine.nvim', dependencies = { 'nvim-tree/nvim-web-devicons' } },
    { "folke/todo-comments.nvim", dependencies = { "nvim-lua/plenary.nvim" }, opts = {} },
    { "ellisonleao/gruvbox.nvim", priority = 1000 , config = true, opts = {} },
    { "max397574/better-escape.nvim", config = function() require("better_escape").setup() end },
    { 'numToStr/Comment.nvim', opts = {}, lazy = false },
    { 'akinsho/bufferline.nvim', version = "*", dependencies = 'nvim-tree/nvim-web-devicons'},
    { "nvim-tree/nvim-tree.lua", version = "*", lazy = false, dependencies = { "nvim-tree/nvim-web-devicons" }, config = function() require("nvim-tree").setup {} end },
    { 'RRethy/vim-illuminate' },
    { "vhyrro/luarocks.nvim", priority = 1001, opts = { rocks = { "magick" } } },
    { "folke/trouble.nvim", dependencies = { "nvim-tree/nvim-web-devicons" }, opts = {} },
    { 'akinsho/toggleterm.nvim', version = "*", config = true },
    { "folke/which-key.nvim", event = "VeryLazy", opts = {}, keys = { { "<leader>?", function() require("which-key").show({ global = false }) end, desc = "Buffer Local Keymaps (which-key)", }, }, },

    -- Автоматический запуск кода
    {
        "CRAG666/code_runner.nvim",
        config = function()
            require('code_runner').setup({
                mode = "term", -- Теперь используем настоящий терминал!
                focus = true,        -- Автоматически переводить курсор в терминал
                filetype = {
                    c = "cd $dir && gcc $fileName -o $fileNameWithoutExt && ./$fileNameWithoutExt",
                    python = "python3 -u $fileName",
                },
            })
        end
    },
    -- Выравнивание и перемещение текста
    { 'echasnovski/mini.nvim', version = false },
    { 'echasnovski/mini.move', version = false },
    { 'echasnovski/mini.pairs', version = false },

    -- =================================================================
    -- НОВЫЕ ПЛАГИНЫ ДЛЯ REVERSE ENGINEERING, C И ОТЛАДКИ
    -- =================================================================

    -- 1. Hex редактор (Просмотр бинарников)
    { "RaafatTurki/hex.nvim", config = true },

    -- 2. Compiler Explorer (Анализ ассемблера из С-кода)
    {
        "krady21/compiler-explorer.nvim",
        cmd = { "CECompile", "CECompileLive" }
    },

    -- 3. Мощный Отладчик (DAP)
    {
        "mfussenegger/nvim-dap",
        dependencies = {
            "rcarriga/nvim-dap-ui",
            "nvim-neotest/nvim-nio",
            "jay-babu/mason-nvim-dap.nvim",
            "mfussenegger/nvim-dap-python",
        },
        config = function()
            local dap = require("dap")
            local dapui = require("dapui")

            -- Связка Mason и DAP для автоматической установки адаптеров
            require("mason-nvim-dap").setup({
                ensure_installed = { "python", "codelldb" },
                automatic_installation = true,
                handlers = {},
            })

            dapui.setup()

            -- Автоматическое открытие окон отладчика
            dap.listeners.after.event_initialized["dapui_config"] = function() dapui.open() end
            dap.listeners.before.event_terminated["dapui_config"] = function() dapui.close() end
            dap.listeners.before.event_exited["dapui_config"] = function() dapui.close() end

            -- Настройка Python DAP
            require("dap-python").setup("python3")
        end
    },
})

-- =====================================================================
-- 4. ГОРЯЧИЕ КЛАВИШИ (Keymaps)
-- =====================================================================
-- Выход, Копирование, Сохранение
vim.keymap.set('n', '<C-q>', '<cmd>:q<CR>')
vim.keymap.set('n', '<C-a>', '<cmd>%y+<CR>')
vim.keymap.set('i', '<C-s>', '<cmd>:w<CR>')
vim.keymap.set('n', '<C-s>', '<cmd>:w<CR>')

-- Code Runner (Запуск кода на C/Python без отладки)
vim.keymap.set('n', '<F4>', ':RunFile<CR>', { noremap = true, silent = false })
vim.keymap.set('n', '<F5>', ':RunClose<CR>', { noremap = true, silent = false })

-- === ХАКЕРСКИЕ И ОТЛАДОЧНЫЕ ГОРЯЧИЕ КЛАВИШИ ===

-- Hex Editor (Пробел + h включает/выключает Hex режим)
vim.keymap.set('n', '<leader>h', ':HexToggle<CR>', { noremap = true, silent = true })

-- Отладка (DAP)
vim.keymap.set('n', '<F9>', ":lua require'dap'.toggle_breakpoint()<CR>", { noremap = true, silent = true, desc = "Toggle Breakpoint" })
vim.keymap.set('n', '<F10>', ":lua require'dap'.step_over()<CR>", { noremap = true, silent = true, desc = "Step Over" })
vim.keymap.set('n', '<F11>', ":lua require'dap'.step_into()<CR>", { noremap = true, silent = true, desc = "Step Into" })
vim.keymap.set('n', '<F12>', ":lua require'dap'.continue()<CR>", { noremap = true, silent = true, desc = "Start/Continue Debugging" })


-- =====================================================================
-- 5. НАСТРОЙКА LSP И АВТОДОПОЛНЕНИЯ ( Mason + Новые стандарты Nvim )
-- =====================================================================
require('mason').setup()

local capabilities = vim.g.cmp_capabilities or vim.lsp.protocol.make_client_capabilities()

-- Python (pyright):
vim.lsp.config('pyright', {
    capabilities = capabilities,
    settings = {
        pyright = { disableOrganizeImports = true },
        python  = { analysis = { ignore = { '*' } } },
    },
})
vim.lsp.enable('pyright')

-- Python (ruff):
vim.lsp.config('ruff', { capabilities = capabilities })
vim.lsp.enable('ruff')

-- C / C++ (clangd) - ВАЖНО ДЛЯ РЕВЕРСА И С:
vim.lsp.config('clangd', { capabilities = capabilities })
vim.lsp.enable('clangd')

-- =====================================================================
-- 6. ТВИКИ ДЛЯ ТЕРМИНАЛА
-- =====================================================================
-- Автоматически переходить в режим ввода (Insert) при открытии терминала
vim.api.nvim_create_autocmd("TermOpen", {
    pattern = "*",
    command = "startinsert",
})

-- Удобный выход из режима ввода в терминале (чтобы можно было его скрыть)
vim.keymap.set('t', '<Esc>', '<C-\\><C-n>', { noremap = true, silent = true })
