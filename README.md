# LunaWallet
# LunaWallet

LunaWalletは、複数ウォレット管理、報酬システム、圧縮機能などを備えた仮想通貨ウォレットアプリケーションです。

## 主な機能
- 複数ウォレットの作成・管理
- 報酬残高の計算・修正
- シーケンシャル圧縮による報酬管理
- トランザクション制限・インターワレット転送
- 鍵のエクスポート・インポート
- GUIによる直感的な操作

## ディレクトリ構成
- main.py : アプリケーションのエントリーポイント
- gui/ : GUI関連のページ・タブ
- utils.py : ユーティリティ関数
- test_multi_wallet_rewards.py : テストコード
- assets/, images/, sounds/ : 各種リソース

## セットアップ
1. 必要なPythonパッケージをインストール
	```bash
	pip install -r requirements.txt
	```
2. main.pyを実行してアプリを起動
	```bash
	python main.py
	```

## ライセンス
本プロジェクトはMITライセンスです。
