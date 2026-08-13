# azure-functions-knowledge-python

[![Test and Coverage](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml/badge.svg)](https://github.com/yeongseon/azure-functions-knowledge-python/actions/workflows/ci-test.yml)
[![PyPI version](https://badge.fury.io/py/azure-functions-knowledge.svg)](https://badge.fury.io/py/azure-functions-knowledge)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Azure Functions Python v2용 지식 검색(RAG) 데코레이터입니다.

다른 언어로 읽기: [English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-CN.md)

> ℹ️ 이 번역은 커뮤니티가 관리하는 참고용 문서로, 최신 [English README](README.md)보다 뒤처질 수 있습니다. 정확한 최신 정보는 영어 원문을 기준으로 하세요.

## 기능

- **데코레이터 기반 API** — Azure Functions Python v2 프로그래밍 모델과의 원활한 통합
- **프로바이더 추상화** — 프로토콜 기반 인터페이스를 통한 플러거블 지식 프로바이더
- **Notion 지원** — 페이지 검색 및 조회를 위한 내장 Notion 프로바이더
- **비동기 지원** — 논블로킹 실행을 위한 자동 비동기 오프로딩
- **환경 변수 해석** — 안전한 자격 증명 처리를 위한 `%VAR%` 플레이스홀더 치환

## 설치

```bash
pip install azure-functions-knowledge[notion]
```

## 빠른 시작

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

## 데코레이터

### `input` — 데이터 주입

지식 프로바이더를 검색하고 결과를 핸들러에 주입합니다:

```python
@kb.input("docs", provider="notion", query="roadmap", connection="%NOTION_TOKEN%")
def handler(timer, docs: list[Document]) -> None:
    for doc in docs:
        print(doc.title, doc.url)
```

### `inject_client` — 클라이언트 주입

명령적 제어를 위해 프로바이더 인스턴스를 주입합니다:

```python
@kb.inject_client("client", provider="notion", connection="%NOTION_TOKEN%")
def handler(req, client) -> func.HttpResponse:
    doc = client.get_document(page_id)
    results = client.search("query", top=10)
    ...
```

## 커스텀 프로바이더

`KnowledgeProvider` 프로토콜을 구현하고 등록합니다:

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

## 문서

전체 문서: [https://yeongseon.github.io/azure-functions-knowledge-python/](https://yeongseon.github.io/azure-functions-knowledge-python/)

## 라이선스

MIT License. 자세한 내용은 [LICENSE](LICENSE)를 참조하세요.
