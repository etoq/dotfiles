-- Capabilities из cmp
local capabilities = vim.g.cmp_capabilities or vim.lsp.protocol.make_client_capabilities()

-- Python (pyright):
vim.lsp.config('pyright', {
    capabilities = capabilities,
    settings = {
        pyright = { disableOrganizeImports = true },
        python  = { analysis = { diagnosticMode = 'openFiles', typeCheckingMode = 'basic' } },
    },
})
-- Активируем сервер
vim.lsp.enable('pyright')

-- Python (ruff):
vim.lsp.config('ruff', { capabilities = capabilities })
if vim.fn.executable('ruff') == 1 then vim.lsp.enable('ruff') end

-- TypeScript/JavaScript:
vim.lsp.config('ts_ls', { capabilities = capabilities })
if vim.fn.executable('typescript-language-server') == 1 then vim.lsp.enable('ts_ls') end
