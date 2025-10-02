# YudaiV3 — Model Marketplace for Coding Agents

[![YudaiV3 Logo](https://via.placeholder.com/300x100.png?text=YudaiV3+Logo)](https://yudai.app)

> **Create. Finetune. Tokenize. Monetize.**  
> Turn your GitHub issues & merged PRs into a production model you can list on a marketplace, pair with liquidity, and earn from per-request usage.

---

![NodeJS](https://img.shields.io/badge/node.js-6DA55F?style-for-the-badge&logo=node.js&logoColor=white)
![Vite](https://img.shields.io/badge/vite-%23646CFF.svg?style-for-the-badge&logo=vite&logoColor=white)
![GitHub](https://img.shields.io/badge/github-%23121011.svg?style-for-the-badge&logo=github&logoColor=white)
![Ruff](https://img.shields.io/badge/Ruff-Python%20Linter-FF4500?style-for-the-badge&logo=python&logoColor=white)

##
![Ubuntu](https://img.shields.io/badge/Ubuntu-E95420?style=for-the-badge&logo=ubuntu&logoColor=white)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![TypeScript](https://img.shields.io/badge/typescript-%23007ACC.svg?style=for-the-badge&logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![GitHub Actions](https://img.shields.io/badge/github%20actions-%232671E5.svg?style=for-the-badge&logo=githubactions&logoColor=white)
![Ethereum](https://img.shields.io/badge/Ethereum-3C3C3D?style=for-the-badge&logo=Ethereum&logoColor=white)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/react-%2320232a.svg?style=for-the-badge&logo=react&logoColor=%2361DAFB)
![TailwindCSS](https://img.shields.io/badge/tailwindcss-%2338B2AC.svg?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Vultr](https://img.shields.io/badge/Vultr-007BFC.svg?style=for-the-badge&logo=vultr)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Nginx](https://img.shields.io/badge/nginx-%23009639.svg?style=for-the-badge&logo=nginx&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-%23EE4C2C.svg?style=for-the-badge&logo=PyTorch&logoColor=white)

---

## What is YudaiV3?

YudaiV3 is a **model marketplace for coding agents**. It transforms your repo’s development activity (issues created, PRs merged) into a finetuned, tokenized model that you can **list, provide liquidity for, and monetize**.

- **Base Models:** GPT-5, Claude, Qwen3-Coder, Grok (and more)
- **Milestone → Finetune:** After **30 issues created** and **30 issues merged**, you can trigger a guided finetune
- **Tokenization:** Each finetuned model mints its own **ERC-20 (AGENTx)**, paired with **$SOLVE** on Uniswap v4
- **Monetization:** Earn from **per-request usage** (x402 pay-per-call) and **LP swap fees** streamed via Uniswap v4 **Hooks**

---

## Who is it for?

- **Solo devs & indie hackers** who want their repo history to compound into a sellable model
- **Product & growth engineers** who want usage-based revenue on top of existing workflows
- **Open-source maintainers** who seek a sustainable economic loop tied to real code impact

---

## How it works (high-level)

1. **Create & Merge**  
   Keep shipping. YudaiV3 tracks issues created and merged PRs to build your training corpus.

2. **Hit 30/30 → Finetune**  
   Reach **30 issues created** and **30 merged** to unlock a guided finetune for your repo-specific agent.

3. **Mint & List (AGENTx)**  
   Your model is minted as **AGENTx (ERC-20)** and listed **AGENTx / $SOLVE** on Uniswap v4.

4. **Provide Liquidity & Earn**  
   Add LP to deepen markets. **Uniswap v4 Hooks** stream a portion of swap fees to your creator vault.

5. **Get Paid Per Request (x402)**  
   The hosted model charges per request using **x402 (HTTP-402)**. Usage revenue settles in stable assets and is routed to your vault, with internal conversion to support your token.

> **All of the above happens without changing your GitHub workflow.** You build; the marketplace handles tokenization, liquidity, and billing.

---

## Key Concepts

- **$SOLVE**  
  Ecosystem and routing token used to pair liquidity with model tokens and anchor discovery across pools.

- **AGENTx (per-model ERC-20)**  
  A token representing your finetuned model. Traders can provide LP; users can pay to call your model; you earn from both.

- **Uniswap v4 Hooks**  
  Pool-level logic that automatically **directs a share of trading fees** to creator/protocol vaults—no manual harvesting.

- **x402 Pay-Per-Call**  
  Machine-native HTTP-402 billing for **per-request** or **per-token** usage. Clean receipts, stable settlement, creator-first routing.

---

## Features (current & planned)

- ✅ GitHub-native issue & PR signal ingestion  
- ✅ Finetune unlock at **30/30 milestone**  
- ✅ Tokenization & marketplace listing per model (AGENTx)  
- ✅ Liquidity provisioning (AGENTx / $SOLVE) with v4 Hooks fee streaming  
- ✅ Usage billing via x402 (per request)  
- 🛠️ Roadmap: per-model eval cards, dataset attestations, advanced creator analytics, additional base models

---

## Contributing

We welcome contributions to the marketplace code and docs:

1. Fork this repository  
2. Create a feature branch (`feat/your-idea`)  
3. Open a PR with a clear description and rationale

Check the [issues page](https://github.com/pranay5255/YudaiV3/issues) for open tasks.

---

## License

YudaiV3 is an early-stage open-source project. The license is currently under consideration. Feel free to open an [issue](https://github.com/pranay5255/YudaiV3/issues) to discuss licensing or usage terms.

---

## Contact

Questions or partnerships: [support@yudai.app](mailto:support@yudai.app)

---

## 👉 Call to Action

**Ready to monetize your model? Visit the marketplace:** **[yudai.app](https://yudai.app)**
