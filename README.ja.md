# azure-functions-knowledge-python

[![Test and Coverage](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/azure-functions-knowledge.svg)](https://badge.fury.io/py/azure-functions-knowledge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Azure Functions Python v2向けのナレッジ検索（RAG）デコレーターです。

他の言語で読む: [English](README.md) | [한국어](README.ko.md) | [简体中文](README.zh-CN.md)

> ℹ️ この翻訳はコミュニティによる参考用であり、最新の [English README](README.md) より古い場合があります。正確な最新情報は英語版を参照してください。

## 機能

- **デコレーターベースのAPI** — Azure Functions Python v2プログラミングモデルとのシームレスな統合
- **プロバイダー抽象化** — プロトコルベースのインターフェースによるプラガブルなナレッジプロバイダー
- **Notion対応** — ページの検索・取得のための組み込みNotionプロバイダー
- **非同期サポート** — ノンブロッキング実行のための自動非同期オフローディング
- **環境変数解決** — 安全な認証情報処理のための `%VAR%` プレースホルダー置換

## インストール

```bash
pip install azure-functions-knowledge[notion]
```

## クイックスタート

```python
import azure.functions as func
from azure_functions_knowledge import Document, KnowledgeBindings

app = func.FunctionApp()
kb = KnowledgeBindings()

@app.route(route="search", methods=["GET"])
@kb.input(
    "docs",
    provider="notion",
    query=lambda req: req.params.get("q", ""),
    top=5,
    connection="%NOTION_TOKEN%",
)
def search(req: func.HttpRequest, docs: list[Document]) -> func.HttpResponse:
    import json
    results = [{"title": d.title, "url": d.url} for d in docs]
    return func.HttpResponse(json.dumps(results), mimetype="application/json")
```

## デコレーター

### `input` — データインジェクション

ナレッジプロバイダーを検索し、結果をハンドラーに注入します：

```python
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    for doc in docs:
        print(doc.title, doc.url)
```

### `inject_client` — クライアントインジェクション

命令的な制御のためにプロバイダーインスタンスを注入します：

```python
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def handler(req, client) -> func.HttpResponse:
    doc = client.get_document(page_id)
    results = client.search("query", top=10)
    ...
```

## カスタムプロバイダー

`KnowledgeProvider` プロトコルを実装して登録します：

```python
from azure_functions_knowledge import Document, register_provider

class MyProvider:
    def __init__(self, *, connection, **kwargs):
        ...

    def search(self, query: str, *, top: int = 5) -> list[Document]:
        ...

    def get_document(self, document_id: str) -> Document:
        ...

    def close(self) -> None:
        ...

register_provider("my-provider", MyProvider)
```

## ドキュメント

完全なドキュメント: [https://yeongseon.github.io/azure-functions-knowledge-python/](https://yeongseon.github.io/azure-functions-knowledge-python/)

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
