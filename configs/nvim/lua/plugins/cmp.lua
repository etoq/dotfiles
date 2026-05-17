local ok, cmp = pcall(require, 'cmp')
if not ok then return end

cmp.setup({
    snippet = {
        expand = function(args)
            -- раскомментируй нужный движок если используешь:
            -- require('luasnip').lsp_expand(args.body)
        end
    },
    window = {
        completion    = cmp.config.window.bordered(),
        documentation = cmp.config.window.bordered(),
    },
    mapping = cmp.mapping.preset.insert({
        ['<C-b>']     = cmp.mapping.scroll_docs(-4),
        ['<C-f>']     = cmp.mapping.scroll_docs(4),
        ['<C-Space>'] = cmp.mapping.complete(),
        ['<C-e>']     = cmp.mapping.abort(),
        ['<CR>']      = cmp.mapping.confirm({ select = true }),
        ['<Tab>']     = cmp.mapping.select_next_item(),
        ['<S-Tab>']   = cmp.mapping.select_prev_item(),
    }),
    sources = cmp.config.sources({
        { name = 'nvim_lsp' },
        { name = 'buffer'   },
        { name = 'path'     },
    }),
})

-- Автодополнение в поиске /
cmp.setup.cmdline('/', {
    mapping = cmp.mapping.preset.cmdline(),
    sources = {{ name = 'buffer' }},
})

-- Автодополнение в командной строке :
cmp.setup.cmdline(':', {
    mapping = cmp.mapping.preset.cmdline(),
    sources = cmp.config.sources(
        {{ name = 'path' }},
        {{ name = 'cmdline' }}
    ),
})

-- Capabilities для lspconfig (передаём в lsp.lua через глобальную переменную):
local ok_lsp, cmp_lsp = pcall(require, 'cmp_nvim_lsp')
if ok_lsp then
    vim.g.cmp_capabilities = cmp_lsp.default_capabilities()
end
