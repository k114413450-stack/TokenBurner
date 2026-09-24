# TokenBurner 🔥

> **The 3D Holographic AI Token HUD & Cyber War Report Generator for Vibe Coders.**  
> Track, visualize, and celebrate your AI token consumption across Cursor, GitHub Copilot, DoubaoWork, Antigravity, and domestic AI IDEs with zero API keys and 100% local privacy.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-brightgreen.svg)](https://python.org)
[![Three.js](https://img.shields.io/badge/3D%20Engine-Three.js%20WebGL-black.svg)](https://threejs.org)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078d4.svg)](https://microsoft.com)
[![Privacy: 100% Local](https://img.shields.io/badge/Privacy-100%25%20Local-success.svg)](#privacy--security)

---

## 🌟 Visual Showcase

<div align="center">
  <p><b>✨ Real-Time 3D Holographic Floating Desktop HUD (EVA-01 Unit Theme)</b></p>
  <img src="assets/hud_preview.png" width="460" alt="TokenBurner 3D Holographic HUD Preview" />
  <br/><br/>
  <p><b>📊 1080x1920 High-Definition Cyber War Report Poster (24H Stock-Style Token Surge)</b></p>
  <img src="assets/war_report_preview.png" width="480" alt="TokenBurner War Report Poster" />
</div>

---

## 🚀 Why TokenBurner?

In the era of **Vibe Coding**, every prompt, agent trajectory, and refactored function burns AI tokens. Whether you use **Cursor**, **GitHub Copilot**, **Antigravity**, or **DoubaoWork**, keeping track of your cumulative compute power should be thrilling, beautiful, and effortless.

TokenBurner acts as your desktop's cybernetic companion:
- **Zero API Key Requirement**: No credit card or API tokens needed. TokenBurner reads existing local session caches created by your desktop tools.
- **100% Local & Privacy-First**: No code, prompts, or personal telemetry are ever transmitted to any remote server.
- **桌宠级 3D 全息 HUD**: A frameless, hardware-accelerated WebGL holographic crystal that floats on your desktop with live particle bursts and real-time token counters.
- **年度赛博战报 (Cyber War Report)**: Generate 1080x1920 social posters with 24H stock-market momentum curves, RPG title progressions, and real-world equivalent benchmarks.

---

## ⚡ Supported AI Tools & IDEs

TokenBurner internally scans and aggregates compute metrics across:

| Platform / IDE | Data Source | Token Discovery |
| :--- | :--- | :--- |
| **GitHub Copilot** (WinApp & CLI) | `~/.copilot/session-state/` events | Automatic JSONL parsing |
| **DoubaoWork (豆包工作台)** | `%LOCALAPPDATA%\DoubaoWork` | LevelDB chat & sandbox logs |
| **Antigravity** | `~/.gemini/antigravity/brain/` | Multi-session transcripts |
| **Cursor** | `%APPDATA%\Cursor\User\globalStorage` | SQLite `state.vscdb` ItemTable |
| **ByteDance Trae** | `%APPDATA%\Trae\User\globalStorage` | SQLite `state.vscdb` ItemTable |
| **Alibaba Qoder / 通义灵码** | `~/.lingma`, `~/.qoder`, Code storage | Local conversation cache |
| **Tencent WorkBuddy** | `%APPDATA%\WorkBuddy` | Local SQLite & session DBs |
| **Baidu Comate (文心快码)** | `~/.comate` | Local completion logs |
| **CodeGeeX (智谱)** | `~/.codegeex` | Local workspace history |
| **Windsurf & Claude Code CLI** | `%APPDATA%\Windsurf`, `~/.claude` | Cascade DBs & CLI logs |

---

## 🎮 Key Features

### 1. 3D Holographic Desktop Core (Three.js + WebView2)
- **EVA-01 Test Type & Quantum Cyan**: Switch between EVA Toxic Purple-Green or Cyberpunk Cyan themes with OS-level hardware-accelerated rounded corners.
- **Reactive Particle Burst**: Every time new tokens are burned, neon particles surge through the 3D orbit rings.
- **Dynamic Period Switching**: Click the core to switch between **Total (🪐 ALL)**, **30-Day (🗓️ MONTH)**, **7-Day (📅 WEEK)**, and **24-Hour (⚡ TODAY)** stats.

### 2. Built-in YOLO Mode (Auto-Approver)
- Built-in OpenCV template matching allows background agents (like Claude Code, Antigravity, or terminal CLI agents) to auto-approve safe confirmation prompts with zero click friction.

### 3. Cyberpunk War Report Poster
- Instant generation of a 1080x1920 poster featuring:
  - **100-Level RPG Title Progression**: From *Mortal Era (凡人纪元)* to *Mythos Era (神话纪元)*.
  - **24H Parabolic Surge Curve**: Stock-chart momentum style with glowing neon beacon points.
  - **Real-World Power Equivalents**: Books digested, lines of code forged, espresso burned, and autonomous agent hours driven.

---

## 🛠️ Quick Start (30 Seconds)

### Prerequisites
- Windows 10 / 11 (64-bit)
- Python 3.10 or higher
- Microsoft Edge WebView2 (pre-installed on Windows 10/11)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/k114413450-stack/TokenBurner.git
   cd TokenBurner
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch TokenBurner**:
   ```bash
   # Double-click run_hud_3d.bat OR run in terminal:
   run_hud_3d.bat
   ```

---

## 🔒 Privacy & Security

- **No Remote Telemetry**: TokenBurner does not possess any cloud backend. All metrics are calculated directly on your local CPU.
- **Internal Recognition Only**: Your exact tools and workflows remain your secret. The user interface and exported posters celebrate your pure token power without exposing your underlying tool stack.
- **Read-Only Local Scanning**: TokenBurner only reads token byte lengths and character counts from existing local session files; it never modifies your IDE's internal state.

---

## 🤝 Contributing

Community contributions are warmly welcomed! You can help by:
- Adding support for more AI coding assistants and IDEs in `src/scanner.py`.
- Designing new 3D Three.js themes (e.g. Gundam, Matrix, Retro Synthwave) in `src/hud_3d.html`.
- Porting the desktop window manager to macOS and Linux.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
