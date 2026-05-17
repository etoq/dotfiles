
local wk = require("which-key")

wk.add({
	{ "<leader>f", group = "Find" }, -- group
	{ "<leader>ff", desc = "Find File", mode = "n" },
	{ "<leader>ft", desc = "Find Text", mode = "n"},
	{ "<leader>fb", desc = "Find Buffer", mode = "n"},
	{ "<leader>fh", desc = "Find Help", mode = "n"},

	{ "<leader>g", group = "Git"},
	{ "<leader>gb", desc = "Open Branches", mode = "n" },
	{ "<leader>gc", desc = "Open Commits", mode = "n" },
	{ "<leader>gs", desc = "Open Status", mode = "n" },

	{ "<leader>l", group = "LSP"},
	{ "<leader>lD", desc = "Declaration", mode = "n" },
	{ "<leader>ld", desc = "Definition", mode = "n" },
	{ "<leader>lk", desc = "Hover", mode = "n" },

	{ "<leader>t", group = "NvimTree"},
	{ "<leader>tt", "<cmd>NvimTreeToggle<cr>", desc = "Tree Toggle", mode = "n" },
	{ "<leader>tf", "<cmd>NvimTreeFocus<cr>", desc = "Tree Focus", mode = "n" },

	{ "<leader>n", group = "TodoList"},
	{ "<leader>nl", "<cmd>TodoTelescope<cr>", desc = "Open List", mode = "n" },

	{ "<leader>c", group = "Themes"},
	{ "<leader>cs", "<cmd>Telescope find_files<cr>", desc = "Change", mode = "n" },
	
	{ "<leader>e", desc = "Open Diagnostic Window", mode = "n" },
	{ "<leader>s", "<cmd>ToggleTerm direction=float<cr>", desc = "Open Terminal", mode = "n" },
	{ "<leader>r", "<cmd>w<cr>", desc = "Ruff", mode = "n" },
})

