# LunaWallet

LunaWallet is a cryptocurrency wallet application with multi‑wallet management, rewards handling, and a simple GUI.

## Key Features
- Create and manage multiple wallets
- Reward balance calculation and correction
- Sequential reward compression
- Transaction limits and inter‑wallet transfers
- Key export/import
- Intuitive GUI

## Directory Overview
- main.py: Application entry point
- gui/: GUI pages and tabs
- utils.py: Utility functions
- test_multi_wallet_rewards.py: Tests
- assets/, images/, sounds/: Resources

## Install & Use
### Prerequisites
- Python 3.11+
- Windows / macOS / Linux

### 1) Install dependencies
```bash
pip install -r requirements.txt
```

### 2) Run the app
Choose one of the following:

**Option A: Run directly (recommended)**
```bash
python main.py
```

**Option B: Run with Flet**
```bash
flet run
```

### 3) First‑time usage
1. On the lock screen, choose **Create Wallet** or **Import Wallet**
2. After creating/importing, unlock to start syncing
3. Select a wallet in the sidebar to view balance and history
4. Use the top buttons for Send / Receive / Key export

### 4) Common actions
- **Switch wallets**: Click a wallet in the sidebar
- **Refresh history**: Click the refresh icon in Recent Transactions
- **Export key**: Click **Key**

### 5) Troubleshooting
- Dependency issues: re‑run `pip install -r requirements.txt`
- UI not updating: restart the app and wait for sync to finish

## License
This project is licensed under the MIT License.

---

# LunaWallet（中文）

LunaWallet 是一款支持多钱包管理、奖励处理与图形界面的加密货币钱包应用。

## 主要功能
- 创建与管理多个钱包
- 奖励余额计算与修正
- 奖励交易序列压缩
- 交易限制与钱包间转账
- 私钥导出/导入
- 直观的图形界面

## 目录概览
- main.py：应用入口
- gui/：界面页面与标签
- utils.py：工具函数
- test_multi_wallet_rewards.py：测试代码
- assets/、images/、sounds/：资源文件

## 安装与使用
### 环境要求
- Python 3.11+
- Windows / macOS / Linux

### 1) 安装依赖
```bash
pip install -r requirements.txt
```

### 2) 启动应用
二选一：

**方式A：直接启动（推荐）**
```bash
python main.py
```

**方式B：使用 Flet 启动**
```bash
flet run
```

### 3) 首次使用流程
1. 在锁屏界面选择 **Create Wallet** 或 **Import Wallet**
2. 创建/导入后解锁，开始同步
3. 在左侧侧边栏选择钱包查看余额与交易记录
4. 顶部按钮用于发送/接收/导出密钥

### 4) 常用操作
- **切换钱包**：点击侧边栏的钱包
- **刷新记录**：点击 Recent Transactions 的刷新按钮
- **导出密钥**：点击 **Key**

### 5) 常见问题
- 依赖问题：重新执行 `pip install -r requirements.txt`
- 界面未更新：重启应用并等待同步完成

## 许可证
本项目采用 MIT 许可证。
