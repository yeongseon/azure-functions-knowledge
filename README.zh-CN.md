# azure-functions-knowledge-python

> ⚠️ **实验性（Experimental）** — 处于模式探索阶段。API 和行为可能会变化，暂不建议作为生产依赖使用。

[![Test and Coverage](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/azure-functions-knowledge.svg)](https://badge.fury.io/py/azure-functions-knowledge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Azure Functions Python v2 的知识检索（RAG）装饰器。

其他语言: [English](README.md) | [한국어](README.ko.md) | [日本語](README.ja.md)

## 功能

- **基于装饰器的 API** — 与 Azure Functions Python v2 编程模型无缝集成
- **Provider 抽象** — 通过基于协议的接口实现可插拔的知识 Provider
- **Notion 支持** — 内置 Notion Provider，支持页面搜索和检索
- **异步支持** — 自动异步卸载，实现非阻塞执行
- **环境变量解析** — 通过 `%VAR%` 占位符替换实现安全的凭证处理

## 安装

```bash
pip install azure-functions-knowledge[notion]
```

## 快速开始

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

## 装饰器

### `input` — 数据注入

搜索知识 Provider 并将结果注入到处理器中：

```python
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    for doc in docs:
        print(doc.title, doc.url)
```

### `inject_client` — 客户端注入

注入 Provider 实例以进行命令式控制：

```python
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def handler(req, client) -> func.HttpResponse:
    doc = client.get_document(page_id)
    results = client.search("query", top=10)
    ...
```

## 自定义 Provider

实现 `KnowledgeProvider` 协议并注册：

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

## 文档

完整文档: [https://yeongseon.github.io/azure-functions-knowledge-python/](https://yeongseon.github.io/azure-functions-knowledge-python/)

## 许可证

MIT License。详情请参阅 [LICENSE](LICENSE)。
