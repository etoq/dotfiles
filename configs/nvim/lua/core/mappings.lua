vim.g.mapleader = " "

-- Quit
vim.keymap.set('n', '<C-q>', '<cmd>:q<CR>')

-- Copy all text
vim.keymap.set('n', '<C-a>', '<cmd>%y+<CR>')

-- Saving a file via Ctrl+S
vim.keymap.set('i', '<C-s>', '<cmd>:w<CR>')
vim.keymap.set('n', '<C-s>', '<cmd>:w<CR>')

-- Code Runner
vim.keymap.set('n', '<F4>', ':RunFile<CR>', { noremap = true, silent = false })
vim.keymap.set('n', '<F5>', ':RunClose<CR>', { noremap = true, silent = false })
