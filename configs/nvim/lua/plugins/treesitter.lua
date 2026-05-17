local ok, configs = pcall(require, 'nvim-treesitter.configs')
if not ok then return end

configs.setup {
  ensure_installed = {
    "bash", "css", "dockerfile", "html",
    "javascript", "json", "json5", "lua",
    "python", "vim", "yaml", "c", "go", "rust",
  },
  highlight = { enable = true },
  indent    = { enable = true },
}
