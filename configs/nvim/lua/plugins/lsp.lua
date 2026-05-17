-- Capabilities из cmp
local capabilities = vim.g.cmp_capabilities or vim.lsp.protocol.make_client_capabilities()

-- Python (pyright):
vim.lsp.config('pyright', {
    capabilities = capabilities,
    settings = {
        pyright = { disableOrganizeImports = true },
        python  = { analysis = { ignore = { '*' } } },
    },
})
-- Активируем сервер
vim.lsp.enable('pyright')

-- Python (ruff):
vim.lsp.config('ruff', { capabilities = capabilities })
vim.lsp.enable('ruff')

-- TypeScript/JavaScript:
vim.lsp.config('ts_ls', { capabilities = capabilities })
vim.lsp.enable('ts_ls')
