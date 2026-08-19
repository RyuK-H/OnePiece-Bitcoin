# Security Policy

## Reporting a vulnerability in the tool

If you find a security issue in OnePiece Bitcoin itself (for example, a bug that
leaks a found private key, makes an unexpected network call, or writes secrets
somewhere world-readable), please report it privately:

- Use GitHub's **Security > Report a vulnerability** on this repository, or
- Open a minimal issue asking the maintainer ([@RyuK-H](https://github.com/RyuK-H))
  for a private contact channel.

Please do not open a public issue with exploit details until a fix is available.

## Supported versions

Only the `main` branch is supported. There are no released versions to back-port
fixes to yet.

## Safety notes specific to this project

This project searches for private keys of an open, on-chain bounty (the Bitcoin
Puzzle). A few safety rules matter more here than in most tools:

1. **Never paste a found private key anywhere online.** If the engine ever finds
   a key, it stops and writes the key to a local file with mode `0600` under
   `~/.onepiece/found/`. Import it into a wallet you control and move the funds
   yourself, immediately. Broadcasting late exposes it to mempool front-running
   bots that can steal the prize.
2. **The tool makes no outbound calls except the once-per-hour balance check.**
   Do not run forks that add telemetry, upload progress, or "share" found keys.
   If a build tries to send anything else, treat it as malicious.
3. **This is not a tool for accessing funds you do not own.** The puzzle
   addresses are a deliberate, public bounty created by their author. Using this
   against arbitrary third-party addresses would be both futile (the keyspace is
   astronomical) and wrong.
4. **The odds are effectively zero.** Nothing here improves them. Do not treat a
   hunt as an investment or a guarantee.
