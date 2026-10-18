
local ok, configs = pcall(require, 'nvim-treesitter.configs')
if not ok then return end

configs.setup {
  prefer_git = true, -- <--- ДОБАВЬТЕ ЭТУ СТРОКУ СЮДА

  ensure_installed = {
    "bash", "css", "dockerfile", "html",
    "javascript", "json", "json5", "lua",
    "python", "vim", "yaml", "c", "go", "rust",
  },
  highlight = { enable = true },
  indent    = { enable = true },
}
