# Contributing

1. Read the installation and test instructions in [README.md](README.md).
2. Create a branch from `main` for a focused change.
3. Run Ruff, the public tests and the JavaScript syntax check before opening a pull request.
4. Explain the problem, the change and the checks you ran in the pull request.

Use Conventional Commits, for example `fix: handle empty uploads` or `docs: clarify model setup`.
Do not change recognition thresholds or preprocessing without corresponding tests.

Never submit real student photos, face embeddings, names, IDs, private models, `.env` files,
tokens, production logs or database dumps. Use fictional test data. Do not attach private-data
test output to issues or pull requests. The public tests need no private dataset or CI secrets.

New code contributions should be compatible with the MIT license. For third-party assets,
include their source, license and required attribution; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
